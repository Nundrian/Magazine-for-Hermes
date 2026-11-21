"""Real installed-image acceptance. Run only in the disposable test container."""
import base64
import io
import json
from pathlib import Path
import sys
import time
import urllib.request
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'vendor'))
TOKEN = Path('/opt/data/magazine-test-token').read_text()
BASE = 'http://127.0.0.1:9119'
for _ in range(100):
    try:
        if urllib.request.urlopen(BASE+'/api/dashboard/plugins',timeout=2).status==200:break
    except OSError:pass
    time.sleep(.2)
else:raise RuntimeError('Isolated dashboard did not become ready')


def rpc(action, **data):
    request = urllib.request.Request(BASE+'/api/plugins/magazine/rpc',
        json.dumps({'action': action, 'data': data}).encode(),
        headers={'Content-Type': 'application/json', 'X-Hermes-Session-Token': TOKEN})
    with urllib.request.urlopen(request, timeout=120) as response:
        value = json.load(response)
    if not value.get('ok'):
        raise RuntimeError(value)
    return value['result']


def package(name, cartridges, recovery=None):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        manifest = {'schema_version': '1.0', 'name': name, 'cartridges': cartridges,
                    'handover_mode': 'result_file_v1'}
        if recovery:
            manifest['recovery'] = recovery
        import yaml
        archive.writestr('magazine.yaml', yaml.safe_dump(manifest))
    return base64.b64encode(buffer.getvalue()).decode()


def prepare(name, cartridges, model, tools=None, **extras):
    imported = rpc('import', file_name=name+'.zip', file_data_b64=package(name, cartridges, extras.pop('recovery', None)))
    print('IMPORTED', json.dumps(imported), flush=True)
    project = imported.get('workflow_id') or imported.get('project_id')
    preview = rpc('preview', project_id=project)
    result = rpc('prepare', magazine=json.dumps(preview['document']), project_id=project,
                 default_model=model, tool_ids=tools or [], handover_mode='result_file_v1', **extras)
    return result['run_id']


def wait(rid, timeout=900):
    start = time.monotonic()
    previous = None
    while time.monotonic()-start < timeout:
        value = rpc('status', run_id=rid)
        state = (value.get('display_status'), value.get('status'), value.get('current_cartridge'), len(value.get('done') or []))
        if state != previous:
            print('STATUS', rid, state, flush=True)
            previous = state
        if value.get('status') in ('COMPLETED', 'HALTED') and not value.get('active'):
            return value
        time.sleep(2)
    raise TimeoutError(rid)


def basic():
    model = 'custom/hf.co/AtomicChat/Ornith-1.5-35B-A3B-GGUF:Q4_K_M'
    rid = prepare('Hermes-Basic-'+str(int(time.time())), [
        {'id': 'first', 'model': 'general', 'prompt': 'Use write_file to create outputs/hello.txt: one line HELLO MAGAZINE followed by one real line feed character U+000A (decimal 10). The file must be exactly 15 bytes; do not write literal backslash-n characters. Read it back with read_file and check the content. Return the native structured result and required DONE line.',
         'artifacts': {'outputs': ['hello.txt']}, 'retry_safe': True},
        {'id': 'second', 'model': 'general', 'prompt': 'Read inputs/first/hello.txt using read_file. Use write_file to create outputs/verified.txt: one line HELLO MAGAZINE VERIFIED followed by one real line feed character U+000A (decimal 10). The file must be exactly 24 bytes; do not write literal backslash-n characters. Read it back and return the native structured result. Finish with the required DONE line.',
         'artifacts': {'inputs': [{'from': 'first', 'path': 'hello.txt'}], 'outputs': ['verified.txt']}, 'retry_safe': True}],
        model, ['file'])
    print('RUN', rid, flush=True)
    Path('/workspace/basic-run-id').write_text(rid)
    rpc('start', run_id=rid)
    final = wait(rid)
    ledger = rpc('ledger', run_id=rid)
    report = {'scenario': 'A', 'run_id': rid, 'status': final, 'ledger': ledger}
    Path('/workspace/basic-report.json').write_text(json.dumps(report, indent=2))
    assert final['status'] == 'COMPLETED', final
    assert Path('/workspace/magazine-runs',rid,'first/outputs/hello.txt').read_text() == 'HELLO MAGAZINE\n'
    assert Path('/workspace/magazine-runs',rid,'second/outputs/verified.txt').read_text() == 'HELLO MAGAZINE VERIFIED\n'
    attempts = [a for c in ledger['ledger']['cartridges'].values() for a in c['attempts']]
    assert len({a['session_id'] for a in attempts}) == len(attempts)
    print('PASS A/B', rid, flush=True)


if __name__ == '__main__':
    if sys.argv[1:] == ['basic']:
        basic()
    else:
        action = sys.argv[1] if len(sys.argv)>1 else 'runs'
        data = json.loads(sys.argv[2]) if len(sys.argv)>2 else {}
        print(json.dumps(rpc(action, **data), ensure_ascii=False))
