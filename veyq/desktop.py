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
        self._model_cancel = threading.Event()
        self._model_response = None
        with self._store.lock:
            if not self._store.data["settings"]["workspace"]:
                workspace = self._store.root.parent / "Veynuq Workspace"
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
        s["recovery_notice"] = self._store.recovery_notice
        return s

    def get_tool_catalog(self):
        from .tools import TOOLS
        names = {tool['function']['name'] for tool in TOOLS}
        groups = [
            ('Files and coding', 'Read, search, edit, run commands and tests, manage Git, clone repositories and restore backups.', {'list_dir','read_file','search_files','write_file','edit_file','make_dir','move_file','delete_file','exec_cmd','git_status','clone_repository','restore_backup'}),
            ('Mouse and keyboard', 'Inspect Windows applications, click, double-click, right-click, drag, scroll, type and change keyboard layouts.', {'computer_windows','computer_inspect','computer_action','computer_pointer','keyboard_layout'}),
            ('Web and browser', 'Search, read websites, download files and operate an isolated browser with observed page elements.', {'web_search','read_url','download_file','browser_open','browser_state','browser_action'}),
            ('GitHub', 'Read and update repositories, issues, pull requests, branches and releases.', {'github'}),
            ('Images and documents', 'Inspect image files and read PDF/DOCX documents. Create documents, spreadsheets and charts with project code.', {'view_image','read_document'}),
            ('Memory and task control', 'Maintain local memory, plan work, ask essential questions and use context from related project chats.', {'save_memory','update_plan','ask_user','read_project_context'}),
        ]
        return {'total': len(names), 'groups': [{'name': title,'description': description,'count': len(tools & names)} for title, description, tools in groups]}

    def save_settings(self, values):
        with self._agent.lock:
            self._idle()
            if not isinstance(values, dict):
                raise ValueError("Impostazioni non valide.")
            s = self._store.snapshot()["settings"]
            for key in ("lang", "provider", "url", "model", "permission", "network", "max_steps", "command_timeout", "github_repo", "auto_update", "vision"):
                if key in values:
                    s[key] = values[key]
            if s["provider"] not in {"local", "compatible"} or s["permission"] not in {"always", "auto", "full"}:
                raise ValueError("Modalita' non valida.")
            if s["lang"] not in {"en", "it", "es", "fr"}:
                raise ValueError("Supported languages: English, Italian, Spanish, French.")
            if s["permission"] == "full" and values.get("confirm_full") is not True:
                raise ValueError("Conferma esplicita richiesta per accesso completo.")
            if not isinstance(s["network"], bool) or not isinstance(s.get("auto_update", False), bool):
                raise ValueError("Valore rete/aggiornamenti non valido.")
            if not isinstance(s["vision"], bool):
                raise ValueError("Vision must be enabled explicitly for remote vision models.")
            if type(s["max_steps"]) is not int or not 0 <= s["max_steps"] <= 100:
                raise ValueError("Step limit: 0 for unlimited, or 1–100.")
            if type(s["command_timeout"]) is not int or not 0 <= s["command_timeout"] <= 600:
                raise ValueError("Command timeout: 0 to disable, or 1–600 seconds.")
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

    def get_sessions(self, query=""):
        query = str(query).lower()[:500]
        rows = []
        for s in self._store.snapshot()["sessions"]:
            history = s.get("history", [])
            if query and query not in (s["title"] + " " + " ".join(str(m.get("content", "")) for m in history)).lower():
                continue
            title = s["title"]
            first = next((m.get("content", "").strip() for m in history if m.get("role") == "user"), "")
            if s.get("auto_title", True) and first and title == first[:25]:
                title = first.splitlines()[0][:100]
            rows.append({**{k: s.get(k) for k in ("id", "workspace", "project_id")}, "title": title,
                         "untitled": s.get("title") == "New activity" and not history})
        return rows

    def get_projects(self):
        return self._store.snapshot()["projects"]

    def set_language(self, lang):
        if lang not in {"en", "it", "es", "fr"}:
            raise ValueError("Unsupported language.")
        with self._store.lock:
            self._store.data["settings"]["lang"] = lang
            self._store.save()
        return {"ok": True}

    def create_project(self, name, path=""):
        with self._agent.lock:
            self._idle()
            if not isinstance(name, str) or not name.strip() or len(name) > 100:
                raise ValueError("Project name must contain 1–100 characters.")
            project_id = uuid.uuid4().hex
            target = Path(path).resolve() if path else Path(self._store.data["settings"]["workspace"]) / (re.sub(r"[^A-Za-z0-9_-]", "-", name).strip("-")[:50] or "project")
            from .tools import sensitive
            if sensitive(target) or target.is_relative_to(self._store.root.resolve()) or target == Path(target.anchor):
                raise ValueError("Choose a project folder outside protected data.")
            if not path and target.exists():
                target = target.with_name(target.name + "-" + project_id[:6])
            target.mkdir(parents=True, exist_ok=True)
            project = {"id": project_id, "name": name.strip(), "path": str(target)}
            with self._store.lock:
                self._store.data["projects"].append(project)
                self._store.save()
            return project

    def assign_project(self, session_id, project_id):
        with self._agent.lock:
            self._idle()
            project = next((p for p in self._store.data["projects"] if p["id"] == project_id), None)
            if project_id and not project:
                raise ValueError("Project not found.")
            with self._store.lock:
                s = next(s for s in self._store.data["sessions"] if s["id"] == session_id)
                s["project_id"] = project_id
                if project:
                    s["workspace"] = project["path"]
                    s["cwd"] = project["path"]
                self._store.save()
            return {"ok": True}

    def get_session(self, session_id):
        return next((s for s in self._store.snapshot()["sessions"] if s["id"] == session_id), None)

    def create_session(self):
        with self._agent.lock:
            self._idle()
            with self._store.lock:
                session = {"id": uuid.uuid4().hex, "title": "New activity", "history": [], "plan": [],
                           "workspace": self._store.data["settings"]["workspace"], "project_id": "", "auto_title": True}
                self._store.data["sessions"].insert(0, session)
                self._store.save()
            return session["id"]

    def rename_session(self, session_id, title):
        with self._agent.lock:
            self._idle()
            with self._store.lock:
                s = next(s for s in self._store.data["sessions"] if s["id"] == session_id)
                s["title"] = str(title).strip()[:100] or "Attivita'"
                s["auto_title"] = False
                self._store.save()
            return {"ok": True}

    def delete_session(self, session_id):
        with self._agent.lock:
            self._idle()
            with self._store.lock:
                self._store.data["sessions"] = [s for s in self._store.data["sessions"] if s["id"] != session_id]
                self._store.save()
            if self._agent.current_session == session_id:
                self._agent.current_session = ""
                self._agent.events = type(self._agent.events)((e for e in self._agent.events if e.get("session_id") != session_id), maxlen=2000)
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
                s["cwd"] = str(workspace)
                self._store.data["settings"]["workspace"] = str(workspace)
                self._store.save()
            return str(workspace)

    def attach_file(self, session_id):
        if not self._window:
            return None
        import webview
        files = self._window.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=True)
        if not files:
            return None
        from .tools import sensitive
        session = self.get_session(session_id)
        if not session or len(files) > 10:
            raise ValueError("Choose a chat and at most ten files.")
        workspace = Path(session["workspace"]).resolve()
        folder = workspace / ".veyq-attachments"
        if sensitive(folder.resolve()) or folder.is_symlink() or not folder.resolve().is_relative_to(workspace):
            raise ValueError("Attachment folder is protected or points outside the project.")
        result = []
        for value in files:
            source = Path(value).resolve()
            if sensitive(source) or source.is_relative_to(self._store.root.resolve()) or not source.is_file():
                raise ValueError("Protected attachment: use an example without secrets.")
            if source.stat().st_size > 20_000_000:
                raise ValueError("Attachment limit is 20 MB per file.")
            folder.mkdir(exist_ok=True)
            destination = folder / (uuid.uuid4().hex[:8] + "-" + source.name)
            shutil.copy2(source, destination)
            record = {"name": source.name, "path": str(destination), "bytes": destination.stat().st_size}
            if source.stat().st_size < 1_000_000:
                try:
                    text = source.read_text(encoding="utf-8")
                    if "\x00" not in text:
                        record["text"] = text[:8000]
                        record["truncated"] = len(text) > 8000
                except (UnicodeError, OSError):
                    pass
            result.append(record)
        return result

    def link_folder(self):
        if not self._window:
            return None
        import webview
        selected = self._window.create_file_dialog(webview.FOLDER_DIALOG)
        if not selected:
            return None
        target = Path(selected[0]).resolve()
        from .tools import sensitive
        if sensitive(target) or target.is_relative_to(self._store.root.resolve()) or target == Path(target.anchor):
            raise ValueError("Choose a folder outside protected data.")
        return str(target)

    def start_run(self, session_id, text):
        with self._agent.lock:
            self._idle()
            return self._agent.start(session_id, text)

    def follow_up(self, session_id, text):
        return self._agent.follow_up(session_id, text)

    def answer_question(self, question_id, answer):
        return self._agent.resolve_question(question_id, answer)

    def regenerate(self, session_id, history_index, confirmed=False):
        with self._agent.lock:
            self._idle()
            if not confirmed or type(history_index) is not int:
                raise ValueError("Confirm regeneration; later chat messages will be removed, executed actions stay applied.")
            session = next(s for s in self._store.data["sessions"] if s["id"] == session_id)
            if not 0 <= history_index < len(session["history"]) or session["history"][history_index]["role"] != "assistant":
                raise ValueError("Choose an assistant response.")
            with self._store.lock:
                session["history"] = session["history"][:history_index]
                self._store.save()
            return self._agent.start(session_id, "Regenerate the response using existing tool evidence. Completed side effects remain applied; inspect before repeating any action.")

    def browse_project(self, session_id, path="."):
        self._idle()
        return self._agent.manual(session_id, "list_dir", {"path": path})

    def preview_project_file(self, session_id, path, start_line=1):
        self._idle()
        return self._agent.manual(session_id, "read_file", {"path": path, "start_line": start_line, "end_line": start_line + 299})

    def get_events(self, after=0):
        return {**self._agent.poll(after), "model_busy": self._maintenance.locked()}

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

    def save_memory(self, text):
        self._idle()
        if not isinstance(text, str) or len(text) > 10000:
            raise ValueError("Memory limit: 10000 characters.")
        if redact(text, [self._store.vault.get("provider"), self._store.vault.get("github")]) != text:
            raise ValueError("Do not store credentials in memory.")
        with self._store.lock:
            self._store.data["memory"] = text
            self._store.save()
        return {"ok": True}

    def open_external(self, url):
        from urllib.parse import urlsplit
        parsed = urlsplit(url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or len(url) > 4000:
            raise ValueError("Only public HTTPS links can be opened.")
        from .network import public_target
        public_target(url)
        import webbrowser
        webbrowser.open(url)
        return {"ok": True}

    def open_provider_account(self):
        from urllib.parse import urlsplit
        s = self.get_settings()
        if s["provider"] == "local":
            return self.open_external("https://ollama.com")
        p = urlsplit(s["url"])
        return self.open_external("https://" + p.netloc)

    def setup_local_engine(self, confirmed=False):
        self._idle()
        if confirmed is not True:
            raise ValueError("Confirm installation of the optional local engine.")
        from .setup import setup_engine
        with self._maintenance:
            return setup_engine(self._store.root)

    def finish_setup(self):
        with self._store.lock:
            self._store.data["settings"]["setup_completed"] = True
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
            records = r.json().get(key, [])
            return {"ok": True, "models": [m.get("name", m.get("id")) for m in records], "details": records}
        except Exception as e:
            return {"ok": False, "error": redact(str(e), [token])}
        finally:
            client.close()

    def get_model_catalog(self):
        from .models import catalog, hardware
        return {"models": catalog(), "hardware": hardware(self._store.data["settings"]["workspace"])}

    def get_model_info(self, name):
        from .models import estimate, hardware
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}", name):
            raise ValueError("Choose a model first.")
        info = estimate(name)
        s = self.get_settings()
        info["hardware"] = hardware(s["workspace"])
        if s["provider"] != "local":
            info = {**estimate("unknown"), "name": name, "hardware": info["hardware"], "metadata_origin": "Remote provider: local requirements do not apply"}
            return info
        client = requests.Session()
        client.trust_env = False
        try:
            token = self._store.vault.get("provider")
            response = client.post(validate_endpoint(s["url"], s["network"]) + "/api/show", json={"model": name}, headers={"Authorization": "Bearer " + token} if token else {}, timeout=(5, 10), allow_redirects=False)
            if response.status_code == 200:
                data = response.json()
                info["installed"] = True
                info["metadata_origin"] = "Installed engine metadata"
                if isinstance(data.get("capabilities"), list):
                    info["installed_capabilities"] = data["capabilities"]
                    info["tools"] = "tools" in data["capabilities"]
                    info["vision"] = "vision" in data["capabilities"]
                details = data.get("details", {})
                info["parameters"] = details.get("parameter_size") or info.get("parameters")
                info["quantization"] = details.get("quantization_level") or info.get("quantization")
                info["family"] = details.get("family")
                limits = [v for k, v in data.get("model_info", {}).items() if k.endswith(".context_length") and isinstance(v, int)]
                if limits: info["context_tokens"] = max(limits)
                # A tag can be customized locally; its capabilities override catalog expectations.
                tags = self.get_models()
                record = next((m for m in tags.get("details", []) if m.get("name") == name), {})
                if record.get("size"):
                    info["installed_size_gb"] = round(record["size"] / 1e9, 2)
                    if not info.get("source"):
                        actual = estimate(name, record["size"])
                        for k in ["download_gb", "ram_min_gb", "ram_recommended_gb", "vram_min_gb", "vram_recommended_gb"]: info[k] = actual[k]
        except Exception:
            pass
        finally:
            client.close()
        return info

    def open_model_source(self, name):
        from .models import catalog
        model = next((m for m in catalog() if m["name"] == name), None)
        if not model:
            raise ValueError("Choose a catalog model.")
        import webbrowser
        webbrowser.open(model["source"])
        return {"ok": True}

    def model_action(self, model, action, confirmed=False):
        self._idle()
        if not isinstance(model, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}", model):
            raise ValueError("Enter a valid model name.")
        if not confirmed or action not in {"pull", "delete"}:
            raise ValueError("Conferma richiesta per la gestione dei modelli.")
        if not self._maintenance.acquire(blocking=False):
            raise RuntimeError("Manutenzione gia' in corso.")
        client = requests.Session()
        client.trust_env = False
        self._model_cancel.clear()
        try:
            s = self.get_settings()
            if s["provider"] != "local":
                raise ValueError("Gestione download disponibile solo per il motore locale.")
            # The user's explicit model-download confirmation is independent of
            # the agent's network permission, like the app updater and installer.
            base = validate_endpoint(s["url"], s["network"])
            if action == "pull" and base in {"http://localhost:11434", "http://127.0.0.1:11434"} and os.name == "nt":
                from .setup import engine_available, setup_engine
                if not engine_available():
                    self._agent.emit("model", {"status": "Setting up the local engine…"})
                    setup_engine(self._store.root)
            token = self._store.vault.get("provider")
            headers = {"Authorization": "Bearer " + token} if token else {}
            if action == "delete":
                with client.delete(base + "/api/delete", headers=headers, json={"model": model}, timeout=(5, 30), allow_redirects=False) as r:
                    r.raise_for_status()
            else:
                with client.post(base + "/api/pull", headers=headers, json={"model": model, "stream": True}, stream=True, timeout=(10, 90), allow_redirects=False) as r:
                    self._model_response = r
                    r.raise_for_status()
                    for line in r.iter_lines():
                        if self._model_cancel.is_set():
                            return {"ok": False, "cancelled": True}
                        if line:
                            chunk = json.loads(line)
                            if "error" in chunk:
                                raise RuntimeError(chunk["error"])
                            self._agent.emit("model", {"status": chunk.get("status"), "completed": chunk.get("completed"), "total": chunk.get("total")})
            return {"ok": True}
        except Exception:
            if self._model_cancel.is_set():
                return {"ok": False, "cancelled": True}
            raise
        finally:
            self._model_response = None
            client.close()
            self._maintenance.release()

    def cancel_model_action(self):
        self._model_cancel.set()
        if self._model_response is not None:
            from .engine import interrupt_response
            interrupt_response(self._model_response)
        return {"ok": True}

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
    profile = ROOT / "profile.json"
    data_dir = None
    if not (os.environ.get("VEYNUQ_DATA_DIR") or os.environ.get("VEYQ_DATA_DIR")) and profile.exists():
        data_dir = Path(json.loads(profile.read_text(encoding="utf-8"))["data_dir"])
        if not data_dir.is_absolute():
            raise ValueError("The installed profile path must be absolute.")
    store = Store(root=data_dir, legacy=ROOT / "codex_data.json")
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
        raise RuntimeError("Veynuq e' gia' aperto.")
    if "--self-check" in sys.argv:
        api = DesktopAPI(store)
        print(json.dumps({"version": "4.0.0", "models": api.get_models(), "data_dir": str(store.root)}))
        return
    if "--install" in sys.argv:
        from .updater import enable_updates
        enable_updates(ROOT, store)
        from .storage import atomic_json
        atomic_json(ROOT / "profile.json", {"data_dir": str(store.root)})
        return
    import webview
    api = DesktopAPI(store)
    window = webview.create_window("Veynuq", url=str(ROOT / "index.html"), js_api=api,
                                  width=1440, height=940, min_size=(900, 650), resizable=True, text_select=True)
    api._window = window
    import faulthandler
    window.events.loaded += faulthandler.cancel_dump_traceback_later
    def shutdown():
        # pywebview puts callback returns in a set: API dictionaries cannot
        # be returned from an event handler. Closing must also stop downloads.
        api._agent.stop()
        api.cancel_model_action()
    window.events.closing += shutdown
    window.events.closed += shutdown
    webview.start(debug=False, icon=str(ROOT / "assets" / "brand" / "veynuq-dark.ico"))
    instance.close()
