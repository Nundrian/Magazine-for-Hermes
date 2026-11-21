"""Crash an owned test engine; verify UNKNOWN, retained queue and explicit recovery."""
import json
import os
from pathlib import Path
import signal
import time
import psutil
from acceptance import prepare,rpc
from scenarios import SMALL

initial=rpc('runs')
if initial['scheduler'].get('uncertain_execution'):rpc('reconcile_execution',confirmed=True)
for entry in initial['scheduler']['queue']:
    if entry.get('recovery_required'):
        previous=rpc('status',run_id=entry['run_id'])
        if previous['status']=='RUNNING':rpc('recover',run_id=entry['run_id'])
        rpc('stop',run_id=entry['run_id'])

rid=prepare('Crash-A-'+str(int(time.time())),[
    {'id':'wait','model':'general','prompt':'Use terminal to run sleep 90 and wait for completion. Then return the word WAITED as the result note.'}],SMALL,['terminal'])
queued=prepare('Crash-B-'+str(int(time.time())),[
    {'id':'queued','model':'general','prompt':'The complete text deliverable is QUEUED. Put QUEUED in the result note.'}],SMALL)
rpc('set_scheduler',mode='round_robin')
rpc('start',run_id=rid);rpc('start',run_id=queued)
for _ in range(90):
    ledger=rpc('ledger',run_id=rid)['ledger']
    attempts=(ledger or {}).get('cartridges',{}).get('wait',{}).get('attempts',[])
    if attempts and attempts[-1].get('visible_evidence'):break
    time.sleep(1)
else:raise TimeoutError('Crash fixture never reached a real tool call')
assert rpc('status',run_id=rid)['active']
assert not rpc('ledger',run_id=queued)['ledger']
root=Path('/opt/data/plugin-data/magazine')
owner=json.loads((root/'engine-owner.json').read_bytes())['pid']
process=psutil.Process(owner)
assert 'daemon.py' in ' '.join(process.cmdline()) and str(root) in process.cmdline()
children=process.children(recursive=True)
known=[{'pid':p.pid,'started':p.create_time()} for p in children]
os.kill(owner,signal.SIGKILL)
# Only the exact disposable engine's captured descendants are eligible cleanup targets.
for child in children:
    try:child.terminate()
    except psutil.NoSuchProcess:pass
_,alive=psutil.wait_procs(children,timeout=3)
for child in alive:
    try:child.kill()
    except psutil.NoSuchProcess:pass
psutil.wait_procs(alive,timeout=3)
for _ in range(60):
    try:
        saved=rpc('runs')
        break
    except (OSError,RuntimeError):time.sleep(.2)
else:raise TimeoutError('Engine did not reconcile')
assert saved['scheduler']['uncertain_execution']['state']=='UNKNOWN',saved['scheduler']
assert any(e['run_id']==queued and e['recovery_required'] for e in saved['scheduler']['queue'])
before=len(rpc('ledger',run_id=rid)['ledger']['cartridges']['wait']['attempts'])
try:rpc('start',run_id=queued)
except RuntimeError as error:assert 'UNKNOWN' in str(error),error
else:raise AssertionError('Unknown admission allowed inference')
time.sleep(3)
assert len(rpc('ledger',run_id=rid)['ledger']['cartridges']['wait']['attempts'])==before
assert not rpc('ledger',run_id=queued)['ledger']
assert any(c['run_id']==rid for c in rpc('chats')['chats'])
rpc('reconcile_execution',confirmed=True)
rpc('recover',run_id=rid)
assert rpc('status',run_id=rid)['status']=='READY'
time.sleep(2)
assert rpc('status',run_id=rid)['status']=='READY'
rpc('stop',run_id=queued)  # Dequeue retained first turn, preserving READY.
rpc('stop',run_id=rid)     # Remove retained recovered turn; no inference.
report={'passed':True,'interrupted_run':rid,'queued_run':queued,'captured_test_descendants':known,
    'unknown_blocks_start':True,'queue_and_chat_retained':True,'automatic_resume':False,
    'explicit_reconciliation_and_recovery':True,'attempts_before_and_after':before}
Path('/workspace/restart-crash-report.json').write_text(json.dumps(report,indent=2))
print('PASS crash UNKNOWN gate, retained queue/chats, explicit reconciliation and no automatic inference')
