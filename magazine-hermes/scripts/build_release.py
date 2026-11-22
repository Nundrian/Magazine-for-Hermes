"""Reproducible source/plugin ZIPs. No runtime directories are eligible."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]
VERSION='0.1.0-hermes.rc3'
OUT=ROOT.parent/'dist'
OUT.mkdir(exist_ok=True)
excluded={'__pycache__','.git','node_modules','.venv','evidence','runtime','private'}
allowed_dirs={'dashboard','docs','examples','magazine','scripts','tests','vendor'}
allowed_root={'__init__.py','antiloop.py','beta5_helpers.py','compatibility.json','daemon.py','executor.py',
    'handover.py','hermes_dispatch.py','hermes_worker.py','ledger.py','LICENSE','model_selection.py',
    'plugin.yaml','protocol.py','README.md','requirements-test.txt','run_export.py','scheduler.py',
    'service.py','tokens.py','ui_support.py'}
allowed_suffixes={'.py','.md','.json','.yaml','.yml','.mjs','.js','.txt','.ps1'}
files=sorted(p for p in ROOT.rglob('*') if p.is_file() and not p.is_symlink()
    and not any(x in excluded or x.startswith('.') for x in p.relative_to(ROOT).parts)
    and (p.relative_to(ROOT).parts[0] in allowed_dirs or p.relative_to(ROOT).as_posix() in allowed_root)
    and (p.suffix in allowed_suffixes or p.name in ('LICENSE','LICENSE.txt')))
manifest={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
target=OUT/('Magazine-for-Hermes-'+VERSION+'.zip')
with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
    for p in files:
        info=zipfile.ZipInfo('magazine/'+p.relative_to(ROOT).as_posix(),(2026,1,1,0,0,0))
        info.create_system=3;info.external_attr=0o100644<<16;info.compress_type=zipfile.ZIP_DEFLATED
        archive.writestr(info,p.read_bytes())
    info=zipfile.ZipInfo('magazine/SOURCE-SHA256.json',(2026,1,1,0,0,0));info.create_system=3;info.external_attr=0o100644<<16
    archive.writestr(info,json.dumps(manifest,sort_keys=True,indent=2)+'\n')
examples=[]
for folder in sorted((ROOT/'examples').iterdir()):
    if not folder.is_dir():continue
    path=OUT/('Example-'+folder.name+'.zip')
    with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for file in sorted(folder.rglob('*')):
            if file.is_file():
                entry=zipfile.ZipInfo(file.relative_to(folder).as_posix(),(2026,1,1,0,0,0))
                entry.create_system=3;entry.external_attr=0o100644<<16;entry.compress_type=zipfile.ZIP_DEFLATED
                archive.writestr(entry,file.read_bytes())
    examples.append(path)
digest=hashlib.sha256(target.read_bytes()).hexdigest()
(OUT/'SHA256SUMS.txt').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in [target,*examples]))
with zipfile.ZipFile(target) as archive:
    assert archive.testzip() is None
    assert not any(any(part in excluded for part in Path(name).parts) for name in archive.namelist())
print(json.dumps({'archive':str(target.resolve()),'sha256':digest,'source_files':len(files)}))
