"""One profile owner across the foreground app and scheduled workers."""
import json
import os
import time
from pathlib import Path


def profile_root(app_root):
    override = os.environ.get('VEYNUQ_DATA_DIR') or os.environ.get('VEYQ_DATA_DIR')
    anchor = Path(app_root)/'profile.json'
    if override:
        root = Path(override)
    elif anchor.exists():
        root = Path(json.loads(anchor.read_text(encoding='utf-8'))['data_dir'])
        if not root.is_absolute(): raise ValueError('Profile path must be absolute.')
    else:
        home = Path(os.environ.get('LOCALAPPDATA', str(Path.home()/'.local/share')))
        root = home/('Veyq' if (home/'Veyq/state.json').exists() else 'Veynuq')
    return (root/'state.json').resolve().parent if (root/'state.json').exists() else root.resolve()


class ProfileLease:
    def __init__(self, root):
        self.root = Path(root)
        self.stream = None

    def acquire(self, foreground=False, timeout=0):
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root/'instance.lock'
        self.stream = path.open('a+b')
        self.root = path.resolve().parent
        # Windows denies reading an exclusively locked byte. Inspect file size
        # before attempting the lock, so a second instance can signal the owner.
        try:
            if os.fstat(self.stream.fileno()).st_size == 0:
                self.stream.write(b'0'); self.stream.flush()
        except OSError:
            self.close(); raise
        deadline = time.monotonic()+timeout
        signalled = False
        while True:
            try:
                self.stream.seek(0)
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self.stream, fcntl.LOCK_EX|fcntl.LOCK_NB)
            except OSError:
                # The worker cancels a read-only run when the user opens the app.
                if foreground and not signalled:
                    try:
                        owner=json.loads((self.root/'profile-owner.json').read_text(encoding='utf-8'))
                    except (OSError,ValueError): owner={}
                    if owner.get('kind')!='background':
                        self.close()
                        raise RuntimeError('Veynuq is already open for this profile.')
                    (self.root/'background-stop').write_text(str(time.time()), encoding='ascii')
                    signalled = True
                if time.monotonic() >= deadline:
                    self.close()
                    raise RuntimeError('This profile is in use. Wait for the active app or worker to close.')
                time.sleep(.2)
                continue
            break
        try:
            (self.root/'profile-owner.json').write_text(json.dumps({'pid':os.getpid(),'kind':'foreground' if foreground else 'background'}),encoding='utf-8')
        except OSError:
            self.close(); raise
        return self

    def close(self):
        if self.stream:
            self.stream.close(); self.stream = None

    def __enter__(self): return self
    def __exit__(self, *args): self.close()
