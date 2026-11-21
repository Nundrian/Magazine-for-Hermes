"""Real Hermes inference with controlled publication loss at the adapter boundary.

The injection lives only in this test process, never in shipped engine paths.
Run while other acceptance workflows are idle; the global execution flock also
refuses overlap. State and transcripts remain in a separate disposable root.
"""
import asyncio
from datetime import datetime
import json
from pathlib import Path
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'vendor')]
import executor as ex
from service import Service


async def main():
    root=Path('/opt/data/plugin-data/magazine-fault-tests')/uuid.uuid4().hex[:10]
    Path('/workspace/fault-tests').mkdir(exist_ok=True)
    service=Service(root,{'cwd':'/workspace/fault-tests','python':'/opt/hermes/.venv/bin/python'})
    reports=[]
    original=ex.CartridgeExecutor.one_attempt
    mode='once'

    async def inject(self,cid,prompt,model_id,attempt):
        run=self.dispatch.run
        async def with_loss(*args,**kwargs):
            result=await run(*args,**kwargs)
            if mode=='always' or attempt['attempt_number']==1:
                Path(kwargs['publish']['resultPath']).unlink()
                attempt['test_fault']='Publication file removed after genuine completed Hermes execution and before controller read-back'
            return result
        self.dispatch.run=with_loss
        try:return await original(self,cid,prompt,model_id,attempt)
        finally:self.dispatch.run=run

    ex.CartridgeExecutor.one_attempt=inject
    try:
        for case in ('once','always'):
            mode=case
            document={'schema_version':'1.0','cartridges':[{'id':'fault','job_type':'general',
                'prompt':'The complete text deliverable is FAULT. Put FAULT in the result note.'}]}
            prepared=await service.handle({'action':'prepare','data':{'magazine':json.dumps(document),
                'default_model':'custom/bonsai-2:27b','tool_ids':[],'handover_mode':'result_file_v1'}})
            rid=prepared['run_id']
            await service.handle({'action':'start','data':{'run_id':rid}})
            for _ in range(600):
                status=await service.handle({'action':'status','data':{'run_id':rid}})
                if status['status'] in ('COMPLETED','HALTED') and not status['active']:break
                await asyncio.sleep(1)
            else:raise TimeoutError(rid)
            ledger=(await service.handle({'action':'ledger','data':{'run_id':rid}}))['ledger']
            attempts=ledger['cartridges']['fault']['attempts']
            assert (2<=len(attempts)<=5 if case=='once' else len(attempts)==5),attempts
            assert len({a['session_id'] for a in attempts})==len(attempts)
            assert status['status']==('COMPLETED' if case=='once' else 'HALTED'),status
            if case=='always':
                try:
                    await service.handle({'action':'recover','data':{'run_id':rid}})
                    await service.handle({'action':'start','data':{'run_id':rid}})
                except ValueError as error:
                    assert 'five' in str(error).lower() or '5' in str(error),error
                else:raise AssertionError('Sixth attempt accepted')
            reports.append({'scenario':case,'run_id':rid,'state_root':str(root),'status':status,'ledger':ledger})
            Path('/workspace/fault-report.json').write_text(json.dumps(reports,indent=2))
            print('PASS real publication fault',case,rid,'attempts',len(attempts),flush=True)
    finally:
        ex.CartridgeExecutor.one_attempt=original
        await service.close()


if __name__=='__main__':asyncio.run(main())
