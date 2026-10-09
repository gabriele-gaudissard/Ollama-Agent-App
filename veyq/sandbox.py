"""Offline Docker execution over a disposable, filtered copy of the project."""
import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import uuid
from pathlib import Path

IMAGE = 'python:3.13-slim'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


class Sandbox:
    def __init__(self, runner):
        self.runner = runner
        self.root = None
        self.baseline = {}
        self.container = None
        self.context = None
        saved = runner.session.get('sandbox', {})
        key = saved.get('id', '')
        if re.fullmatch(r'[0-9a-f]{32}', key) and saved.get('workspace') == str(runner.workspace):
            root = runner.store.root / 'sandboxes' / key
            try:
                from .tools import linklike
                if linklike(root) or root.with_suffix('.json').stat().st_size > 500000: raise ValueError('Invalid sandbox record.')
                baseline = json.loads(root.with_suffix('.json').read_text(encoding='utf-8'))
                if not isinstance(baseline, dict) or any(not isinstance(p, str) or Path(p).is_absolute() or '..' in Path(p).parts or not re.fullmatch(r'[0-9a-f]{64}', h) for p, h in baseline.items()):
                    raise ValueError('Invalid sandbox baseline.')
                if root.is_dir():
                    self.root, self.baseline = root, baseline
            except (OSError, ValueError): pass

    def save(self):
        from .storage import atomic_json
        atomic_json(self.root.with_suffix('.json'), self.baseline)
        with self.runner.store.lock:
            self.runner.session['sandbox'] = {'id': self.root.name, 'workspace': str(self.runner.workspace)}
            self.runner.store.save()

    def local_context(self):
        # Explicit context overrides DOCKER_HOST. Refuse remote engines entirely.
        kwargs = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
        result = subprocess.run(['docker', 'context', 'show'], capture_output=True, text=True, timeout=5, **kwargs)
        context = result.stdout.strip()
        if result.returncode or not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}', context):
            raise RuntimeError('Cannot inspect the Docker context; no command was run.')
        result = subprocess.run(['docker', 'context', 'inspect', context], capture_output=True, text=True, timeout=5, **kwargs)
        if result.returncode: raise RuntimeError('Cannot inspect the Docker endpoint.')
        endpoint = json.loads(result.stdout)[0]['Endpoints']['docker']['Host']
        if not (endpoint.startswith('unix:///') or endpoint.lower().startswith('npipe:////./pipe/')):
            raise PermissionError('Sandbox requires a local Docker engine; remote endpoints are refused.')
        self.context = context

    def prepare(self):
        from .tools import sensitive, linklike, SKIP
        if not shutil.which('docker'):
            raise RuntimeError('Docker is not installed. Sandbox execution is unavailable; no host command was run.')
        self.local_context()
        if self.root:
            self.check_size()
            return
        self.baseline = {}
        root = self.runner.store.root / 'sandboxes' / uuid.uuid4().hex
        root.mkdir(parents=True)
        total = 0
        for directory, folders, files in os.walk(self.runner.workspace, followlinks=False):
            folders[:] = [n for n in folders if n not in SKIP and not sensitive(Path(directory, n)) and not linklike(Path(directory, n)) and not Path(directory, n).resolve().is_relative_to(self.runner.store.root)]
            for name in files:
                source = Path(directory, name)
                if sensitive(source) or linklike(source) or source.resolve().is_relative_to(self.runner.store.root):
                    continue
                total += source.stat().st_size
                if total > 20_000_000 or len(self.baseline) >= 2000 or source.stat().st_size > 2_000_000:
                    raise ValueError('Sandbox copy exceeds 20 MB / 2000 files / 2 MB per file. Choose a smaller source project.')
                rel = source.relative_to(self.runner.workspace).as_posix()
                destination = root / rel
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)
                self.baseline[rel] = digest(source)
        self.root = root
        self.save()

    def check_size(self):
        if not self.root: return
        total = count = 0
        for directory, folders, files in os.walk(self.root, followlinks=False):
            count += len(folders) + len(files)
            for name in files:
                path = Path(directory, name)
                if not path.is_symlink(): total += path.stat().st_size
            if total > 20_000_000 or count > 4000:
                raise ValueError('Sandbox output exceeded the monitored 20 MB / 4000 entries limit; execution stopped.')

    def execute(self, command, cwd, timeout):
        self.prepare()
        if not cwd.is_relative_to(self.runner.workspace):
            raise PermissionError('Sandbox commands must start inside the selected project.')
        if ',' in str(self.root):
            raise ValueError('Docker mount path cannot contain a comma.')
        self.container = 'veynuq-' + uuid.uuid4().hex
        argv = ['docker', '--context', self.context, 'run', '--rm', '--pull=never', '--name', self.container, '--network=none',
                '--read-only', '--cap-drop=ALL', '--security-opt=no-new-privileges', '--pids-limit=128',
                '--memory=512m', '--cpus=1', '--user', '65534:65534', '--tmpfs', '/tmp:rw,noexec,nosuid,size=64m',
                '--mount', 'type=bind,src=' + str(self.root) + ',dst=/workspace', '--workdir',
                '/workspace/' + cwd.relative_to(self.runner.workspace).as_posix(), IMAGE, '/bin/sh', '-c', command]
        # Linux bind mounts need a writable disposable directory for the unprivileged UID.
        if os.name != 'nt':
            for folder, dirs, files in os.walk(self.root):
                Path(folder).chmod(0o777)
                for file in files: Path(folder, file).chmod(0o666)
        try:
            result = self.runner.run_process(argv, self.runner.workspace, timeout)
            result.update(environment='sandbox', network='disabled', host_project_unchanged=True,
                          changes=self.changes())
            return result
        finally:
            self.stop()

    def stop(self):
        if self.container:
            name, self.container = self.container, None
            kwargs = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
            try: subprocess.run(['docker', '--context', self.context, 'rm', '-f', name], capture_output=True, timeout=10, **kwargs)
            except (OSError, subprocess.TimeoutExpired): pass

    def changes(self):
        from .tools import sensitive, linklike
        if not self.root: return []
        self.check_size()
        files = {}
        for directory, folders, names in os.walk(self.root, followlinks=False):
            if any(linklike(Path(directory, n)) for n in folders):
                raise PermissionError('Sandbox created a link; changes cannot be applied.')
            for name in names:
                path = Path(directory, name)
                if linklike(path) or sensitive(path) or path.stat().st_size > 2_000_000:
                    raise PermissionError('Sandbox output contains a protected, linked or oversized file.')
                if len(files) >= 2000: raise ValueError('Too many sandbox output files.')
                files[path.relative_to(self.root).as_posix()] = digest(path)
        result = []
        for rel in sorted(set(files) | set(self.baseline)):
            if files.get(rel) == self.baseline.get(rel): continue
            before = self.runner.workspace / rel
            after = self.root / rel
            try:
                a = before.read_text(encoding='utf-8').splitlines() if before.exists() else []
                b = after.read_text(encoding='utf-8').splitlines() if after.exists() else []
                diff = '\n'.join(difflib.unified_diff(a, b, fromfile=rel, tofile=rel))[:10000]
            except UnicodeError: diff = '[Binary file]'
            result.append({'path': rel, 'base_hash': self.baseline.get(rel), 'new_hash': files.get(rel), 'diff': diff})
        return result

    def apply(self):
        from .storage import atomic_bytes
        changes = self.changes()
        pending = []
        for row in changes:
            target = self.runner.path(row['path'])
            if not target.is_relative_to(self.runner.workspace) or digest(target) != row['base_hash']:
                raise ValueError('Host file changed since sandbox creation; inspect and rerun before applying: ' + row['path'])
            pending.append((row, target, target.read_bytes() if target.is_file() else None))
        applied = []
        try:
            for row, target, old in pending:
                if self.runner.cancel.is_set(): raise RuntimeError('Sandbox application stopped; applied changes will be rolled back.')
                self.runner.backup(target)
                target.parent.mkdir(parents=True, exist_ok=True)
                if row['new_hash'] is None: target.unlink()
                else: atomic_bytes(target, (self.root / row['path']).read_bytes())
                applied.append((target, old))
        except Exception:
            for target, old in reversed(applied):
                if old is None: target.unlink(missing_ok=True)
                else: atomic_bytes(target, old)
            raise
        for row in changes:
            if row['new_hash'] is None: self.baseline.pop(row['path'], None)
            else: self.baseline[row['path']] = row['new_hash']
        self.save()
        return {'applied': len(changes), 'backups_created': True}
