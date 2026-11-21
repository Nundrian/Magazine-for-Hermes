"""Real native storage, disposable home; no model inference or user records."""
from pathlib import Path
import sys
import tempfile

sys.path[:0] = [str(Path(__file__).resolve().parents[1])]
import hermes_worker as worker
from persistence_assembly import open_persistence, profile_scope
from persistence.conversation.sessions import NewSession
from persistence.conversation.messages import NewMessage

assert worker.result_error({'exit_code':7,'error':None})
assert not worker.result_error({'exit_code':0,'error':None})
assert worker.visible_record({'role':'tool','content':'{"exit_code":7,"error":null}'},0)['message']['isError']
base='{"error":"File not found","not_found":true}'
annotated=[base+'\n\n[Tool loop warning: repeated_exact_failure_warning; count='+str(i)+'; read_file failed.]\n\n[hermes note: this is the '+str(i)+'th consecutive identical call to read_file.]' for i in (2,3)]
assert worker.tool_value(annotated[0])==worker.tool_value(annotated[1])==worker.tool_value(base)
assert all(worker.result_error(value) for value in annotated)
assert worker.tool_value(base+'\nUnknown meaningful suffix')==base+'\nUnknown meaningful suffix'

with tempfile.TemporaryDirectory(prefix='magazine-lineage-') as temp:
    store = open_persistence(profile_scope(home=Path(temp)), eager=True)
    try:
        store.sessions.create(NewSession('root', source='cli', model='fixture'))
        store.messages.append('root', NewMessage('user', 'ORIGINAL REQUEST'))
        store.messages.append('root', NewMessage('assistant', 'VISIBLE EARLY RESPONSE', reasoning='PRIVATE REASONING'))
        store.sessions.end('root', 'compression')
        store.sessions.create(NewSession('continued', source='cli', model='fixture', parent_session_id='root'))
        store.messages.append('continued', NewMessage('user', 'NATIVE SUMMARY', compressed_summary=True))
        store.messages.append('continued', NewMessage('assistant', '{"status":"DONE"}'))
        tip, rows = worker.native_rows(store, 'root')
        assert tip == 'continued', tip
        text = [r.get('content') for r in rows]
        assert 'ORIGINAL REQUEST' in text and 'VISIBLE EARLY RESPONSE' in text and '{"status":"DONE"}' in text, text
        visible = [worker.visible_record(row, i) for i, row in enumerate(rows)]
        assert 'PRIVATE REASONING' not in str(visible)
        tip, final = worker.native_rows(store, 'root', display=False)
        assert tip == 'continued' and final[-1]['content'] == '{"status":"DONE"}'
        assert not any(r.get('content') == 'ORIGINAL REQUEST' for r in final)
    finally:
        store.close()
worker.WIRE.write('PASS native compression lineage, authoritative tip final and private reasoning exclusion\n')
