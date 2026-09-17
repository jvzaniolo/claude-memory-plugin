#!/usr/bin/env python3
"""Workers isolados; validação e aplicação das mudanças pertencem ao processo local."""
import argparse
import contextlib
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parent.parent


def state_dir():
    return Path(os.environ.get('MEM_STATE_DIR', str(Path.home() / '.claude'))).resolve()


def memory_store():
    if os.environ.get('MEM_STORE'):
        return Path(os.environ['MEM_STORE']).expanduser().resolve(strict=True)
    config = json.loads((Path.home() / '.claude/settings.json').read_text())
    return Path(config['autoMemoryDirectory']).expanduser().resolve(strict=True)


def atomic_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.' + path.name + '-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def save_json(path, data):
    atomic_write(path, json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def read_json(path, default):
    return json.loads(path.read_text()) if path.exists() else default


def log(mode, message):
    name = 'memory-worker.log' if mode == 'checkpoint' else 'memory-consolidate.log'
    path = state_dir() / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as stream:
        stream.write(f'[{datetime.datetime.now():%F %T}] {message}\n')


@contextlib.contextmanager
def store_lock(store):
    directory = state_dir() / 'memory-locks'
    directory.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(str(store.resolve()).encode()).hexdigest()
    # Não remover o arquivo: outro processo pode estar esperando no mesmo inode.
    with (directory / (key + '.lock')).open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def snapshot(store):
    result = {}
    for path in store.rglob('*'):
        if path.is_symlink():
            raise ValueError(f'store contém link simbólico: {path.name}')
        if path.is_file() and (path.suffix == '.md' or path.name == '.memory-usage.json'):
            result[path.relative_to(store).as_posix()] = path.read_bytes()
    if 'MEMORY.md' not in result:
        raise ValueError('store sem MEMORY.md')
    return result


def stage_files(store, data):
    for name, content in data.items():
        path = store / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)


def frontmatter_field(data, field):
    text = data.decode() if isinstance(data, bytes) else data
    if not text.startswith('---\n'):
        return None
    header = text.split('---', 2)[1]
    match = re.search(r'^\s*' + re.escape(field) + r':\s*(.+?)\s*$', header, re.M)
    return match[1].strip().strip('"') if match else None


def report_schema(mode):
    if mode == 'checkpoint':
        properties = {'completed': {'type': 'boolean'},
                      'used_memories': {'type': 'array', 'items': {'type': 'string'}, 'uniqueItems': True}}
    else:
        properties = {'results': {'type': 'array', 'items': {
            'type': 'object', 'additionalProperties': False,
            'properties': {'file': {'type': 'string'},
                           'status': {'enum': ['consolidated', 'already_summarized', 'skipped']}},
            'required': ['file', 'status']}}}
    return {'type': 'object', 'properties': properties, 'required': list(properties),
            'additionalProperties': False}


def claude_command(work, mode, writable, prompt_file):
    settings = {'disableAllHooks': True, 'autoMemoryEnabled': False,
                'permissions': {'allow': ['Read', 'Glob', 'Grep'] + [
                    f'Edit(/{work / name})' for name in writable]}}
    # --restricted confina os arquivos; --safe-mode preserva autenticação sem customizações.
    return ['claude', '-p', '--safe-mode', '--restricted', '--strict-mcp-config',
            '--mcp-config', '{"mcpServers":{}}', '--no-session-persistence',
            '--tools', 'Read,Write,Edit,Glob,Grep', '--permission-mode', 'dontAsk',
            '--settings', json.dumps(settings), '--model', 'sonnet',
            '--system-prompt-file', str(prompt_file), '--output-format', 'json',
            '--json-schema', json.dumps(report_schema(mode))]


def model_run(work, mode, writable, prompt, request):
    prompt_file = work.parent / 'system-prompt.txt'
    prompt_file.write_text(prompt)
    env = dict(os.environ, CLAUDE_MEMORY_WORKER='1')
    env.pop('CLAUDECODE', None)
    env.pop('CLAUDE_PROJECT_DIR', None)
    output = subprocess.run(claude_command(work, mode, writable, prompt_file),
                            input=request, text=True, capture_output=True, cwd=work,
                            env=env, timeout=1800)
    if output.returncode:
        raise ValueError(f'Claude falhou (rc={output.returncode}): {output.stderr[-1000:]} {output.stdout[-1000:]}')
    envelope = json.loads(output.stdout)
    if not isinstance(envelope, dict) or envelope.get('is_error') or envelope.get('subtype') != 'success':
        raise ValueError('Claude não confirmou conclusão bem-sucedida')
    report = envelope.get('structured_output')
    if not isinstance(report, dict):
        raise ValueError('Claude não retornou structured_output')
    return report


