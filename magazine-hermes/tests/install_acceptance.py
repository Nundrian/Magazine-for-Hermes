"""Actual install/update/rollback/uninstall in its own disposable Docker volume."""
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile

source=Path('/source')
home=Path('/opt/data')
sentinel=home/'plugin-data/magazine/install-sentinel.json'
sentinel.parent.mkdir(parents=True,exist_ok=True)
sentinel.write_text('{"preserve":true}\n')
db=home/'install-sentinel.db'
with sqlite3.connect(db) as conn:
    conn.execute('CREATE TABLE IF NOT EXISTS test(value TEXT)')
    conn.execute('INSERT INTO test VALUES(?)',('preserve',))

def install(src=source,operation='install',backup=None):
    args=[sys.executable,str(source/'scripts/install.py'),str(src),'--operation',operation]
    if backup:args+=['--backup',backup]
    result=subprocess.run(args,text=True,capture_output=True)
    if result.returncode:raise RuntimeError(result.stderr+result.stdout)
    record=json.loads(result.stdout.strip().splitlines()[-1])
    uid,gid=home.stat().st_uid,home.stat().st_gid
    assert (home/'plugin-data/magazine').stat().st_uid==uid
    if operation!='uninstall':assert (home/'plugins/magazine').stat().st_uid==uid
    assert (home/'plugin-data/magazine-execution.lock').stat().st_uid==uid
    assert sentinel.read_text()=='{"preserve":true}\n'
    with sqlite3.connect(db) as conn:assert conn.execute('SELECT value FROM test').fetchone()[0]=='preserve'
    return record

records=[install()]
assert (home/'plugins/magazine/dashboard/manifest.json').exists()
with tempfile.TemporaryDirectory(prefix='magazine-update-') as temp:
    update=Path(temp)/'package'
    shutil.copytree(source,update,ignore=shutil.ignore_patterns('__pycache__'))
    (update/'UPDATE-PROBE.txt').write_text('Disposable update marker\n')
    updated=install(update);records.append(updated)
    assert (home/'plugins/magazine/UPDATE-PROBE.txt').exists()
    records.append(install(operation='rollback',backup=updated['backup']))
    assert not (home/'plugins/magazine/UPDATE-PROBE.txt').exists()
records.append(install(operation='uninstall'))
assert not (home/'plugins/magazine').exists()
records.append(install())
# Use the actual service UID against the private socket, rather than relying on
# root-only lifecycle checks. This opens empty state and never starts inference.
uid,gid=home.stat().st_uid,home.stat().st_gid
probe="import sys;sys.path.insert(0,'/opt/data/plugins/magazine/dashboard');from plugin_api import exchange;r=exchange({'action':'runs','data':{}});assert r['ok'],r;assert not any(x.get('active') for x in r['result']['runs']);print('PASS native service UID private IPC')"
result=subprocess.run([sys.executable,'-c',probe],capture_output=True,text=True,
    user=uid,group=gid,extra_groups=[])
assert result.returncode==0,result.stdout+result.stderr
for record in records:
    with sqlite3.connect(Path(record['backup'])/'install-sentinel.db') as conn:
        assert conn.execute('SELECT value FROM test').fetchone()[0]=='preserve'
Path('/workspace/install-report.json').write_text(json.dumps({'passed':True,'operations':records,'runtime_service_uid':uid,'runtime_service_ipc':True},indent=2))
print('PASS actual install, update, rollback, uninstall, reinstall; data and online SQLite backups retained')
