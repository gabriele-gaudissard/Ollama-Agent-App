"""Narrow JavaScript bridge: tools are reachable only through the agent gate."""
import json
import os
import re
import shutil
import sys
import threading
import uuid
from pathlib import Path

import requests
from .engine import Agent, validate_endpoint
from .storage import Store, DEFAULTS, redact

ROOT = Path(__file__).resolve().parent.parent


class DesktopAPI:
    def __init__(self, store=None):
        self._store = store or Store(legacy=ROOT / "codex_data.json")
        self._agent = Agent(self._store, ROOT)
        self._window = None
        self._maintenance = threading.Lock()
        with self._store.lock:
            if not self._store.data["settings"]["workspace"]:
                workspace = self._store.root.parent / "Veyq Workspace"
                workspace.mkdir(exist_ok=True)
                self._store.data["settings"]["workspace"] = str(workspace)
                self._store.save()

    def _idle(self):
        if self._agent.busy or self._maintenance.locked():
            raise RuntimeError("Attendi la fine dell'attivita' prima di cambiare configurazione.")

    def get_settings(self):
        s = self._store.snapshot()["settings"]
        s["has_provider_token"] = bool(self._store.vault.get("provider"))
        s["has_github_token"] = bool(self._store.vault.get("github"))
        s["data_dir"] = str(self._store.root)
        s["version"] = "4.0.0"
        return s

    def save_settings(self, values):
        with self._agent.lock:
            self._idle()
            if not isinstance(values, dict):
                raise ValueError("Impostazioni non valide.")
            s = self._store.snapshot()["settings"]
            for key in ("lang", "provider", "url", "model", "permission", "network", "max_steps", "command_timeout", "github_repo", "auto_update"):
                if key in values:
                    s[key] = values[key]
            if s["provider"] not in {"local", "compatible"} or s["permission"] not in {"always", "auto", "full"}:
                raise ValueError("Modalita' non valida.")
            if s["permission"] == "full" and values.get("confirm_full") is not True:
                raise ValueError("Conferma esplicita richiesta per accesso completo.")
            if not isinstance(s["network"], bool) or not isinstance(s.get("auto_update", False), bool):
                raise ValueError("Valore rete/aggiornamenti non valido.")
            if not isinstance(s["max_steps"], int) or not 1 <= s["max_steps"] <= 100:
                raise ValueError("Limite passi: 1-100.")
            if not isinstance(s["command_timeout"], int) or not 1 <= s["command_timeout"] <= 600:
                raise ValueError("Timeout comandi: 1-600 secondi.")
            if not isinstance(s["model"], str) or not s["model"].strip() or len(s["model"]) > 200:
                raise ValueError("Nome modello non valido.")
            validate_endpoint(s["url"], s["network"])
            for name, field in (("provider", "provider_token"), ("github", "github_token")):
                if values.get("clear_" + field):
                    self._store.vault.set(name, "")
                elif values.get(field):
                    self._store.vault.set(name, values[field])
            with self._store.lock:
                self._store.data["settings"] = s
                self._store.save()
            return {"ok": True}

    def get_sessions(self):
        return [{k: s.get(k) for k in ("id", "title", "workspace", "project_id")} for s in self._store.snapshot()["sessions"]]

    def get_session(self, session_id):
        return next((s for s in self._store.snapshot()["sessions"] if s["id"] == session_id), None)

    def create_session(self):
        with self._agent.lock:
            self._idle()
            with self._store.lock:
                session = {"id": uuid.uuid4().hex, "title": "Nuova attivita'", "history": [], "plan": [],
                           "workspace": self._store.data["settings"]["workspace"], "project_id": ""}
                self._store.data["sessions"].insert(0, session)
                self._store.save()
            return session["id"]

    def rename_session(self, session_id, title):
        with self._agent.lock:
            self._idle()
            with self._store.lock:
                s = next(s for s in self._store.data["sessions"] if s["id"] == session_id)
                s["title"] = str(title).strip()[:100] or "Attivita'"
                self._store.save()
            return {"ok": True}

    def delete_session(self, session_id):
        with self._agent.lock:
            self._idle()
            with self._store.lock:
                self._store.data["sessions"] = [s for s in self._store.data["sessions"] if s["id"] != session_id]
                self._store.save()
            return {"ok": True}

    def choose_workspace(self, session_id):
        self._idle()
        if not self._window:
            return None
        import webview
        selected = self._window.create_file_dialog(webview.FOLDER_DIALOG)
        return self.set_workspace(session_id, selected[0]) if selected else None

    def set_workspace(self, session_id, path):
        with self._agent.lock:
            self._idle()
            workspace = Path(path).resolve()
            if not workspace.is_dir() or workspace == Path(workspace.anchor):
                raise ValueError("Scegli una cartella di progetto, non la radice del disco.")
            if workspace == self._store.root.resolve():
                raise ValueError("La cartella dati privata non puo' essere il progetto.")
            with self._store.lock:
                s = next(s for s in self._store.data["sessions"] if s["id"] == session_id)
                s["workspace"] = str(workspace)
                self._store.data["settings"]["workspace"] = str(workspace)
                self._store.save()
            return str(workspace)

    def attach_file(self):
        self._idle()
        if not self._window:
            return None
        import webview
        files = self._window.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=False)
        if not files:
            return None
        target = Path(files[0])
        from .tools import sensitive
        if sensitive(target) or target.resolve().is_relative_to(self._store.root.resolve()):
            raise ValueError("Allegato privato o contenente credenziali: usa un esempio senza segreti.")
        if target.stat().st_size > 20000:
            raise ValueError("Allega un file di testo sotto 20 KB; per file piu' grandi usa la cartella progetto.")
        content = redact(target.read_text(encoding="utf-8"), [self._store.vault.get("provider"), self._store.vault.get("github")])
        return {"name": target.name, "content": content}

    def start_run(self, session_id, text):
        with self._agent.lock:
            self._idle()
            return self._agent.start(session_id, text)

    def browse_project(self, session_id, path="."):
        self._idle()
        return self._agent.manual(session_id, "list_dir", {"path": path})

    def preview_project_file(self, session_id, path, start_line=1):
        self._idle()
        return self._agent.manual(session_id, "read_file", {"path": path, "start_line": start_line, "end_line": start_line + 299})

    def get_events(self, after=0):
        return self._agent.poll(after)

    def stop_run(self):
        return self._agent.stop()

    def resolve_approval(self, approval_id, allow):
        return self._agent.resolve(approval_id, allow)

    def get_memory(self):
        return self._store.snapshot().get("memory", "")

    def clear_memory(self):
        self._idle()
        with self._store.lock:
            self._store.data["memory"] = ""
            self._store.save()
        return {"ok": True}

    def export_session(self, session_id):
        session = self.get_session(session_id)
        if not self._window or not session:
            return None
        import webview
        files = self._window.create_file_dialog(webview.SAVE_DIALOG, save_filename="veyq-chat.json")
        if files:
            Path(files[0]).write_text(json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8")
            return str(files[0])
        return None

    def get_backups(self):
        folder = self._store.root / "backups"
        return sorted([{**json.loads(p.read_text(encoding="utf-8")), "id": p.stem} for p in folder.glob("*.json")], key=lambda b: b["time"], reverse=True)[:100]

    def restore_backup(self, backup_id, confirmed=False):
        self._idle()
        if not confirmed or not isinstance(backup_id, str) or not re.fullmatch(r"[a-f0-9]{32}", backup_id):
            raise ValueError("Conferma di ripristino richiesta.")
        folder = self._store.root / "backups"
        record = json.loads((folder / (backup_id + ".json")).read_text(encoding="utf-8"))
        target = Path(record["path"]).resolve()
        from .tools import ToolRunner, sensitive
        if target.is_relative_to(self._store.root.resolve()) or sensitive(target):
            raise ValueError("Ripristino in dati privati bloccato.")
        if target.exists():
            runner = ToolRunner(self._store, {**DEFAULTS, "workspace": str(target.parent)}, "restore", threading.Event(), lambda *a: None, lambda *a: False, ROOT, {})
            runner.backup(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(folder / backup_id, target)
        self._store.audit("restore", "restore_backup", "completed", backup_id)
        return {"ok": True, "path": str(target)}

    def get_models(self):
        s = self.get_settings()
        base = validate_endpoint(s["url"], s["network"])
        token = self._store.vault.get("provider")
        client = requests.Session()
        client.trust_env = False
        try:
            r = client.get(base + ("/api/tags" if s["provider"] == "local" else "/models"),
                           headers={"Authorization": "Bearer " + token} if token else {}, timeout=(5, 10), allow_redirects=False)
            r.raise_for_status()
            key = "models" if s["provider"] == "local" else "data"
            return {"ok": True, "models": [m.get("name", m.get("id")) for m in r.json().get(key, [])]}
        except Exception as e:
            return {"ok": False, "error": redact(str(e), [token])}
        finally:
            client.close()

    def model_action(self, model, action, confirmed=False):
        self._idle()
        if not confirmed or action not in {"pull", "delete"}:
            raise ValueError("Conferma richiesta per la gestione dei modelli.")
        if not self._maintenance.acquire(blocking=False):
            raise RuntimeError("Manutenzione gia' in corso.")
        client = requests.Session()
        client.trust_env = False
        try:
            s = self.get_settings()
            if s["provider"] != "local":
                raise ValueError("Gestione download disponibile solo per il motore locale.")
            if action == "pull" and not s["network"]:
                raise ValueError("Abilita la rete prima di scaricare modelli.")
            base = validate_endpoint(s["url"], s["network"])
            token = self._store.vault.get("provider")
            headers = {"Authorization": "Bearer " + token} if token else {}
            if action == "delete":
                with client.delete(base + "/api/delete", headers=headers, json={"model": model}, timeout=(5, 30), allow_redirects=False) as r:
                    r.raise_for_status()
            else:
                with client.post(base + "/api/pull", headers=headers, json={"model": model, "stream": True}, stream=True, timeout=(10, 90), allow_redirects=False) as r:
                    r.raise_for_status()
                    for line in r.iter_lines():
                        if line:
                            chunk = json.loads(line)
                            if "error" in chunk:
                                raise RuntimeError(chunk["error"])
                            self._agent.emit("model", {"status": chunk.get("status"), "completed": chunk.get("completed"), "total": chunk.get("total")})
            return {"ok": True}
        finally:
            client.close()
            self._maintenance.release()

    def check_updates(self):
        self._idle()
        from .updater import Updater
        with self._maintenance:
            return Updater(ROOT, self._store).check_and_stage()

    def apply_update(self):
        self._idle()
        from .updater import Updater
        result = Updater(ROOT, self._store).launch_apply()
        if result.get("ok") and self._window:
            self._window.destroy()
        return result


def main():
    store = Store(legacy=ROOT / "codex_data.json")
    instance = (store.root / "instance.lock").open("a+b")
    try:
        if os.name == "nt":
            import msvcrt
            instance.seek(0)
            if not instance.read(1):
                instance.write(b"0")
                instance.flush()
            instance.seek(0)
            msvcrt.locking(instance.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(instance, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        raise RuntimeError("Veyq e' gia' aperto.")
    if "--self-check" in sys.argv:
        api = DesktopAPI(store)
        print(json.dumps({"version": "4.0.0", "models": api.get_models(), "data_dir": str(store.root)}))
        return
    if "--install" in sys.argv:
        from .updater import enable_updates
        enable_updates(ROOT, store)
        return
    import webview
    api = DesktopAPI(store)
    window = webview.create_window("Veyq", url=str(ROOT / "index.html"), js_api=api,
                                  width=1440, height=940, min_size=(900, 650), resizable=True, text_select=True)
    api._window = window
    window.events.closed += api._agent.stop
    webview.start(debug=False)
    instance.close()