def validate_report(report, mode, candidates=None):
    if mode == 'checkpoint':
        used = report.get('used_memories')
        if (set(report) != {'completed', 'used_memories'} or report['completed'] is not True
                or not isinstance(used, list) or any(not isinstance(x, str) for x in used)
                or len(used) != len(set(used))):
            raise ValueError('checkpoint incompleto ou relatório inválido')
        return used
    if set(report) != {'results'} or not isinstance(report['results'], list):
        raise ValueError('relatório de consolidação inválido')
    expected = {c['arquivo'] for c in candidates}
    results = {}
    for row in report['results']:
        if (not isinstance(row, dict) or set(row) != {'file', 'status'}
                or not isinstance(row['file'], str) or row['file'] not in expected
                or row['file'] in results
                or row['status'] not in ['consolidated', 'already_summarized', 'skipped']):
            raise ValueError('resultado desconhecido, duplicado ou inválido')
        results[row['file']] = row['status']
    return results


def validate_changes(work, before, mode, candidates=None, results=None):
    all_files = {}
    for path in work.rglob('*'):
        if path.is_symlink():
            raise ValueError('worker criou um link simbólico')
        if path.is_file():
            all_files[path.relative_to(work).as_posix()] = path.read_bytes()
    if set(before) - set(all_files):
        raise ValueError('worker tentou apagar memória')
    changes = {n: data for n, data in all_files.items() if before.get(n) != data}
    allowed_dossiers = {c['dossie'] for c in candidates or []
                        if results.get(c['arquivo']) == 'consolidated'}
    for name in changes:
        if mode == 'consolidate':
            if name not in allowed_dossiers:
                raise ValueError(f'consolidação alterou arquivo não autorizado: {name}')
        elif (not name.endswith('.md') or name.startswith('.')
              or any(part.startswith('.') for part in Path(name).parts)):
            raise ValueError(f'checkpoint alterou arquivo não autorizado: {name}')
    check = subprocess.run(['bash', str(ROOT / 'scripts/check.sh'), str(work)],
                           text=True, capture_output=True)
    if check.returncode:
        raise ValueError('integridade da cópia falhou:\n' + check.stdout + check.stderr)
    index = all_files['MEMORY.md']
    previous_index = before['MEMORY.md']
    if (len(index.splitlines()) > max(200, len(previous_index.splitlines()))
            or len(index) > max(25600, len(previous_index))):
        raise ValueError('índice excede 200 linhas ou 25 KB')
    return changes


def apply_changes(store, before, changes):
    # Detecta alterações da thread principal/iCloud feitas durante a chamada do modelo.
    if snapshot(store) != before:
        raise ValueError('store mudou durante a execução; nada aplicado, tentar novamente')
    if not changes:
        return
    backup = state_dir() / 'memory-backups' / (datetime.datetime.now().strftime('%Y%m%d-%H%M%S-') + uuid.uuid4().hex[:8])
    backup.mkdir(parents=True)
    for name in changes:
        if name in before:
            copy = backup / name
            copy.parent.mkdir(parents=True, exist_ok=True)
            copy.write_bytes(before[name])
    save_json(backup / 'manifest.json', {'store': str(store), 'changed': list(changes),
                                       'created': [n for n in changes if n not in before]})
    for name, content in changes.items():
        atomic_write(store / name, content.decode())


def record_usage(before, changed, names, session):
    usage = json.loads(before.get('.memory-usage.json', b'{}'))
    if not isinstance(usage, dict):
        raise ValueError('contador de uso inválido')
    today = datetime.date.today().isoformat()
    for name in names:
        if name == 'MEMORY.md' or name not in before or not name.endswith('.md'):
            raise ValueError(f'uso aponta para memória inexistente: {name}')
        record = usage.setdefault(name, {'uses': 0, 'recent': []})
        if session not in record.setdefault('sessions', []):
            record['uses'] = record.get('uses', 0) + 1
            record['last_used'] = today
            record['recent'] = (record.get('recent', []) + [today])[-10:]
            record['sessions'].append(session)
    if names:
        changed['.memory-usage.json'] = (json.dumps(usage, ensure_ascii=False, indent=2) + '\n').encode()


def checkpoint(store, request):
    session, lines = request['session_id'], request['lines']
    marker = state_dir() / 'memory-checkpoints' / (session + '.json')
    previous = read_json(marker, {'lines': 0})['lines']
    minimum = 20 if request.get('hook_event_name') == 'PreCompact' else 120
    if lines - previous < minimum:
        return
    before = snapshot(store)
    with tempfile.TemporaryDirectory(prefix='claude-memory-') as tmp:
        work = Path(tmp).resolve() / 'store'
        work.mkdir()
        stage_files(work, before)
        prompt = (ROOT / 'hooks/worker-prompt.md').read_text() + '\n' + (ROOT / 'skills/memory-curation/SKILL.md').read_text()
        # O transcript é dado, não uma sessão retomada com ferramentas e hooks herdados.
        request_text = json.dumps({'session_id': session, 'store': str(work),
                                  'transcript': request['transcript']}, ensure_ascii=False)
        report = model_run(work, 'checkpoint', ['**/*.md'], prompt, request_text)
        used = validate_report(report, 'checkpoint')
        changes = validate_changes(work, before, 'checkpoint')
        record_usage(before, changes, used, session)
        apply_changes(store, before, changes)
    save_json(marker, {'lines': lines})
    log('checkpoint', f'checkpoint confirmado sessao={session[:8]} arquivos={len(changes)}')


