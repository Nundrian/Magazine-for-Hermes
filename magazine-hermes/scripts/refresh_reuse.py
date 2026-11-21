"""Refresh copied-file identities without modifying reference checkouts."""
import hashlib
import json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
path=root/'docs/REUSE.json'
value=json.loads(path.read_text())
for row in value['files']:
    raw=(root/row['path']).read_bytes()
    row['current_sha256']=hashlib.sha256(raw).hexdigest()
    row['reuse']='unchanged' if row['current_sha256']==row['source_sha256'] else 'adapted'
path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
print('Refreshed',len(value['files']),'source reuse identities')
