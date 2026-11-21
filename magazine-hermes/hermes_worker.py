"""One attempt per process, using Hermes' documented Python embedding API.

Only visible native transcript fields are projected to the Magazine viewer.
Credentials are resolved by Hermes in this process and never cross IPC.
"""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import signal
import re
import sys
import threading
import time
import uuid

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / 'vendor'))
# Installed image exposes the source here; no source files are modified.
sys.path.insert(0, os.environ.get('MAGAZINE_HERMES_SOURCE', '/opt/hermes'))
from magazine.durability import atomic_write
from run_export import redact

WIRE = sys.stdout
sys.stdout = sys.stderr  # Hermes diagnostics must not corrupt the private IPC.
SEND_LOCK = threading.Lock()
SECRETS = []


def send(value):
    with SEND_LOCK:
        WIRE.write(json.dumps(redact(value, SECRETS), ensure_ascii=False, default=str) + '\n')
        WIRE.flush()


def stamp():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def compatibility():
    from hermes_cli.version_info import get_code_identity
    import inspect
    from run_agent import AIAgent
    info = get_code_identity()
    table = json.loads((HERE/'compatibility.json').read_text())
    if not any(info.get('version')==row['version'] and info.get('sha')==row['sha'] for row in table['verified']):
        raise ValueError('Unverified Hermes build; run compatibility acceptance before enabling Magazine: '+str(info.get('version'))+' '+str(info.get('sha')))
    required = {'session_id','persistence','enabled_toolsets','fallback_model','cwd','tool_start_callback','tool_complete_callback'}
    if not required <= set(inspect.signature(AIAgent).parameters):
        raise ValueError('Installed Hermes lacks required embedding controls')
    return info


def catalogue():
    from hermes_cli.inventory import build_model_options_payload, load_picker_context
    from hermes_cli.runtime_provider import resolve_runtime_provider
    from model_tools import get_tool_definitions, get_available_toolsets
    from hermes_cli.plugins import discover_plugins
    discover_plugins()
    context = load_picker_context()
    inventory = build_model_options_payload(context)
    models = {}
    for provider in inventory.get('providers', []):
        pid = provider.get('id') or provider.get('provider') or provider.get('slug')
        if not pid:
            continue
        for row in provider.get('models', []):
            mid = row if isinstance(row, str) else row.get('id') or row.get('model')
            if mid:
                models[pid + '/' + mid] = {'id': pid + '/' + mid, 'name': mid, 'provider': pid, 'model_id': mid}
    # The configured compatible endpoint is authoritative for exact local names.
    if context.current_provider.startswith('custom'):
        from openai import OpenAI
        runtime = resolve_runtime_provider(requested=context.current_provider, target_model=context.current_model)
        client = OpenAI(base_url=runtime['base_url'], api_key=runtime.get('api_key') or 'local', timeout=15)
        rows = list(client.models.list())
        client.close()
        pid = context.current_provider
        # Avoid stale picker entries masquerading as available local models.
        models = {k: v for k, v in models.items() if v['provider'] != pid}
        for row in rows:
            models[pid + '/' + row.id] = {'id': pid + '/' + row.id, 'name': row.id, 'provider': pid, 'model_id': row.id}
    if context.current_provider == 'custom':
        models = {k:v for k,v in models.items() if not v['provider'].startswith('custom:')}
    tools = []
    for toolset in get_available_toolsets():
        if toolset.startswith('magazine'):
            continue
        defs = get_tool_definitions(enabled_toolsets=[toolset], quiet_mode=True, skip_tool_search_assembly=True)
        names = sorted(d['function']['name'] for d in defs)
        if names:
            tools.append({'id': toolset, 'name': toolset + ' (Hermes toolset)', 'description': ', '.join(names), 'functions': names})
    return {'models': list(models.values()), 'tools': tools, 'provider': context.current_provider,
            'compatibility': compatibility(), 'tool_selection': 'Hermes toolsets; expanded function set verified before inference'}


