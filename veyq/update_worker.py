"""Update transaction with publisher-signature verification and rollback."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import venv
from pathlib import Path

if __package__:
    from .signing import verify_manifest
    from .runtime import ProfileLease
else:
    from signing import verify_manifest
    from runtime import ProfileLease


def write_json(path, data):
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(temp, path)


def wait_parent(pid):
    if os.name == "nt":
        import ctypes
        ctypes.windll.kernel32.OpenProcess.restype = ctypes.c_void_p
        handle = ctypes.windll.kernel32.OpenProcess(0x100000, False, pid)
        if handle:
            result = ctypes.windll.kernel32.WaitForSingleObject(ctypes.c_void_p(handle), 120000)
            ctypes.windll.kernel32.CloseHandle(ctypes.c_void_p(handle))
            if result != 0:
                raise RuntimeError("L'app non si e' chiusa: aggiornamento annullato.")
    else:
        for _ in range(240):
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return
            time.sleep(.5)
        raise RuntimeError("L'app non si e' chiusa: aggiornamento annullato.")


def _apply(plan_file, parent_pid=0):
    plan_file = Path(plan_file)
    plan = json.loads(plan_file.read_text(encoding="utf-8"))
    root, stage, data = (Path(plan[k]).resolve() for k in ("root", "stage", "data_root"))
    manifest, previous = plan["manifest"], plan["previous"]
    verify_manifest(manifest)
    if manifest["sequence"] <= previous.get("sequence", 0):
        raise ValueError("Aggiornamento precedente o ripetuto rifiutato.")
    if not stage.is_relative_to(data / "updates") or root == Path(root.anchor) or (root / ".git").exists():
        raise ValueError("Installazione o staging non valido.")
    # Check every staged and installed path immediately before applying.
    for name, digest in manifest["files"].items():
        path = stage / name
        if not path.resolve().is_relative_to(stage) or not (root / name).resolve().is_relative_to(root) or path.is_symlink():
            raise ValueError("Percorso aggiornamento non valido.")
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("Il pacchetto preparato e' cambiato.")
    if parent_pid:
        wait_parent(parent_pid)
    for name, digest in previous["files"].items():
        target = root / name
        if not target.resolve().is_relative_to(root) or not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise ValueError("File dell'app cambiato: nessuna modifica applicata.")
    backup = data / "app-backups" / (previous["commit"] + "-" + str(int(time.time())))
    backup.mkdir(parents=True)
    runtime_path = root / "runtime.json"
    old_runtime = runtime_path.read_bytes() if runtime_path.exists() else None
    changed = []
    created = []
    try:
        # Prepare a separate environment if dependencies change. The active
        # environment is untouched and can be reused during rollback.
        new_requirements = (stage / "requirements.txt").read_bytes()
        old_requirements = (root / "requirements.txt").read_bytes()
        if new_requirements != old_requirements:
            environment = root / ".veyq-runtime" / manifest["commit"]
            venv.EnvBuilder(with_pip=True).create(environment)
            python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            subprocess.run([str(python), "-m", "pip", "install", "-r", str(stage / "requirements.txt")],
                           check=True, timeout=600, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           **({"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}))
            write_json(runtime_path, {"python": str(python)})
        for name in set(previous["files"]) | set(manifest["files"]):
            target = root / name
            if target.exists():
                dest = backup / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, dest)
                changed.append(name)
            else:
                created.append(name)
            if name in manifest["files"]:
                target.parent.mkdir(parents=True, exist_ok=True)
                temp = target.with_suffix(target.suffix + ".update-tmp")
                shutil.copy2(stage / name, temp)
                os.replace(temp, target)
            else:
                target.unlink()
        # Verify the new modules compile without executing downloaded code.
        import py_compile
        for name in manifest["files"]:
            if name.endswith(".py"):
                py_compile.compile(str(root / name), doraise=True)
        write_json(data / "installation.json", {"root": str(root), "commit": manifest["commit"], "sequence": manifest["sequence"], "files": manifest["files"]})
        write_json(backup / "previous-installation.json", previous)
        plan_file.unlink()
        write_json(data / "update-status.json", {"ok": True, "commit": manifest["commit"], "backup": str(backup)})
    except Exception:
        for name in changed:
            shutil.copy2(backup / name, root / name)
        for name in created:
            (root / name).unlink(missing_ok=True)
        if old_runtime is None:
            runtime_path.unlink(missing_ok=True)
        else:
            runtime_path.write_bytes(old_runtime)
        write_json(data / "installation.json", previous)
        raise


def restart_verified_installation(root, data):
    """Only reopen the intact installation after success or early rejection."""
    try:
        installation = json.loads((data / "installation.json").read_text(encoding="utf-8"))
        if root == Path(root.anchor) or (root / ".git").exists() or Path(installation["root"]).resolve() != root:
            return False
        if not {"app.py", "Launcher.ps1"}.issubset(installation["files"]):
            return False
        for name, digest in installation["files"].items():
            path = root / name
            if path.is_symlink() or not path.resolve().is_relative_to(root) or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                return False
        flags = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {"start_new_session": True}
        if os.name == "nt":
            # The signed installer owns the same desktop/start-menu icon setup
            # for both first install and updates, including a branding change.
            if {"install.ps1", "assets/brand/veynuq-dark.ico"}.issubset(installation["files"]):
                try:
                    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(root / "install.ps1"), "-ShortcutOnly"], cwd=root, timeout=20, check=True,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **flags)
                except (OSError, subprocess.SubprocessError):
                    pass  # A read-only Desktop must not prevent the app reopening.
            subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(root / "Launcher.ps1")], cwd=root, **flags)
        else:
            subprocess.Popen([sys.executable, str(root / "app.py")], cwd=root, **flags)
        return True
    except (OSError, ValueError, KeyError, TypeError):
        return False


def apply(plan_file, parent_pid=0, restart=True):
    plan = json.loads(Path(plan_file).read_text(encoding="utf-8"))
    root, data = (Path(plan[k]).resolve() for k in ("root", "data_root"))
    try:
        if parent_pid: wait_parent(parent_pid)
        with ProfileLease(data).acquire(foreground=True,timeout=30):
            return _apply(plan_file, 0)
    finally:
        if restart:
            restart_verified_installation(root, data)


if __name__ == "__main__":
    try:
        apply(sys.argv[1], int(sys.argv[2]))
    except Exception as error:
        p = Path(sys.argv[1])
        write_json(p.parent / "update-status.json", {"ok": False, "error": str(error)})
        # Do not retry a broken update on every app startup.
        if p.exists():
            p.rename(p.with_name("failed-update.json"))
