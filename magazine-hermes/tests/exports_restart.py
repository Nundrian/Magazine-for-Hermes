"""Real dashboard exports/auth and idle-container restart acceptance; no inference."""
import base64
import hashlib
import io
import json
from pathlib import Path
import stat
import sys
import time
import urllib.error
import urllib.request
import zipfile
from acceptance import rpc, BASE

workspace=Path('/workspace')
report_path=workspace/'exports-restart-report.json'
phase=sys.argv[1]
rid=(workspace/'basic-run-id').read_text().strip()

def retained():
    status=rpc('status',run_id=rid)
    ledger=rpc('ledger',run_id=rid)['ledger']
    assert status['status']=='COMPLETED' and not status['active'],status
    artifacts={str(p.relative_to(workspace)):hashlib.sha256(p.read_bytes()).hexdigest()
               for p in (workspace/'magazine-runs'/rid).rglob('*.txt') if p.is_file()}
    return {'status':status['status'],'done':status['done'],'ledger':ledger,'artifacts':artifacts}

if phase=='before':
    for token in (None,'incorrect-test-token'):
        headers={'Content-Type':'application/json'}
        if token:headers['X-Hermes-Session-Token']=token
        req=urllib.request.Request(BASE+'/api/plugins/magazine/rpc',b'{"action":"runs","data":{}}',headers=headers)
        try:urllib.request.urlopen(req,timeout=15)
        except urllib.error.HTTPError as error:assert error.code in (401,403),error.code
        else:raise AssertionError('Unauthorised Magazine RPC succeeded')
    assert stat.S_IMODE(Path('/opt/data/plugin-data/magazine/engine.sock').stat().st_mode)==0o600
    captures={}
    for action in ('download','download_jsonl','download_ledger','download_history'):
        value=rpc(action,run_id=rid)
        raw=base64.b64decode(value['file_data_b64'])
        (workspace/value['file_name']).write_bytes(raw)
        captures[action]={'file':value['file_name'],'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
        if action=='download':
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                assert archive.testzip() is None
                names=archive.namelist()
                assert len(names)==len(set(names))
                assert archive.read('verified-artifacts/first/hello.txt')==b'HELLO MAGAZINE\n'
                assert archive.read('verified-artifacts/second/verified.txt')==b'HELLO MAGAZINE VERIFIED\n'
                assert 'magazine-ledger/prepared-config.json' in names
        elif action=='download_jsonl':
            records=[json.loads(line) for line in raw.splitlines()]
            assert any(r['kind']=='execution_history' for r in records)
            sessions={r['session_id'] for r in records if r['kind']=='session_record'}
            assert len(sessions)>=2
        elif action=='download_ledger':assert json.loads(raw)['cartridges']['second']['status']=='done'
        else:assert len([json.loads(line) for line in raw.splitlines()])>1
    runs=rpc('runs')
    assert not any(r.get('active') for r in runs['runs']), 'Restart requires an idle test environment'
    report={'passed_before':True,'run_id':rid,'before':retained(),'exports':captures,
            'unauthorised_requests_denied':True,'socket_mode':'0600','scheduler_before':runs['scheduler']}
    report_path.write_text(json.dumps(report,indent=2))
    print('PASS exports, independently verified ZIP artifacts, JSONL/history and dashboard authentication')
elif phase=='after':
    report=json.loads(report_path.read_text())
    before=report['before']
    after=retained()
    assert before==after,'Saved run/ledger/artifacts changed over idle container restart'
    runs=rpc('runs')
    assert not any(r.get('active') for r in runs['runs'])
    time.sleep(3)
    assert retained()==before
    assert any(c['run_id']==rid for c in rpc('chats')['chats'])
    report.update(passed_after=True,container_restart_preserved_run_ledger_artifacts_chats=True,
                  automatic_resume=False,scheduler_after=runs['scheduler'])
    report_path.write_text(json.dumps(report,indent=2))
    print('PASS actual idle container restart; saved run, ledger, artifacts and chats retained; no automatic inference')
else:raise ValueError(phase)
