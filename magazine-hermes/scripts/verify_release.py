"""Verify source identity, archive safety and repeated-build reproducibility."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import zipfile
root=Path(__file__).resolve().parents[1]
builder=root/'scripts/build_release.py'
one=json.loads(subprocess.check_output([sys.executable,str(builder)],text=True))
two=json.loads(subprocess.check_output([sys.executable,str(builder)],text=True))
assert one['sha256']==two['sha256'],'Repeated builds differ'
archive=Path(two['archive'])
with zipfile.ZipFile(archive) as source:
    assert source.testzip() is None
    names=source.namelist()
    assert len(names)==len(set(names))
    manifest=json.loads(source.read('magazine/SOURCE-SHA256.json'))
    assert len(names)==len(manifest)+1
    dashboard=json.loads(source.read('magazine/dashboard/manifest.json'))
    assert 'dashboard/'+dashboard['entry'] in manifest, 'Native dashboard entry omitted from package'
    for required in ('dashboard/dist/entry.mjs','dashboard/plugin_api.py','hermes_worker.py','vendor/yaml/__init__.py'):
        assert required in manifest,required+' omitted from package'
    for name,digest in manifest.items():
        assert not Path(name).is_absolute() and '..' not in Path(name).parts
        assert not any(p.startswith('.') or p in ('__pycache__','evidence','references','runtime','private','.venv','node_modules') for p in Path(name).parts)
        raw=source.read('magazine/'+name)
        assert hashlib.sha256(raw).hexdigest()==digest
        assert (root/name).read_bytes()==raw
        assert not re.search(rb'(?:sk-[A-Za-z0-9]{24,}|ghp_[A-Za-z0-9]{25,}|github_pat_[A-Za-z0-9_]{30,}|-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----)',raw),name
    reuse=json.loads(source.read('magazine/docs/REUSE.json'))
    for row in reuse['files']:
        assert manifest[row['path']]==row['current_sha256']
report={'passed':True,'archive':archive.name,'sha256':two['sha256'],'source_files':len(manifest),
    'archive_bytes':archive.stat().st_size,'repeated_build_identical':True,
    'source_identity_verified':True,'runtime_and_private_data_excluded':True}
(archive.parent/'release-verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
