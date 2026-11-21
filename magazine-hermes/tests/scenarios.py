"""Small real-model fixtures: routing, HALT, retries, recovery, scheduling, STOP."""
import json
from pathlib import Path
import sys
import time

from acceptance import prepare, rpc, wait

ORNITH='custom/hf.co/AtomicChat/Ornith-1.5-35B-A3B-GGUF:Q4_K_M'
SMALL='custom/bonsai-2:27b'
REPORT=Path('/workspace/scenarios-report.json')
results=json.loads(REPORT.read_text()) if REPORT.exists() else []


def record(name,rid,assertion):
    status=rpc('status',run_id=rid)
    ledger=rpc('ledger',run_id=rid)
    assertion(status,ledger['ledger'])
    results.append({'scenario':name,'run_id':rid,'status':status,'ledger':ledger})
    REPORT.write_text(json.dumps(results,indent=2))
    print('PASS',name,rid,flush=True)


def complete(status,ledger):
    assert status['status']=='COMPLETED',status


def routing():
    rid=prepare('Routing-'+str(int(time.time())),[
        {'id':'ornith35','model':'general','prompt':'The complete text deliverable for this cartridge is the word FIRST. Put FIRST in the result note.'},
        {'id':'ornith9','model':'general','prompt':'The complete text deliverable for this cartridge is the word SECOND. Put SECOND in the result note.'}],ORNITH,
        cartridge_models={'ornith35':ORNITH,'ornith9':SMALL},cartridge_tools={'ornith35':[],'ornith9':[]})
    rpc('start',run_id=rid);wait(rid)
    def check(status,ledger):
        complete(status,ledger)
        a=ledger['cartridges']['ornith35']['attempts'][-1]
        b=ledger['cartridges']['ornith9']['attempts'][-1]
        assert a['model']==ORNITH and b['model']==SMALL
        assert a['session_id']!=b['session_id']
        assert a['active_tools']==[] and b['active_tools']==[],(a['active_tools'],b['active_tools'])
    record('C exact routing and empty tool selection',rid,check)


def halt():
    rid=prepare('HALT-'+str(int(time.time())),[
        {'id':'halt','model':'general','prompt':'This is the authoritative blocked-task fixture. End your final response with exactly {"status":"HALT","reason":"fixture blocked"}. Do not publish a success.'},
        {'id':'never','model':'general','prompt':'Publish note UNEXPECTED, then DONE.'}],SMALL)
    rpc('start',run_id=rid);wait(rid)
    def check(status,ledger):
        assert status['status']=='HALTED'
        assert len(ledger['cartridges']['halt']['attempts'])==1
        assert ledger['cartridges']['halt']['status']=='halted'
        assert not ledger['cartridges']['never']['attempts']
    record('Authoritative HALT stops downstream',rid,check)


def retry():
    rid=prepare('Retry-'+str(int(time.time())),[
        {'id':'retry','model':'general','prompt':
         'Acceptance fixture. On the initial work attempt: publish note FIRST and the DONE line, leaving the declared output absent. On a repair attempt: create the required file outputs/repaired.txt containing exactly REPAIRED followed by a newline, read it back, publish the checked result and DONE. The attempt kind is supplied in the recovery instructions.',
         'artifacts':{'outputs':['repaired.txt']},'retry_safe':True}],SMALL,['file'])
    rpc('start',run_id=rid);wait(rid)
    def check(status,ledger):
        complete(status,ledger)
        attempts=ledger['cartridges']['retry']['attempts']
        assert 2<=len(attempts)<=5,attempts
        assert attempts[0]['code']=='OUTPUT_MISSING'
        assert len({a['session_id'] for a in attempts})==len(attempts)
        assert Path('/workspace/magazine-runs',rid,'retry/outputs/repaired.txt').read_text()=='REPAIRED\n'
    record('E automatic fresh-session retry',rid,check)


def recovery():
    rid=prepare('Recovery-'+str(int(time.time())),[
        {'id':'predecessor','model':'general','prompt':'The complete text deliverable is PREDECESSOR. Put it in the result note.'},
        {'id':'recover','model':'general','prompt':
         'Use read_file to check whether outputs/operator-ok.txt exists in this cartridge work directory (same directory as the declared output). If it does not exist, end with {"status":"HALT","reason":"waiting for operator flag"}. If it exists, write outputs/recovered.txt containing exactly RECOVERED followed by a newline, read it back, publish the checked result and DONE.',
         'artifacts':{'outputs':['recovered.txt']},'retry_safe':True}],SMALL,['file'])
    rpc('start',run_id=rid);status=wait(rid)
    assert status['status']=='HALTED'
    before=rpc('ledger',run_id=rid)['ledger']
    assert len(before['cartridges']['predecessor']['attempts'])==1
    Path('/workspace/magazine-runs',rid,'recover/outputs/operator-ok.txt').write_text('operator accepted fixture\n')
    rpc('recover',run_id=rid)
    assert rpc('status',run_id=rid)['status']=='READY'
    time.sleep(2)
    assert rpc('status',run_id=rid)['status']=='READY'
    rpc('start',run_id=rid);wait(rid)
    def check(status,ledger):
        complete(status,ledger)
        assert len(ledger['cartridges']['predecessor']['attempts'])==1
        assert len(ledger['cartridges']['recover']['attempts'])==2
        assert Path('/workspace/magazine-runs',rid,'recover/outputs/recovered.txt').read_text()=='RECOVERED\n'
    record('E manual recovery retains verified predecessor',rid,check)