def native_publisher(publish, session_id, native_source=None):
    import handover as ho

    def handler(args, **kwargs):
        try:
            if args.get('payload_json') is not None:
                payload = ho.strict_json(args['payload_json'])
            else:
                payload = {'result': {'step': publish['cartridgeId'], 'verified': args.get('verified') is True,
                           'files': args.get('files', []), 'checks': args.get('checks', []), 'note': args.get('note', '')}}
            if not isinstance(payload, dict):
                raise ValueError('payload must be an object')
            document = {'run_id': publish['runId'], 'cartridge_id': publish['cartridgeId'],
                        'attempt_id': publish['attemptId'], 'session_id': session_id,
                        'schema': 'magazine.result.v1', 'payload': payload}
            raw = (json.dumps(document, ensure_ascii=False, allow_nan=False) + '\n').encode()
            if len(raw) > 1024 * 1024:
                raise ValueError('Result exceeds 1 MiB')
            target = Path(publish['resultPath'])
            with ho.open_plain(target.parent.parent, 'attempt.json') as handle:
                identity = json.load(handle)
            if any(identity.get(k) != document[k] for k in ('run_id', 'cartridge_id', 'attempt_id')):
                raise ValueError('Attempt identity mismatch')
            # Anchored O_NOFOLLOW traversal and atomic, fsynced read-back publication.
            receipt = ho.durable_bytes(target, raw)
            back, info = ho.read_result_file(target.parent.parent)
            if back != document or info['sha256'] != receipt['sha256']:
                raise ValueError('Publication read-back mismatch')
            send({'event': 'published', 'receiptId':uuid.uuid4().hex,'publisher':'hermes-native-final-v1',
                  'nativeSessionId':session_id,'nativeSource':dict(native_source or {}), **info})
            return json.dumps({'published': True, **info})
        except Exception as exc:
            return json.dumps({'error': str(exc)})

    return handler


def tool_value(value):
    """Canonical structured result without Hermes' changing loop-count suffix.

    Full original text stays in Chats. Unknown suffixes stay opaque.
    """
    if isinstance(value, str):
        try:
            text=value.lstrip()
            decoded,end=json.JSONDecoder().raw_decode(text)
        except ValueError:return value
        tail=text[end:]
        if not tail.strip() or re.fullmatch(
            r'(?:\s*\[(?:Tool loop (?:warning|hard stop):|hermes note: (?:this is the|this result is byte-identical to|the last))[^\]]*\])+\s*',tail):
            return decoded
    return value


def result_error(value):
    value=tool_value(value)
    return isinstance(value, dict) and bool(value.get('error') or value.get('isError') or
        (type(value.get('exit_code')) is int and value['exit_code']!=0))


def visible_record(row, index):
    role = row.get('role')
    if role not in ('user', 'assistant', 'tool') or row.get('display_kind') in ('reasoning', 'thinking'):
        return None
    content = row.get('content')
    is_error = bool(row.get('is_error'))
    if role == 'tool':
        is_error = is_error or result_error(content)
    blocks = []
    if role == 'assistant' and isinstance(content,str):
        content = re.sub(r'<think\b[^>]*>[\s\S]*?(?:</think\s*>|$)','',content,flags=re.I)
    if isinstance(content, str) and content:
        blocks.append({'type': 'text', 'text': content})
    elif isinstance(content, list):
        blocks.extend({'type': 'text', 'text': re.sub(r'<think\b[^>]*>[\s\S]*?(?:</think\s*>|$)','',p.get('text',''),flags=re.I) if role=='assistant' else p.get('text','')} for p in content
                      if isinstance(p, dict) and p.get('type') in ('text', 'output_text'))
    for call in row.get('tool_calls') or []:
        fn = call.get('function', {})
        args = fn.get('arguments', '{}')
        try:
            args = json.loads(args) if isinstance(args, str) else args
        except ValueError:
            pass
        blocks.append({'type': 'toolCall', 'id': call.get('id'), 'name': fn.get('name'), 'arguments': args})
    return {'type': 'message', 'id': str(row.get('id', index)), 'timestamp': row.get('timestamp') or stamp(),
            'message': {'role': 'toolResult' if role == 'tool' else role, 'content': blocks,
                        'toolName': row.get('name'), 'toolCallId': row.get('tool_call_id'),
                        'isError': is_error}}


