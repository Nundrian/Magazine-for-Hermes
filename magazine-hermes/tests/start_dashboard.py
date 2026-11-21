"""Isolated acceptance host only; token stays in its private Docker volume."""
import os
from pathlib import Path
import secrets
import sys

sys.path.insert(0, '/opt/hermes')
token = Path('/opt/data/magazine-test-token')
if not token.exists():
    token.write_text(secrets.token_urlsafe(40))
    token.chmod(0o600)
os.environ['HERMES_DASHBOARD_SESSION_TOKEN'] = token.read_text()
os.chdir('/opt/hermes')
from hermes_cli.main import main
sys.argv = ['hermes', 'dashboard', '--host', '0.0.0.0', '--port', '9119', '--no-open']
main()
