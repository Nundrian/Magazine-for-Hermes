"""Three-cartridge display fixture, clearly labelled synthetic; no inference."""
import json
from pathlib import Path
import sys
import uuid
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'vendor')]
import ledger as lg
import tokens

rid=sys.argv[1]
assert len(rid)==12 and all(c in 'abcdef0123456789' for c in rid)
base=Path('/opt/data/plugin-data/magazine/runs/local')/rid
doc=json.loads((base/'magazine.json').read_bytes())
ids=[c['id'] for c in doc['cartridges']]
value=lg.new(rid,ids,'result_file_v1')
(base/'sessions').mkdir(exist_ok=True)
for index,cid in enumerate(ids):
    count=5 if index==0 else (1 if index==1 else 0)
    record=value['cartridges'][cid]
    for n in range(count):
        aid,sid=uuid.uuid4().hex,'fixture-'+uuid.uuid4().hex
        row={'attempt_id':aid,'attempt_number':n+1,'model':'synthetic/ui-fixture','provider':'synthetic',
            'status':'failed','started':'2026-11-21T00:00:00+00:00','finished':'2026-11-21T00:00:02+00:00',
            'code':'SYNTHETIC_TOOL_ERROR','note':'Synthetic display test, not real execution. '+('long visible error '*500),
            'tokens':tokens.unavailable('synthetic_missing'),'session_id':sid,'session_file':'sessions/'+sid+'.jsonl'}
        if index==1:row['tokens']={'available':True,'incomplete':True,'input':12,'output':None,'total':None,'cache_read':None,'cache_write':None}
        record['attempts'].append(row);record['status']='failed'
        messages=[{'type':'session','id':sid,'source':'synthetic display fixture'},
            {'type':'message','id':'u','timestamp':'2026-11-21T00:00:00Z','message':{'role':'user','content':[{'type':'text','text':'Synthetic UI test prompt'}]}},
            {'type':'message','id':'a','timestamp':'2026-11-21T00:00:01Z','message':{'role':'assistant','content':[{'type':'toolCall','id':'tool1','name':'fixture_tool','arguments':{'value':'<script>window.XSS=1</script>'}}]}},
            {'type':'message','id':'t','timestamp':'2026-11-21T00:00:02Z','message':{'role':'toolResult','toolName':'fixture_tool','isError':True,'content':[{'type':'text','text':'Long synthetic error '+('ERROR '*2000)}]}}]
        (base/row['session_file']).write_text(''.join(json.dumps(r)+'\n' for r in messages))
lg.save(base,value)
print('Three-cartridge synthetic display fixture seeded; no inference')
