"""Small deterministic fixtures; real-model scenarios live in acceptance.py."""
import asyncio
import base64
import io
import json
import os
from pathlib import Path
import sqlite3
import stat
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'vendor')]
import antiloop
import beta5_helpers as h
import handover as ho
import ledger as lg
import protocol as proto
import scheduler as sch
import tokens
from service import Service
from run_export import redact


def zipdata(entries):
    out = io.BytesIO()
    with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for name,content in entries:
            archive.writestr(name,content)
    return base64.b64encode(out.getvalue()).decode()


class ProtocolTests(unittest.TestCase):
    def test_done_halt_and_quoted_halt(self):
        for text,expected in [('Done\n{"status":"DONE"}','done'),
                ('{"status":"HALT","reason":"blocked"}','halted'),
                ('Quoted example: {"status":"HALT"}\n{"status":"DONE"}','done'),
                ('A tool said HALT.','failed'),('unfinished','failed')]:
            with self.subTest(text=text):
                self.assertEqual(proto.judge(text,[],True)[0],expected)

    def test_native_final_publication_forms(self):
        for text in ['{"status":"DONE","magazine_result":{"result":"ok"}}',
                     'Comment\n```json\n{"status":"DONE","magazine_result":{"result":"ok"}}\n```',
                     'Comment\n{"magazine_result":{"result":"ok"}}\n{"status":"DONE"}']:
            with self.subTest(text=text):self.assertEqual(proto.native_result_payload(text),{'result':'ok'})
        for text in ['{"status":"HALT","magazine_result":{"result":"bad"}}',
                     '{"status":"DONE","status":"DONE","magazine_result":{"result":"bad"}}',
                     '{"status":"DONE","magazine_result":{"x":NaN}}',
                     '{"status":"DONE","magazine_result":{"result":"bad"}}\nMore text']:
            with self.subTest(text=text):self.assertIsNone(proto.native_result_payload(text))

    def test_five_attempt_ceiling_and_stop(self):
        self.assertEqual(proto.recovery_policy()['attempt_seconds'],1800)
        for n in range(1,6):
            decision=lg.decide_retry({'status':'failed','code':'DONE_MISSING','recovery':'repair'},n,5-n,repeated=True)
            self.assertEqual(decision['decision'],'retry' if n<5 else 'stop')
        for value in ({'max_attempts':6},{'max_attempts':True},{'attempt_seconds':0}):
            with self.subTest(value=value),self.assertRaises(proto.ProtocolError):
                proto.recovery_policy(value)
        self.assertEqual(lg.decide_retry({'status':'failed','code':'DONE_MISSING','recovery':'repair'},1,4,stop_requested=True)['decision'],'stop')

    def test_strict_json_and_identity(self):
        for raw in ('{"x":1,"x":2}','{"x":NaN}','[] trailing'):
            with self.subTest(raw=raw),self.assertRaises(ValueError):
                ho.strict_json(raw)
        document={'schema':'magazine.result.v1','run_id':'r','cartridge_id':'c','attempt_id':'a','session_id':'s','payload':{'result':'ok'}}
        protocol={'result_profile':'generic','cartridges':{'c':{'handover':[]}}}
        identity={k:document[k] for k in ('run_id','cartridge_id','attempt_id','session_id')}
        ho.validate_envelope(document,identity,protocol,'c')
        for key in identity:
            with self.subTest(key=key),self.assertRaises(ho.ResultFailure):
                ho.validate_envelope(dict(document,**{key:'wrong'}),identity,protocol,'c')

    def test_tokens_unavailable_zero_partial_and_cumulative(self):
        self.assertIsNone(tokens.message_usage({'input':0,'output':0,'totalTokens':0}))
        self.assertEqual(tokens.message_usage({'input':0,'output':0,'totalTokens':0,'reported':True})['total'],0)
        partial=tokens.message_usage({'input':12})
        self.assertIsNone(partial['total'])
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'session.jsonl'
            rows=[{'type':'message','id':'a','message':{'role':'assistant','content':[]}},
                {'type':'message','id':'b','message':{'role':'assistant','usage_scope':'native_session_cumulative',
                'usage':{'input':20,'output':3,'totalTokens':23,'reported':True,'coverage_complete':True}}}]
            p.write_text(''.join(json.dumps(r)+'\n' for r in rows))
            one=tokens.from_session(p,finished_normally=True)
            self.assertEqual(one['total'],23)
            self.assertFalse(one['incomplete'])
            self.assertEqual(tokens.from_session(p,finished_normally=True),one)

    def test_antiloop_visible_structured_events_only(self):
        police=antiloop.LoopPolice()
        police.observe({'event':'reasoning','text':'HALT '*20})
        self.assertEqual(police.observed,0)
        for i in range(3):
            police.observe({'event':'assistant','toolCalls':[{'id':str(i),'name':'read_file','argsSha256':'same'}]})
            event={'event':'tool_result','toolCallId':str(i),'resultSha256':'same','isError':True}
            if i<2:
                police.observe(event)
            else:
                with self.assertRaises(antiloop.LoopDetected):
                    police.observe(event)

    def test_storage_retries_are_separate_and_transient_only(self):
        import errno
        import executor as ex
        executor=ex.CartridgeExecutor.__new__(ex.CartridgeExecutor)
        executor.protocol={'recovery':{'io_retries':2}}
        calls=[]
        def transient():
            calls.append(1)
            if len(calls)<3:raise OSError(errno.EAGAIN,'transient')
            return 'committed'
        attempt={}
        self.assertEqual(asyncio.run(executor.retry_storage(attempt,transient)),'committed')
        self.assertEqual(len(attempt['storage_retries']),2)
        for code in (errno.EACCES,errno.ENOSPC,errno.ENOENT):
            failed=[]
            def permanent():
                failed.append(1);raise OSError(code,'permanent')
            with self.subTest(code=code),self.assertRaises(ho.ResultFailure):
                asyncio.run(executor.retry_storage({},permanent))
            self.assertEqual(len(failed),1)

    def test_secret_redaction_and_visible_reasoning_filter(self):
        from ui_support import visible_message
        content=visible_message({'type':'message','message':{'role':'assistant','content':[
            {'type':'thinking','thinking':'PRIVATE'},{'type':'text','text':'<think>PRIVATE</think>Visible'}]}},'model',())
        self.assertNotIn('PRIVATE',json.dumps(content))
        self.assertNotIn('abc123',json.dumps(redact({'authorization':'Bearer abc123','text':'api_key="abc123"'})))


