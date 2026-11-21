"""Dashboard-authenticated bridge. All blocking orchestration runs out of process."""
import asyncio
import base64
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.parse import unquote

from fastapi import APIRouter, HTTPException, Request
from plugins.plugin_storage import plugin_data_dir

router = APIRouter()
SOURCE = Path(__file__).resolve().parent.parent


def exchange(value):
    root = plugin_data_dir('magazine')
    if (root/'maintenance').exists():
        return {'ok':False,'code':503,'error':'Magazine update in progress; refresh after installation completes'}
    endpoint = root / 'engine.sock'
    # Starting a daemon only opens state; the dispatcher starts solely on explicit Start.
    def connect():
        s = socket.socket(socket.AF_UNIX)
        s.settimeout(120)
        try:
            s.connect(str(endpoint))
        except Exception:
            s.close()
            raise
        return s
    try:
        stream = connect()
    except (FileNotFoundError, ConnectionRefusedError):
        log = open(root / 'engine.log', 'ab')
        try:
            subprocess.Popen([sys.executable, str(SOURCE / 'daemon.py'), str(root)],
                stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True,
                cwd=str(SOURCE), env={**os.environ,'HERMES_HOME':str(root.parent.parent)})
        finally:
            log.close()
        for _ in range(60):
            time.sleep(.1)
            try:
                stream = connect()
                break
            except (FileNotFoundError, ConnectionRefusedError):
                continue
        else:
            raise RuntimeError('Magazine engine unavailable; inspect plugin-data/magazine/engine.log')
    with stream:
        stream.sendall((json.dumps(value) + '\n').encode())
        with stream.makefile('rb') as reader:
            data = reader.readline(128*1024*1024)
            if not data.endswith(b'\n'):
                raise RuntimeError('Engine response uncertain; check saved state before repeating any action')
            return json.loads(data)


@router.post('/rpc')
async def rpc(request: Request):
    raw = await request.body()
    if len(raw) > 6*1024*1024:
        raise HTTPException(413, 'Request exceeds 6 MiB')
    try:
        return await asyncio.to_thread(exchange, json.loads(raw))
    except (ValueError, OSError, RuntimeError) as exc:
        return {'ok': False, 'error': str(exc)}


@router.post('/upload')
async def upload(request: Request):
    chunks, size = [], 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > 8*1024*1024:
            raise HTTPException(413, 'ZIP exceeds 8 MiB')
        chunks.append(chunk)
    return await asyncio.to_thread(exchange, {'action': 'import', 'data': {
        'file_name': unquote(request.headers.get('X-Magazine-File-Name', 'workflow.zip')),
        'file_data_b64': base64.b64encode(b''.join(chunks)).decode(),
        'project_id': request.query_params.get('project_id', '')}})
