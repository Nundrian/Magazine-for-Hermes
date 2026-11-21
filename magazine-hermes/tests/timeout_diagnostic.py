"""Disposable real-process timeout diagnostic; no model inference."""
import asyncio
import json
from pathlib import Path
import sys
import tempfile
import traceback
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from hermes_dispatch import HermesDispatch

async def main():
    with tempfile.TemporaryDirectory(prefix='magazine-timeout-') as temp:
        dispatch=HermesDispatch({'dataDir':temp,'cwd':temp},temp)
        if sys.argv[1:]==['real']:
            dispatch.config.update(cwd='/workspace',tools=['terminal'])
            try:
                await dispatch.run('Use terminal to run sleep 120. Wait for completion before responding.',
                                   'custom/bonsai-2:27b',timeout=40)
            except asyncio.TimeoutError:
                assert dispatch.terminated
                print('PASS real native timeout cleanup diagnostic')
            except BaseException:
                Path('/workspace/timeout-traceback.txt').write_text(traceback.format_exc())
                raise
            else:raise AssertionError('Timeout was not raised')
            return
        async def spawn(request):
            dispatch.process=await asyncio.create_subprocess_exec(sys.executable,'-c',
                'import subprocess,time; subprocess.Popen(["sleep","90"]);time.sleep(90)',
                stdout=asyncio.subprocess.PIPE,stdin=asyncio.subprocess.PIPE,start_new_session=True)
        dispatch._spawn=spawn
        try:await dispatch._request({'action':'run'},timeout=1)
        except asyncio.TimeoutError:
            assert dispatch.terminated
            print('PASS actual worker/descendant timeout cleanup without inference')
        except BaseException:
            Path('/workspace/timeout-traceback.txt').write_text(traceback.format_exc())
            raise
        else:raise AssertionError('Timeout was not raised')
        async def broken_cleanup():raise OSError(22,'injected cleanup failure')
        dispatch.terminate=broken_cleanup
        async def no_spawn(request):pass
        async def no_read():return {}
        dispatch._spawn=no_spawn
        dispatch._read=no_read
        try:await dispatch._request({'action':'run'},timeout=1)
        except OSError:pass
        else:raise AssertionError('Injected cleanup failure was not surfaced')
        assert json.loads((Path(temp)/'uncertain-execution.json').read_text())['state']=='UNKNOWN'
        print('PASS cleanup exception always persists UNKNOWN admission gate')
asyncio.run(main())