@unittest.skipUnless(sys.platform=='linux','Linux filesystem semantics')
class StorageTests(unittest.TestCase):
    def setUp(self):
        tempfile.tempdir = None
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.service=Service(self.root/'data',{'cwd':str(self.root/'work')})
    def tearDown(self):
        asyncio.run(self.service.close())
        self.service.scheduler.db.close()
        self.temp.cleanup()

    def test_archive_attacks_and_yml(self):
        manifest='schema_version: "1.0"\nname: Small\ncartridges:\n  - id: one\n    model: general\n    prompt: Test\n'
        for entries in [ [('magazine.yaml',manifest),('../escape','x')],
                [('magazine.yaml',manifest),('a','x'),('A','y')],
                [('magazine.yaml',manifest),('a','x'),('a','x')],
                [('magazine.yaml',manifest),('/absolute','x')],
                [('magazine.yaml',manifest),('nested\\evil','x')],
                [('magazine.yaml',manifest),('bomb','0'*1024*1024)]]:
            with self.subTest(entries=[e[0] for e in entries]),self.assertRaises(h._LibraryError):
                h._library_import(str(self.service.root/'library'),'attack.zip',zipdata(entries))
        symlink=zipfile.ZipInfo('link');symlink.create_system=3;symlink.external_attr=(stat.S_IFLNK|0o777)<<16
        with self.assertRaises(h._LibraryError):
            h._library_import(str(self.service.root/'library'),'link.zip',zipdata([('magazine.yaml',manifest),(symlink,'/etc/passwd')]))
        good=h._library_import(str(self.service.root/'library'),'small.zip',zipdata([('magazine.yml',manifest)]))
        self.assertTrue(good['imported'])
        self.assertEqual(self.service.list_runs(),[])

    def test_yaml_duplicate_alias_and_unknown_fields(self):
        from magazine.package import _parse_yaml
        for text in ['x: 1\nx: 2','x: &anchor [1]\ny: *anchor']:
            with self.subTest(text=text),self.assertRaises(Exception):
                _parse_yaml(text)

    def test_readback_and_tamper(self):
        base=self.root/'attempt'
        receipt=ho.durable_json(base/'publish/result.json',{'ok':True})
        doc,info=ho.read_result_file(base)
        self.assertEqual(receipt['sha256'],info['sha256'])
        self.assertEqual(doc,{'ok':True})
        (base/'publish/result.json').unlink()
        (base/'publish/result.json').symlink_to('/etc/passwd')
        with self.assertRaises((ho.ResultFailure,OSError)):
            ho.read_result_file(base)

    def test_sqlite_scheduler_restart_requires_start(self):
        async def go():
            events=[]
            async def launch(entry):events.append(entry['run_id'])
            s=sch.Scheduler(self.root/'data',launch)
            s.set_mode('round_robin')
            s.admit('a'*12,'local',0)
            s.admit('b'*12,'local',0)
            s.db.close()
            # JSON is an export cache; SQLite remains authoritative.
            s.journal.write_text('corrupted cache')
            restored=sch.Scheduler(self.root/'data',launch)
            self.assertEqual(restored.mode,'round_robin')
            self.assertEqual([e['run_id'] for e in restored.queue],['a'*12,'b'*12])
            self.assertTrue(all(e['needs_start'] for e in restored.queue))
            await restored.pump()
            self.assertEqual(events,[])
            self.assertGreater(restored.db.execute('SELECT count(*) FROM journal').fetchone()[0],0)
            restored.db.close()
        asyncio.run(go())

    def test_commit_crash_reconciles_without_model_replay(self):
        from types import SimpleNamespace
        import executor as ex
        doc={'schema_version':'1.0','cartridges':[{'id':'one','job_type':'general','prompt':'Task'}]}
        protocol=proto.default_protocol(doc)
        layout=ho.Layout(self.root/'run',self.root/'work','a'*12,protocol)
        final='{"status":"DONE","magazine_result":{"result":"ok"}}'
        attempt={'attempt_id':'b'*32,'session_id':'native-test','status':'done','phase':'committed','outputs':[],
                 'tokens':tokens.unavailable(),'attempt_number':1}
        base=ho.setup_attempt(layout,'one',attempt,'Task')
        session=self.root/'native.jsonl'
        session.write_text(json.dumps({'type':'session','id':'native-test'})+'\n'+json.dumps({'type':'message','message':{'role':'assistant','content':[{'type':'text','text':final}]}})+'\n')
        attempt['session_archive']=ho.archive_session(layout,'one',attempt,session)
        document=dict(ho.attempt_identity('a'*12,'one',attempt),schema='magazine.result.v1',payload={'result':'ok'})
        source=ho.durable_json(base/'publish/result.json',document)
        attempt['handover']=ho.commit_attempt_result(layout,'one',attempt,document,source,[])
        ledger=lg.new('a'*12,['one'],'result_file_v1')
        ledger['cartridges']['one']={'status':'done','attempts':[attempt]}
        executor=ex.CartridgeExecutor.__new__(ex.CartridgeExecutor)
        executor.core={'ss':SimpleNamespace(load_run_state=lambda path:{'current':'one'})}
        executor.state_path='unused';executor.meta={'document':doc,'cartridge_models':{'one':'custom/model'}}
        executor.scheduler=None;executor._calls=0;executor.mode='result_file_v1';executor.ledger=ledger
        executor.layout=layout;executor.run_base=layout.base;executor.run_id='a'*12
        async def forbidden(*args):raise AssertionError('Committed cartridge was replayed')
        executor.run_cartridge=forbidden
        self.assertEqual(asyncio.run(executor('Task','custom/model')),final)
        self.assertEqual(len(ledger['cartridges']['one']['attempts']),1)
        (layout.base/attempt['session_archive']['path']).write_text('tampered')
        with self.assertRaises(ho.ResultFailure):ho.committed_final(layout,ledger,'one')

    def test_single_process_owner(self):
        import fcntl
        a=open(self.root/'lock','a+b');b=open(self.root/'lock','a+b')
        try:
            fcntl.flock(a,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError):fcntl.flock(b,fcntl.LOCK_EX|fcntl.LOCK_NB)
        finally:a.close();b.close()


if __name__=='__main__':
    unittest.main(verbosity=2)