def native_rows(store, root_session_id, *, display=True):
    """Read supported native compression lineage, retaining the root attempt identity."""
    from persistence.conversation.messages import TranscriptRead, TranscriptView
    tip = store.lineage.tip(root_session_id)
    request = TranscriptRead(view=TranscriptView.DISPLAY if display else TranscriptView.ACTIVE,
                             include_lineage=display)
    return tip, [row.as_wire_row() for row in store.messages.read_transcript(tip, request)]


def run(request):
    compatibility()
    from run_agent import AIAgent
    from persistence_assembly import open_persistence, profile_scope
    from hermes_cli.runtime_provider import resolve_runtime_provider
    from model_tools import get_tool_definitions
    from hermes_cli.env_loader import load_hermes_dotenv
    from hermes_constants import get_hermes_home
    load_hermes_dotenv()
    provider, model = request['model'].split('/', 1)
    if request.get('publish'):
        run_root = Path(request['cwd']) / 'magazine-runs' / request['publish']['runId']
        run_root.mkdir(parents=True, exist_ok=True)
        os.environ['HERMES_WRITE_SAFE_ROOT'] = str(run_root)
    runtime = resolve_runtime_provider(requested=provider, target_model=model)
    SECRETS.extend(v for k,v in os.environ.items() if len(v)>6 and any(t in k.upper() for t in ('KEY','TOKEN','PASSWORD','SECRET')))
    if runtime.get('api_key') and len(runtime['api_key'])>6:
        SECRETS.append(runtime['api_key'])
    if not runtime or not runtime.get('provider'):
        raise ValueError('Provider unavailable')
    sid = 'magazine-' + uuid.uuid4().hex
    folder = Path(request['sessionDir'])
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (sid + '.jsonl')
    # admission mapping persisted before any inference; each attempt is a new native session.
    header = {'type': 'session', 'id': sid, 'timestamp': stamp(), 'source': 'hermes-native-session-db',
              'provider': provider, 'model': model}
    atomic_write(str(path), (json.dumps(header) + '\n').encode())
    native_source = {}
    publisher = native_publisher(request['publish'],sid,native_source=native_source) if request.get('publish') else None
    toolsets = list(request.get('tools', []))
    expected = {d['function']['name'] for d in get_tool_definitions(enabled_toolsets=toolsets, quiet_mode=True)}
    underlying = {d['function']['name'] for d in get_tool_definitions(enabled_toolsets=toolsets, quiet_mode=True,skip_tool_search_assembly=True)}
    if 'expectedToolFunctions' in request and underlying != set(request['expectedToolFunctions']):
        raise ValueError('Prepared tool function allowlist changed; prepare a new run')
    store = open_persistence(profile_scope(), eager=True)
    if store.sessions.get(sid) is not None:
        raise ValueError('Worker context was not fresh')
    row_times = {}
    callbacks = []
    messages_lock = threading.RLock()
    last_records = []
    stream_text = ['']
    done = threading.Event()

    def refresh(final_usage=None):
        nonlocal last_records
        with messages_lock:
            if done.is_set() and final_usage is None:
                return
            _, rows = native_rows(store, sid)
            names = {c.get('id'): c.get('function',{}).get('name') for r in rows for c in (r.get('tool_calls') or [])}
            records = []
            for index, row in enumerate(rows):
                key = row.get('id', index)
                row_times.setdefault(key, row.get('timestamp') or stamp())
                record = visible_record(dict(row, timestamp=row_times[key], name=row.get('name') or names.get(row.get('tool_call_id'))), index)
                if record:
                    records.append(record)
            if final_usage is not None:
                # Hermes exposes reported cumulative counters, not reliable per-round usage here.
                # Store once on the last assistant record, with its coverage stated explicitly.
                assistants = [r for r in records if r['message']['role'] == 'assistant']
                if assistants:
                    assistants[-1]['message']['usage'] = final_usage
                    assistants[-1]['message']['usage_scope'] = 'native_session_cumulative'
            last_records = records
            # Callbacks retain live tool output even before Hermes flushes its DB.
            known = {r['message'].get('toolCallId') for r in records if r['message']['role'] == 'toolResult'}
            extra = [r for r in callbacks if r['message'].get('toolCallId') not in known]
            if stream_text[0] and not done.is_set():
                extra.append({'type':'message','id':'live-stream','timestamp':stamp(),'message':{'role':'assistant','content':[{'type':'text','text':re.sub(r'<think\b[^>]*>[\s\S]*?(?:</think\s*>|$)','',stream_text[0],flags=re.I)}]}})
            raw = ''.join(json.dumps(redact(r, SECRETS), ensure_ascii=False, default=str) + '\n' for r in [header, *records, *extra])
            atomic_write(str(path), raw.encode())

    def on_start(call_id, name, args):
        with messages_lock:
            callbacks.append({'type': 'message', 'id': call_id + '-start', 'timestamp': stamp(),
                'message': {'role': 'assistant', 'toolCallId': call_id, 'content': [
                    {'type': 'toolCall', 'id': call_id, 'name': name, 'arguments': args}]}})
        send({'event': 'assistant', 'toolCalls': [{'id': call_id, 'name': name, 'argsSha256': digest(args)}]})
        refresh()

    def on_complete(call_id, name, args, result):
        text = result if isinstance(result, str) else json.dumps(result, default=str)
        error = result_error(text)
        with messages_lock:
            callbacks.append({'type': 'message', 'id': call_id + '-result', 'timestamp': stamp(),
                'message': {'role': 'toolResult', 'toolName': name, 'toolCallId': call_id, 'isError': error,
                            'content': [{'type': 'text', 'text': text}]}})
        send({'event': 'tool_result', 'toolCallId': call_id, 'toolName': name,
              'resultSha256': digest(tool_value(result)), 'rawResultSha256':digest(result),
              'normalization':'Structured JSON plus recognised Hermes loop annotations only',
              'isError': error, 'noChange': False})
        refresh()

    def on_delta(text):
        if text is None:
            stream_text[0]=''
        elif isinstance(text,str):
            stream_text[0]+=text

    agent = AIAgent(model=model, provider=runtime['provider'], requested_provider=provider,
        api_key=runtime.get('api_key'), base_url=runtime.get('base_url'), api_mode=runtime.get('api_mode'),
        enabled_toolsets=toolsets, session_id=sid, persistence=store, fallback_model={},
        skip_memory=True, skip_context_files=True, load_soul_identity=False, skip_background_review=True,
        quiet_mode=True, ephemeral_system_prompt='Complete one bounded Magazine cartridge using the available tools when needed. Return the actual requested deliverable in the specified result format. If a required action cannot be performed, return HALT. Code blocks alone do not execute tools.', stream_delta_callback=on_delta, cwd=request['cwd'], tool_start_callback=on_start, tool_complete_callback=on_complete,
        clarify_callback=lambda *a, **k: 'HALT: This bounded worker requires operator clarification.')
    if agent.model != model or set(agent.valid_tool_names) != expected:
        raise ValueError('Exact model/toolset isolation verification failed')
    send({'event': 'session', 'id': sid, 'file': str(path), 'sdkVersion': 'Hermes AIAgent',
          'activeTools': sorted(agent.valid_tool_names), 'provider': provider, 'model': model})

    def controls():
        for line in sys.stdin:
            try:
                if json.loads(line).get('action') == 'abort':
                    agent.interrupt()
                    return
            except ValueError:
                continue

    threading.Thread(target=controls, daemon=True).start()

    def mirror():
        while not done.wait(.5):
            try:
                refresh()
            except Exception:
                pass

    threading.Thread(target=mirror, daemon=True).start()
    send({'event': 'streaming'})
    try:
        result = agent.run_conversation(request['prompt'], conversation_history=[])
        done.set()
        usage = {'input': getattr(agent, 'session_prompt_tokens', None),
                 'output': getattr(agent, 'session_completion_tokens', None)}
        usage['totalTokens'] = getattr(agent, 'session_total_tokens', None)
        usage['reported'] = isinstance(getattr(agent,'_last_turn_usage',None),dict)
        usage['coverage_complete'] = False  # Native cumulative counters do not expose per-call missingness here.
        refresh(usage)
        text = result.get('final_response') or ''
        finish = 'stop' if result.get('completed') is True and not result.get('interrupted') and not result.get('partial') else 'error'
        if finish == 'stop' and publisher:
            # This is publication of a strict structured native final record, never proof of a tool call.
            tip, native_messages = native_rows(store, sid, display=False)
            native = [r for r in native_messages if r.get('role')=='assistant']
            if not native or native[-1].get('tool_calls'):
                raise ValueError('Saved native session has no authoritative final assistant response')
            native_content = native[-1].get('content')
            if isinstance(native_content,str):
                text = native_content
            elif isinstance(native_content,list):
                text = ''.join(p.get('text','') for p in native_content if p.get('type') in ('text','output_text'))
            else:
                raise ValueError('Saved native final response is unavailable')
            native_source.update(session_id=tip,message_id=native[-1].get('id'),final_sha256=hashlib.sha256(text.encode()).hexdigest())
            from protocol import native_result_payload
            payload = native_result_payload(text)
            if payload is not None:
                receipt = json.loads(publisher({'payload_json':json.dumps(payload,allow_nan=False)}))
                if receipt.get('error'):
                    send({'event':'publication_error','error':receipt['error']})
        if agent.model != model or agent.provider != runtime['provider']:
            raise ValueError('Model/provider identity changed during execution')
        outcome = {'event': 'result', 'ok': True, 'result': {'model': request['model'], 'text': text,
              'finish': finish, 'errorMessage': result.get('error') or result.get('turn_exit_reason'),
              'sessionId': sid, 'sessionFile': str(path), 'nativeSessionId': sid,
              'provider': provider, 'reported_usage': usage}}
    finally:
        done.set()
        agent.close()
        from tools.terminal_tool import cleanup_all_environments
        cleanup_all_environments()
        import psutil
        descendants = psutil.Process().children(recursive=True)
        for child in descendants:
            try:child.terminate()
            except psutil.NoSuchProcess:pass
        _, alive = psutil.wait_procs(descendants,timeout=3)
        for child in alive:
            try:child.kill()
            except psutil.NoSuchProcess:pass
        _, alive = psutil.wait_procs(alive,timeout=3)
        if any(p.status()!=psutil.STATUS_ZOMBIE for p in alive):
            raise RuntimeError('Worker-owned subprocess termination uncertain')
        store.close()
    send(outcome)


if __name__ == '__main__':
    try:
        # Worker dies if its engine disappears; restart admission still fails closed.
        parent = os.getppid()
        ctypes.CDLL(None).prctl(1, signal.SIGKILL)
        if os.getppid() != parent:
            raise RuntimeError('Engine disappeared before worker admission')
        req = json.loads(sys.stdin.readline())
        if req.get('action') == 'catalogue':
            from hermes_cli.env_loader import load_hermes_dotenv
            from hermes_constants import get_hermes_home
            load_hermes_dotenv()
            send({'event': 'result', 'ok': True, 'result': catalogue()})
        else:
            run(req)
    except BaseException as exc:
        send({'event': 'result', 'ok': False, 'error': type(exc).__name__ + ': ' + str(exc)})
        sys.exit(1)
