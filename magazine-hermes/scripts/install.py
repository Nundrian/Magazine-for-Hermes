"""Run inside the target container after copying the package to a staging directory."""
import argparse
import atexit
import copy
import fcntl
import psutil
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import sqlite3
import sys
import time

sys.path.insert(0,'/opt/hermes')
parser=argparse.ArgumentParser()
parser.add_argument('source',type=Path)
parser.add_argument('--operation',choices=['install','uninstall','rollback'],default='install')
parser.add_argument('--backup',type=Path)
args=parser.parse_args()
from hermes_constants import get_hermes_home, get_default_hermes_root
from hermes_cli.config import load_config,save_config
home=get_hermes_home()
target=home/'plugins/magazine'
data=home/'plugin-data/magazine'
if args.operation=='rollback':
    if not args.backup or args.backup.parent != home/'backups/magazine':
        raise SystemExit('Use an exact Magazine backup directory under this Hermes home')
    args.source=args.backup/'plugin'
    if not args.source.is_dir():raise SystemExit('Backup has no previous plugin; use uninstall')
    args.operation='install'

data.mkdir(parents=True,exist_ok=True,mode=0o700)
runtime_owner=home.stat()

def runtime_permissions():
    # Docker exec runs as root; the supervised Hermes dashboard runs as the
    # volume's owner. Transfer only Magazine-managed code/state, never the home
    # recursively or unrelated plugin data. Preserve existing permission modes.
    if os.geteuid()!=0:return
    for parent in (data.parent,target.parent):
        if parent.exists() and not parent.is_symlink() and parent.stat().st_uid==0:
            os.chown(parent,runtime_owner.st_uid,runtime_owner.st_gid)
    for base in (data,target):
        if base.is_symlink():raise RuntimeError('Refusing linked Magazine installation/state root')
        if not base.exists():continue
        for path in [base,*base.rglob('*')]:
            if not path.is_symlink():os.chown(path,runtime_owner.st_uid,runtime_owner.st_gid,follow_symlinks=False)

atexit.register(runtime_permissions)
target.parent.mkdir(parents=True,exist_ok=True)
# Precreate the global gate for the runtime user without changing its identity.
gate_root=get_default_hermes_root()
gate_parent=gate_root/'plugin-data'
gate_parent.mkdir(parents=True,exist_ok=True)
gate_fd=os.open(gate_parent/'magazine-execution.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
try:
    if os.geteuid()==0:
        gate_owner=gate_root.stat()
        os.fchown(gate_fd,gate_owner.st_uid,gate_owner.st_gid)
finally:os.close(gate_fd)
maintenance=data/'maintenance'
if maintenance.exists():
    if maintenance.is_symlink():raise SystemExit('Unsafe maintenance marker')
    try:previous=json.loads(maintenance.read_text())
    except ValueError:raise SystemExit('Unrecognised maintenance marker; inspect previous installation before retrying')
    try:
        process=psutil.Process(previous['pid'])
        if process.create_time()==previous['started']:
            raise SystemExit('Another Magazine installation is active')
    except psutil.NoSuchProcess:pass
    maintenance.rename(data/('maintenance-stale-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')))
with open(maintenance,'x') as stream:json.dump({'pid':os.getpid(),'started':psutil.Process().create_time()},stream)
atexit.register(lambda: maintenance.unlink(missing_ok=True))

# Refuse updates with an active or uncertain owner; never replace live code.
if (data/'engine.sock').exists():
    with socket.socket(socket.AF_UNIX) as sock:
        sock.settimeout(30);sock.connect(str(data/'engine.sock'))
        sock.sendall(b'{"action":"runs","data":{}}\n')
        with sock.makefile('rb') as stream:status=json.loads(stream.readline())
    if not status.get('ok'):raise SystemExit('Cannot establish Magazine inactivity; update refused')
    runs=status['result']['runs']
    if any(r.get('active') or r.get('display_status') in ('RUNNING','QUEUED','STOP_REQUESTED') for r in runs):
        raise SystemExit('Magazine is active or queued. Reach an idle checkpoint before updating.')
if (data/'uncertain-execution.json').exists():raise SystemExit('Reconcile uncertain Magazine execution before updating')

stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
backup=home/'backups/magazine'/stamp
backup.mkdir(parents=True,mode=0o700)
if (home/'config.yaml').is_file():shutil.copy2(home/'config.yaml',backup/'config.yaml')
if target.exists():shutil.copytree(target,backup/'plugin',ignore=shutil.ignore_patterns('__pycache__'))
# Native session storage is shared with Hermes; SQLite online backup is consistent.
for path in home.glob('*.db'):
    with sqlite3.connect(str(path)) as source,sqlite3.connect(str(backup/path.name)) as dest:
        source.backup(dest)
if data.exists():
    owner=data/'engine-owner.json'
    if owner.exists():
        pid=json.loads(owner.read_bytes()).get('pid')
        try:
            process=psutil.Process(pid)
            command=process.cmdline()
            if str(target/'daemon.py') in command and str(data) in command:
                process.terminate()
        except psutil.NoSuchProcess:pass
        for _ in range(100):
            if not (data/'engine.sock').exists():break
            time.sleep(.1)
        else:raise SystemExit('Magazine engine did not stop; update refused')
    owner_gate=open(data/'owner.lock','a+b')
    try:fcntl.flock(owner_gate,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:raise SystemExit('Magazine owner or worker still holds ownership; update refused')
    atexit.register(owner_gate.close)
    shutil.copytree(data,backup/'plugin-data',ignore=shutil.ignore_patterns('*.sock','*.lock'))

config=load_config()
original_config=copy.deepcopy(config)
plugins=config.setdefault('plugins',{})
enabled=list(plugins.get('enabled') or [])
disabled=list(plugins.get('disabled') or [])
if args.operation=='uninstall':
    if target.exists():target.rename(backup/'removed-plugin')
    plugins['enabled']=[x for x in enabled if x!='magazine']
    if 'magazine' not in disabled:disabled.append('magazine')
    plugins['disabled']=disabled
else:
    # Verify current installed identity before changing anything.
    sys.path[:0]=[str(args.source),str(args.source/'vendor')]
    from hermes_cli.version_info import get_code_identity
    identity=get_code_identity()
    supported=json.loads((args.source/'compatibility.json').read_bytes())['verified']
    if not any(identity.get('version')==r['version'] and identity.get('sha')==r['sha'] for r in supported):
        raise SystemExit('This Hermes build is not in the verified compatibility table')
    staged=target.with_name('.magazine-install-'+stamp)
    shutil.copytree(args.source,staged,ignore=shutil.ignore_patterns('__pycache__','*.pyc','evidence','dist-release'))
    if target.exists():target.rename(backup/'previous-installed-plugin')
    staged.rename(target)
    if 'magazine' not in enabled:enabled.append('magazine')
    plugins['enabled']=enabled
    plugins['disabled']=[x for x in disabled if x!='magazine']
save_config(config)
verified=load_config()
if {k:v for k,v in verified.items() if k!='plugins'} != {k:v for k,v in original_config.items() if k!='plugins'}:
    if (backup/'config.yaml').exists():shutil.copy2(backup/'config.yaml',home/'config.yaml')
    raise SystemExit('Unexpected non-plugin configuration change; configuration restored from backup')
runtime_permissions()
print(json.dumps({'operation':args.operation,'plugin':str(target),'data_preserved':str(data),'backup':str(backup),'non_plugin_configuration_preserved':True,
                  'runtime_uid':runtime_owner.st_uid,'runtime_gid':runtime_owner.st_gid}))
