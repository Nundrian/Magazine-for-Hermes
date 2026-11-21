"""Single installation owner. Private Unix socket, process lock, no HTTP listener."""
import asyncio
import fcntl
import json
import os
from pathlib import Path
import signal
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / 'vendor'))
from magazine.durability import atomic_write


async def serve(root):
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    owner = open(root / 'owner.lock', 'a+b')
    try:
        fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return
    os.environ['MAGAZINE_OWNER_FD'] = str(owner.fileno())
    generation_path = root / 'engine-generation.json'
    previous = json.loads(generation_path.read_bytes()) if generation_path.exists() else {}
    from service import Service
    service = Service(root, {'cwd': '/workspace', 'dataDir': str(root), 'python': sys.executable})
    if previous and not previous.get('clean') and any(e.get('prepared') for e in service.scheduler.queue):
        atomic_write(str(root / 'uncertain-execution.json'), json.dumps({'state':'UNKNOWN','previous':previous,
            'reason':'Engine disappeared during an admitted cartridge. Inspect retained evidence and external side effects, then explicitly reconcile.'}).encode())
    atomic_write(str(generation_path), json.dumps({'pid':os.getpid(),'clean':False}).encode())
    socket = root / 'engine.sock' 
    socket.unlink(missing_ok=True)
    mutation_lock = asyncio.Lock()

    async def client(reader, writer):
        try:
            raw = await asyncio.wait_for(reader.readline(), 30)
            if len(raw) > 12 * 1024 * 1024:
                raise ValueError('Request too large')
            value = json.loads(raw)
            # Serialise state-changing requests; worker tasks remain independently cancellable.
            reads = {'library', 'preview', 'catalogue', 'runs', 'status', 'ledger', 'chat', 'chats',
                     'results', 'scheduler', 'trash', 'planning_brief', 'delete_preview'}
            if value.get('action') in reads or (value.get('action') == 'view_state' and not value.get('data', {}).get('set')):
                result = await service.handle(value)
            else:
                async with mutation_lock:
                    result = await service.handle(value)
            response = {'ok': True, 'result': result}
        except Exception as exc:
            response = {'ok': False, 'code': getattr(exc, 'code', getattr(exc, 'status_code', 409)),
                        'error': type(exc).__name__ + ': ' + str(exc)}
        try:
            writer.write((json.dumps(response, ensure_ascii=False, default=str) + '\n').encode())
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    old_umask=os.umask(0o077)
    try:
        server = await asyncio.start_unix_server(client, path=str(socket), limit=12*1024*1024)
    finally:
        os.umask(old_umask)
    socket.chmod(0o600)
    atomic_write(str(root / 'engine-owner.json'), json.dumps({'pid': os.getpid(), 'status': 'ready'}).encode())
    stop = asyncio.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        asyncio.get_running_loop().add_signal_handler(sig, stop.set)
    async with server:
        await stop.wait()
    await service.close()
    socket.unlink(missing_ok=True)
    atomic_write(str(generation_path),json.dumps({'pid':os.getpid(),'clean':True}).encode())
    owner.close()


if __name__ == '__main__':
    asyncio.run(serve(Path(sys.argv[1])))
