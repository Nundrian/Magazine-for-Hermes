"""Build a shareable metrics-only report; never package native chats/prompts."""
import argparse
from datetime import datetime
import json
from pathlib import Path

parser=argparse.ArgumentParser()
parser.add_argument('--evidence',type=Path,required=True)
args=parser.parse_args()
workspace=args.evidence/'workspace'
records=[json.loads((workspace/'basic-report.json').read_text())]
scenarios=json.loads((workspace/'scenarios-report.json').read_text())
groups={}
for record in scenarios:groups.setdefault(record['scenario'],[]).append(record)
for name,values in groups.items():records.extend(values[-2:] if name.startswith('H ') else values[-1:])
records.extend(json.loads((workspace/'fault-report.json').read_text()))
out=[]
for record in records:
    ledger=record['ledger']
    if 'ledger' in ledger:ledger=ledger['ledger']
    attempts=[]
    for cid,cartridge in ledger['cartridges'].items():
        for a in cartridge['attempts']:
            tools=sorted({b['name'] for e in a.get('visible_evidence',[]) for b in e.get('blocks',[]) if b.get('type')=='tool_call'})
            attempts.append({'cartridge':cid,'number':a['attempt_number'],'session_id':a.get('session_id'),
                'model':a['model'],'provider':a.get('provider'),'status':a['status'],'code':a.get('code'),
                'started':a.get('started'),'finished':a.get('finished'),'tokens':a.get('tokens'),
                'observed_native_tools':tools,'selected_toolsets':a.get('selected_toolsets'),
                'active_tools':a.get('active_tools'),'timeout_seconds':a.get('timeout_seconds')})
    out.append({'scenario':record['scenario'],'run_id':record['run_id'],'status':record['status']['status'],
                'display_status':record['status'].get('display_status'),'attempts':attempts})
report={'date':'2026-11-21','evidence_kind':'Actual isolated Hermes + installed local Ollama models',
    'usage_limits':'Native cumulative reported counts; absent cache/per-call coverage remains unavailable/incomplete. No estimates.',
    'runs':out,'browser_reports':{name:json.loads((args.evidence/name/'report.json').read_text())
                                for name in ('firefox-final','chromium-final','firefox-release','chromium-release','browser-persistence','browser-live')},
    'engine_crash':json.loads((workspace/'restart-crash-report.json').read_text()),
    'container_restart_and_exports':{k:v for k,v in json.loads((workspace/'exports-restart-report.json').read_text()).items()
                                    if k not in ('before','scheduler_before','scheduler_after')},
    'deterministic_checks':json.loads((workspace/'deterministic-report.json').read_text()),
    'installer_lifecycle_passed':json.loads((args.evidence/'install-workspace/install-report.json').read_text())['passed'],
    'installer_runtime_service_ipc':json.loads((args.evidence/'install-workspace/install-report.json').read_text())['runtime_service_ipc']}
normal=args.evidence/'deployment/report.json'
if normal.exists():
    value=json.loads(normal.read_text())
    report['normal_host_smoke']={k:value[k] for k in ('passed','browsers','model_count','toolset_count','active_runs','inference_started','native_data_retained')}
target=Path(__file__).resolve().parents[1]/'docs/acceptance-results.json'
target.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'report':str(target),'real_runs':len(out),'real_attempts':sum(len(r['attempts']) for r in out)}))
