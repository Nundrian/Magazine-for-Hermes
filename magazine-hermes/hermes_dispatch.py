"""Fresh Hermes workers behind the unchanged injected dispatch boundary.

One worker process per attempt. The process is the cancellation unit: STOP and
Antiloop ask the SDK to abort and wait for its acknowledgement; a timeout or an
unacknowledged worker is terminated by process group and waited for.
"""
import asyncio
import json
import os
import signal
import fcntl
from pathlib import Path
from types import SimpleNamespace
from magazine.durability import atomic_write


class WorkerFailure(ValueError):
    """The worker reported a failure before a saved outcome existed."""


class HermesDispatch:
    def __init__(self, config, session_root):
        self.config = config
        self.session_root = str(session_root)
        self.process = None
        self.reader = None
        self.abort_receipt = None
        self.active_chat_id = None
        self.active_session_file = None
        self.cancel_requested = False
        self.cancel_confirmed = False
        self.on_event = None
        self.terminated = None

    async def _spawn(self, request):
        self.process = await asyncio.create_subprocess_exec(
            self.config.get('python', '/opt/hermes/.venv/bin/python'), str(Path(__file__).with_name('hermes_worker.py')),
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            cwd=self.config['cwd'], limit=8 * 1024 * 1024,
            pass_fds=tuple([int(os.environ['MAGAZINE_OWNER_FD'])] if os.environ.get('MAGAZINE_OWNER_FD') else []) + ((self._execution_file.fileno(),) if getattr(self,'_execution_file',None) else ()),
            env={**os.environ}, start_new_session=True)
        if request.get('action') == 'run':
            # Admission is durable before sending the inference-triggering bytes.
            root = Path(self.config['dataDir'])
            identity = Path(f'/proc/{self.process.pid}/stat').read_text().split()[21]
            atomic_write(str(root/'worker-admission.json'),json.dumps({'pid':self.process.pid,'start_ticks':identity,
                'session_root':self.session_root,'state':'ADMITTED'}).encode())
        self.process.stdin.write((json.dumps(request) + '\n').encode())
        await self.process.stdin.drain()

    async def catalogue(self):
        return await self._request({'action': 'catalogue'})

    async def __call__(self, prompt, model_id):
        """pi.5 contract: exact prompt, exact model, final text only."""
        result = await self.run(prompt, model_id)
        if result.get('finish') != 'stop':
            raise ValueError(f"Hermes worker did not finish normally: {result.get('finish') or 'missing response'}")
        if not result.get('text', '').strip():
            raise ValueError('Hermes worker has no final text')
        return result['text']

    async def run(self, prompt, model_id, *, publish=None, timeout=None, on_event=None):
        """One fresh saved session. Returns the worker's structured outcome."""
        self.cancel_requested = False
        self.cancel_confirmed = False
        self.active_chat_id = None
        self.active_session_file = None
        self.terminated = None
        self.on_event = on_event
        self.abort_receipt = asyncio.get_running_loop().create_future()
        request = {'action': 'run', 'prompt': prompt, 'model': model_id,
                   'tools': self.config.get('tools', []), 'sessionDir': self.session_root}
        if publish is not None:
            request['publish'] = publish
        import sys
        sys.path.insert(0, '/opt/hermes')
        from hermes_constants import get_default_hermes_root
        gate = get_default_hermes_root() / 'plugin-data/magazine-execution.lock'
        gate.parent.mkdir(parents=True,exist_ok=True)
        self._execution_file = open(gate,'a+b')
        try:
            try:fcntl.flock(self._execution_file,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:raise WorkerFailure('Another Magazine installation process holds global execution ownership')
            result = await self._request(request, timeout)
        finally:
            self._execution_file.close()
            self._execution_file = None
        if self.cancel_confirmed:
            raise asyncio.CancelledError('Hermes worker abort requested')
        if result.get('model') != model_id or not isinstance(result.get('text'), str):
            raise ValueError('Hermes dispatch response identity mismatch')
        return result

    async def _request(self, data, timeout=None):
        request = {**self.config, **data, 'dataDir': self.config['dataDir']}
        self.process, self.reader = None, None
        try:
            await self._spawn(request)
            self.reader = asyncio.create_task(self._read())
            limit = timeout if timeout is not None else self.config.get('timeoutSeconds', 1800)
            return await asyncio.wait_for(asyncio.shield(self.reader), limit)
        finally:
            try:
                self.terminated = await self.terminate()
            except BaseException:
                self.terminated = False
                raise
            finally:
                # Cleanup failures must never bypass the admission gate.
                if self.terminated is not True:
                    atomic_write(str(Path(self.config['dataDir'])/'uncertain-execution.json'),
                        json.dumps({'state':'UNKNOWN','reason':'Worker or descendant termination unconfirmed'}).encode())
                if self.reader is not None:
                    if not self.reader.done():self.reader.cancel()
                    await asyncio.gather(self.reader, return_exceptions=True)
            if not self.terminated:
                raise WorkerFailure('STOP_UNCONFIRMED: worker or subprocess termination uncertain')

    def _emit(self, event):
        if self.on_event is not None:
            try:
                self.on_event(event)
            except Exception:
                pass  # observers never break the worker channel

    async def _read(self):
        result = None
        while True:
            line = await self.process.stdout.readline()
            if not line:
                break
            event = json.loads(line)
            kind = event.get('event')
            if kind == 'session':
                self.active_chat_id = event.get('id')
                self.active_session_file = event.get('file')
                atomic_write(str(Path(self.session_root).parent/'active-worker.json'),
                    json.dumps({'session_id':self.active_chat_id,'phase':'created'}).encode())
                self._emit(event)
            elif kind == 'streaming':
                atomic_write(str(Path(self.session_root).parent/'active-worker.json'),
                    json.dumps({'session_id':self.active_chat_id,'phase':'streaming'}).encode())
                self._emit(event)
            elif kind in ('assistant', 'tool_result', 'published'):
                self._emit(event)
            elif kind == 'abort':
                self.cancel_confirmed = event.get('confirmed') is True
                if self.abort_receipt and not self.abort_receipt.done():
                    self.abort_receipt.set_result(event.get('confirmed') is True)
            elif kind == 'result':
                result = event
                break
        if result is None:
            raise WorkerFailure('Hermes worker exited without a result')
        if not result.get('ok'):
            if self.cancel_requested:
                # Let the abort acknowledgement arrive before settling failure.
                if self.abort_receipt and not self.abort_receipt.done():
                    try:
                        while True:
                            tail = await asyncio.wait_for(self.process.stdout.readline(), 2)
                            if not tail:
                                break
                            receipt = json.loads(tail)
                            if receipt.get('event') == 'abort':
                                self.cancel_confirmed = receipt.get('confirmed') is True
                                self.abort_receipt.set_result(receipt.get('confirmed') is True)
                                break
                    except asyncio.TimeoutError:
                        pass
                raise asyncio.CancelledError('Hermes worker aborted')
            raise WorkerFailure(result.get('error', 'Hermes worker failed'))
        return result['result']

    async def terminate(self):
        """Force the active worker's process group to exit; True once it has."""
        process = self.process
        import psutil
        descendants = []
        if process is not None:
            try:descendants = psutil.Process(process.pid).children(recursive=True)
            except psutil.NoSuchProcess:pass
        def alive(child):
            try:return child.is_running() and child.status()!=psutil.STATUS_ZOMBIE
            except psutil.NoSuchProcess:return False
        # Do not synchronously wait/reap descendants owned by Hermes while its
        # event loop is also supervising them. Reap our asyncio child only.
        for child in descendants:
            try:child.terminate()
            except psutil.NoSuchProcess:pass
        if process is not None and process.returncode is None:
            for sig, wait in ((signal.SIGTERM, 5), (signal.SIGKILL, 5)):
                try:os.killpg(process.pid, sig)
                except ProcessLookupError:pass
                try:
                    await asyncio.wait_for(process.wait(), wait)
                    break
                except asyncio.TimeoutError:continue
        for child in descendants:
            if alive(child):
                try:child.kill()
                except psutil.NoSuchProcess:pass
        deadline=asyncio.get_running_loop().time()+3
        while any(alive(child) for child in descendants) and asyncio.get_running_loop().time()<deadline:
            await asyncio.sleep(.1)
        return (process is None or process.returncode is not None) and not any(alive(child) for child in descendants)

    async def cancel_active(self):
        process = self.process
        if process is None or process.returncode is not None:
            return SimpleNamespace(confirmed=True, active=False, detail='Worker process absent')
        self.cancel_requested = True
        try:
            process.stdin.write(b'{"action":"abort"}\n')
            await process.stdin.drain()
            await asyncio.wait_for(process.wait(), 8)
        except (asyncio.TimeoutError, BrokenPipeError, ConnectionResetError):
            pass
        confirmed = await self.terminate()
        self.cancel_confirmed = confirmed
        return SimpleNamespace(confirmed=confirmed, active=True,
            detail='Hermes worker terminated and reaped' if confirmed else 'Worker termination uncertain')