def consolidate(store, daily=False):
    day_marker = state_dir() / '.memory-consolidate-last-run'
    today = datetime.date.today().isoformat()
    if daily and day_marker.exists() and day_marker.read_text().strip() == today:
        return
    env = dict(os.environ, MEM_STATE_DIR=str(state_dir()))
    selected = subprocess.run([sys.executable, str(ROOT / 'scripts/candidates.py'), str(store)],
                              text=True, capture_output=True, env=env, check=True)
    selection = json.loads(selected.stdout)
    batch = int(os.environ.get('MEM_BATCH', '5'))
    if batch < 1:
        raise ValueError('MEM_BATCH deve ser positivo')
    candidates = selection['candidatos'][:batch]
    if not candidates:
        atomic_write(day_marker, today + '\n')
        log('consolidate', 'nada a consolidar (0 candidatos)')
        return
    path = state_dir() / 'memory-consolidated.json'
    state = read_json(path, {})
    if not isinstance(state, dict):
        raise ValueError('estado de consolidação inválido')
    before = snapshot(store)
    with tempfile.TemporaryDirectory(prefix='claude-memory-') as tmp:
        work = Path(tmp).resolve() / 'store'
        work.mkdir()
        stage_files(work, before)
        prompt = (ROOT / 'scripts/consolidate-prompt.md').read_text()
        report = model_run(work, 'consolidate', sorted({c['dossie'] for c in candidates}), prompt,
                           json.dumps({'store': str(work), 'candidatos': candidates}, ensure_ascii=False))
        results = validate_report(report, 'consolidate', candidates)
        changes = validate_changes(work, before, 'consolidate', candidates, results)
        apply_changes(store, before, changes)
    done = [c for c in candidates if results.get(c['arquivo']) in ('consolidated', 'already_summarized')]
    for candidate in done:
        name = candidate['arquivo']
        state[name] = {'modified': frontmatter_field(before[name], 'modified'), 'consolidado_em': today}
    save_json(path, state)
    if len(done) != len(candidates):
        raise ValueError(f'relatório parcial: {len(done)}/{len(candidates)} confirmadas; restantes continuam pendentes')
    atomic_write(day_marker, today + '\n')
    log('consolidate', f'consolidação confirmada arquivos={len(done)}')


def transcript_snapshot(path):
    messages = []
    lines = 0
    with path.open() as stream:
        for line in stream:
            lines += 1
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get('type') in ('user', 'assistant') and isinstance(event.get('message'), dict):
                message = dict(event['message'])
                content = message.get('content')
                if isinstance(content, list):
                    message['content'] = [x for x in content if x.get('type') != 'thinking']
                messages.append({'type': event['type'], 'message': message})
            elif event.get('type') == 'summary':
                messages.append(event)
    return lines, messages


def dispatch(mode):
    if os.environ.get('CLAUDE_MEMORY_WORKER'):
        return
    store = memory_store()
    command = [sys.executable, str(Path(__file__).resolve()), mode]
    if mode == 'checkpoint':
        request = json.load(sys.stdin)
        session = request.get('session_id', '')
        if not re.fullmatch(r'[a-zA-Z0-9-]+', session):
            raise ValueError('session_id inválido')
        lines, messages = transcript_snapshot(Path(request['transcript_path']))
        marker = state_dir() / 'memory-checkpoints' / (session + '.json')
        previous = read_json(marker, {'lines': 0})['lines']
        minimum = 20 if request.get('hook_event_name') == 'PreCompact' else 120
        if lines - previous < minimum:
            return
        fd, name = tempfile.mkstemp(prefix='claude-memory-request-', suffix='.json')
        with os.fdopen(fd, 'w') as stream:
            json.dump({'session_id': session, 'lines': lines, 'transcript': messages,
                       'hook_event_name': request.get('hook_event_name', 'Stop')}, stream)
        command += ['--request', name]
    else:
        command.append('--daily')
    env = dict(os.environ, MEM_STORE=str(store))
    try:
        subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True, env=env,
                         cwd=tempfile.gettempdir())
    except Exception:
        if mode == 'checkpoint':
            Path(name).unlink(missing_ok=True)
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['checkpoint', 'consolidate', 'dispatch-checkpoint', 'dispatch-consolidate'])
    parser.add_argument('--request', type=Path)
    parser.add_argument('--daily', action='store_true')
    args = parser.parse_args()
    mode = args.mode.removeprefix('dispatch-')
    try:
        if args.mode.startswith('dispatch-'):
            dispatch(mode)
            return 0
        store = memory_store()
        with store_lock(store):
            if mode == 'checkpoint':
                checkpoint(store, json.loads(args.request.read_text()))
            else:
                consolidate(store, args.daily)
        return 0
    except BlockingIOError:
        log(mode, 'store ocupado; nenhum marcador avançou')
        return 0
    except Exception as exc:
        log(mode, f'FALHOU: {exc}')
        return 0 if args.mode.startswith('dispatch-') else 1
    finally:
        if args.request:
            args.request.unlink(missing_ok=True)


if __name__ == '__main__':
    sys.exit(main())