def scheduling(mode):
    rpc('set_scheduler',mode=mode)
    runs=[]
    for project in ('A','B'):
        runs.append(prepare('Schedule-'+mode+'-'+project+'-'+str(int(time.time())),[
            {'id':project+'1','model':'general','prompt':f'Use terminal to run the harmless command sleep 8 and wait for completion. The complete text deliverable is {project}1. Put {project}1 in the result note.'},
            {'id':project+'2','model':'general','prompt':f'The complete text deliverable is {project}2. Put {project}2 in the result note.'}],SMALL,
            cartridge_tools={project+'1':['terminal'],project+'2':[]}))
    rpc('start',run_id=runs[0]);rpc('start',run_id=runs[1])
    for rid in runs:wait(rid)
    spans=[]
    for rid in runs:
        ledger=rpc('ledger',run_id=rid)['ledger']
        for cid,cartridge in ledger['cartridges'].items():
            a=cartridge['attempts'][-1]
            spans.append((a['started'],a['finished'],cid))
        record('H '+mode,rid,complete)
    spans.sort()
    order=[x[2] for x in spans]
    assert order==(['A1','A2','B1','B2'] if mode=='sequential' else ['A1','B1','A2','B2']),order
    assert all(spans[i][1]<=spans[i+1][0] for i in range(len(spans)-1)),spans
    print('ORDER',mode,order,flush=True)


def stop():
    Path('/workspace/live-stop-run-id').unlink(missing_ok=True)
    rid=prepare('STOP-'+str(int(time.time())),[
        {'id':'sleep','model':'general','prompt':'Call terminal with the harmless command sleep 90. Wait for it to finish, then publish note FINISHED and DONE.'},
        {'id':'never','model':'general','prompt':'Publish note UNEXPECTED then DONE.'}],SMALL,['terminal'])
    rpc('start',run_id=rid)
    end=time.monotonic()+90
    while time.monotonic()<end:
        ledger=rpc('ledger',run_id=rid)['ledger']
        attempts=(ledger or {}).get('cartridges',{}).get('sleep',{}).get('attempts',[])
        if attempts and attempts[-1].get('visible_evidence'):
            break
        time.sleep(1)
    Path('/workspace/live-stop-run-id').write_text(rid)
    # Allow the simultaneous browser journey to inspect/switch a live conversation.
    time.sleep(35)
    result=rpc('stop',run_id=rid)
    assert result.get('control',{}).get('termination_status')=='CONFIRMED',result
    time.sleep(3)
    def check(status,ledger):
        assert status['display_status']=='STOPPED',status
        assert not ledger['cartridges']['never']['attempts']
    record('D STOP confirms termination and prevents dispatch',rid,check)


def timeout():
    rid=prepare('Timeout-'+str(int(time.time())),[
        {'id':'wait','model':'general','prompt':'Use terminal to run sleep 120. Wait for completion, then put FINISHED in the result note.'},
        {'id':'never','model':'general','prompt':'The complete deliverable is NEVER.'}],SMALL,['terminal'],
        recovery={'max_attempts':1,'attempt_seconds':40})
    rpc('start',run_id=rid);wait(rid)
    def check(status,ledger):
        assert status['status']=='HALTED',status
        attempt=ledger['cartridges']['wait']['attempts'][0]
        assert len(ledger['cartridges']['wait']['attempts'])==1
        assert attempt['timeout_seconds']==40
        assert 'ATTEMPT_TIMEOUT' in json.dumps(attempt),attempt
        assert attempt.get('visible_evidence'), 'No actual native terminal call observed'
        assert not ledger['cartridges']['never']['attempts']
    record('Per-attempt timeout terminates real native tool and stops downstream',rid,check)


def antiloop():
    missing='/workspace/magazine-missing-fixture-'+str(time.time_ns())+'.txt'
    assert not Path(missing).exists()
    rid=prepare('Antiloop-'+str(int(time.time())),[
        {'id':'repeat','model':'general','prompt':
         'This harmless read-only diagnostic deliberately checks a missing file. Use read_file on '+missing+
         ' six separate times with exactly the same arguments, one call per round. The expected missing-file errors are diagnostic results. Keep the path unchanged and do not create the file. After the sixth call, return HALT with reason fixture finished.'},
        {'id':'never','model':'general','prompt':'The deliverable is NEVER.'}],SMALL,['file'],
        recovery={'max_attempts':1,'attempt_seconds':180})
    rpc('start',run_id=rid);wait(rid)
    def check(status,ledger):
        assert status['status']=='HALTED',status
        attempts=ledger['cartridges']['repeat']['attempts']
        assert len(attempts)==1
        assert attempts[0]['code']=='LOOP_DETECTED',attempts[0]
        evidence=attempts[0]['loop_evidence']
        assert evidence['reason']=='identical_errors' and (evidence.get('abort_acknowledged') or evidence.get('process_terminated')),evidence
        assert not ledger['cartridges']['never']['attempts']
    record('Antiloop stops repeated actual native tool errors',rid,check)


if __name__=='__main__':
    selected=sys.argv[1:] or ['routing','halt','retry','recovery','sequential','round_robin','stop']
    for item in selected:
        if item in ('sequential','round_robin'):scheduling(item)
        else:globals()[item]()
