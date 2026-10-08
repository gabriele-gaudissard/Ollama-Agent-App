"""Validated tools and a permission gate shared by every agent action."""
import difflib
import base64
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from urllib.parse import parse_qs, quote, urlsplit

from bs4 import BeautifulSoup
from .network import public_request


def schema(name, description, properties, required=()):
    return {"type": "function", "function": {"name": name, "description": description,
            "parameters": {"type": "object", "properties": properties,
                           "required": list(required), "additionalProperties": False}}}


S = {"type": "string"}
I = {"type": "integer"}
TOOLS = [
    schema("list_dir", "List workspace directory entries, without following links.", {"path": S}, ["path"]),
    schema("read_file", "Read a UTF-8 file with line numbers; use pagination for large files.", {"path": S, "start_line": I, "end_line": I}, ["path"]),
    schema("search_files", "Search literal text recursively in workspace files; excludes secrets, dependencies and links.", {"query": S, "path": S}, ["query"]),
    schema("write_file", "Create/replace a UTF-8 file. Existing content is backed up. Read before overwriting.", {"path": S, "content": S}, ["path", "content"]),
    schema("edit_file", "Replace one exact occurrence, with backup. Fails if old text is missing or ambiguous.", {"path": S, "old": S, "new": S}, ["path", "old", "new"]),
    schema("make_dir", "Create a workspace directory.", {"path": S}, ["path"]),
    schema("move_file", "Move/rename one file, no overwrite. Both paths need permission.", {"path": S, "destination": S}, ["path", "destination"]),
    schema("delete_file", "Delete one regular file after making a recoverable backup. No recursive deletion.", {"path": S}, ["path"]),
    schema("exec_cmd", "Execute a shell command, tests or Git. Commands run with host user permissions, not in an OS sandbox. Needs approval except in full access.", {"command": S, "cwd": S, "timeout": I}, ["command"]),
    schema("git_status", "Read status/diff/log through fixed Git arguments; no arbitrary Git flags.", {"view": {"type": "string", "enum": ["status", "diff", "log"]}}, ["view"]),
    schema("web_search", "Search DuckDuckGo, with Bing fallback, and return titles, URLs and snippets.", {"query": S}, ["query"]),
    schema("read_url", "Read public HTTP(S) documentation. Private network targets are blocked.", {"url": S}, ["url"]),
    schema("github", "GitHub REST for the user-selected owner/repo only. GET reads; POST/PATCH/PUT/DELETE mutations need approval in auto mode. PUT contents requires base64 content and current SHA for replacement. Endpoint begins with issues, pulls, contents, commits, branches, or releases. Credentials are injected by backend.", {"method": {"type": "string", "enum": ["GET", "POST", "PATCH", "PUT", "DELETE"]}, "endpoint": S, "body": {"type": "object"}}, ["method", "endpoint"]),
    schema("update_plan", "Publish task steps with pending, in_progress or completed status.", {"steps": {"type": "array", "items": {"type": "object", "properties": {"step": S, "status": {"type": "string", "enum": ["pending", "in_progress", "completed"]}}, "required": ["step", "status"], "additionalProperties": False}}}, ["steps"]),
    schema("save_memory", "Save a useful preference locally for future chats. Never store secrets.", {"text": S}, ["text"]),
]
SPECS = {t["function"]["name"]: t["function"]["parameters"] for t in TOOLS}
READ_ONLY = {"list_dir", "read_file", "search_files", "git_status"}
WRITE = {"write_file", "edit_file", "make_dir", "move_file", "delete_file"}
SKIP = {".git", "node_modules", ".venv", "venv", "__pycache__", ".ssh", ".aws", ".azure", ".codex", ".veyq", "dist", "build"}


def linklike(path):
    return path.is_symlink() or bool(getattr(path.lstat(), "st_file_attributes", 0) & 0x400)


def validate(value, spec, label="arguments"):
    kind = spec.get("type")
    correct = {"string": lambda x: isinstance(x, str), "integer": lambda x: isinstance(x, int) and not isinstance(x, bool),
               "object": lambda x: isinstance(x, dict), "array": lambda x: isinstance(x, list)}
    if kind in correct and not correct[kind](value):
        raise ValueError(f"{label}: tipo {kind} richiesto.")
    if "enum" in spec and value not in spec["enum"]:
        raise ValueError(f"{label}: valore non ammesso.")
    if kind == "object":
        props = spec.get("properties", {})
        if spec.get("additionalProperties") is False and set(value) - set(props):
            raise ValueError(f"{label}: parametri sconosciuti.")
        if set(spec.get("required", [])) - set(value):
            raise ValueError(f"{label}: parametri mancanti.")
        for k, v in value.items():
            if k in props:
                validate(v, props[k], k)
    if kind == "array":
        if len(value) > 30:
            raise ValueError("Troppi elementi.")
        for item in value:
            validate(item, spec["items"], label)
    if isinstance(value, str) and len(value) > 200000:
        raise ValueError("Parametro troppo grande.")


def sensitive(path):
    p = Path(path)
    return (any(part.lower() in {".ssh", ".aws", ".azure", ".codex"} for part in p.parts)
            or p.name.lower() in {"credentials", "credentials.dpapi", "codex_data.json", "state.json", "id_rsa", "id_ed25519", ".netrc", ".npmrc", ".pypirc"}
            or p.name.lower().startswith(".env") or p.suffix.lower() in {".pem", ".key", ".pfx", ".p12"})


class ToolRunner:
    def __init__(self, store, settings, run_id, cancel, emit, approve, app_root, session):
        self.store, self.settings, self.run_id = store, settings, run_id
        self.cancel, self.emit, self.approve = cancel, emit, approve
        self.workspace = Path(settings["workspace"]).resolve()
        self.app_root = Path(app_root).resolve()
        self.session = session
        self.process = None

    def path(self, value):
        raw = Path(value)
        if os.name == "nt":
            if str(raw).startswith(("\\\\", "//")) or ":" in str(raw)[2:]:
                raise ValueError("Percorsi di rete, device e stream alternativi non ammessi.")
            if any(part.rstrip(" .") != part or part.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))} for part in raw.parts[1:]):
                raise ValueError("Nome file Windows non ammesso.")
        target = (raw if raw.is_absolute() else self.workspace / raw).resolve()
        if sensitive(target) or target.is_relative_to(self.store.root.resolve()):
            raise PermissionError("File di credenziali/dati privati protetto. Usa un file di esempio senza segreti.")
        return target

    def backup(self, path):
        if not path.is_file():
            return None
        if path.stat().st_size > 5_000_000:
            raise ValueError("File oltre il limite di backup (5 MB).")
        key = uuid.uuid4().hex
        folder = self.store.root / "backups"
        folder.mkdir(exist_ok=True)
        shutil.copy2(path, folder / key)
        (folder / (key + ".json")).write_text(json.dumps({"path": str(path), "run": self.run_id, "time": time.time()}), encoding="utf-8")
        return key

    def decision(self, name, args, paths):
        mode = self.settings["permission"]
        if name in {"web_search", "read_url", "github"} and not self.settings["network"]:
            raise PermissionError("Accesso online disattivato nelle impostazioni.")
        # A shell has unrestricted host privileges; with offline tools enabled it
        # could still reach the network. Refuse it unless network is enabled.
        if name == "exec_cmd" and not self.settings["network"]:
            raise PermissionError("Terminale disabilitato mentre la rete e' spenta: i comandi non sono isolati dal sistema.")
        outside = any(not p.is_relative_to(self.workspace) for p in paths)
        app_write = name in WRITE and any(p.is_relative_to(self.app_root) or ".git" in p.parts for p in paths)
        if mode == "full":
            return False, "Accesso completo"
        if mode == "always":
            return True, "Modalita': chiedi sempre"
        if outside:
            return True, "Accesso fuori dal progetto"
        if app_write:
            return True, "Modifica dell'app o dei metadati Git"
        if name in {"exec_cmd", "delete_file", "save_memory"}:
            return True, "Operazione che richiede conferma"
        if name == "github" and args["method"] != "GET":
            return True, "Pubblicazione/modifica su GitHub"
        if name in {"web_search", "read_url", "github"}:
            return True, "Invio dati a un servizio online"
        return False, "Operazione ammessa nel progetto"

    def preview(self, name, args, paths):
        result = {"tool": name, "arguments": args, "workspace": str(self.workspace)}
        if name in {"write_file", "edit_file"} and paths:
            if paths[0].exists() and paths[0].stat().st_size > 500000:
                raise ValueError("File troppo grande per l'anteprima (500 KB).")
            before = paths[0].read_text(encoding="utf-8") if paths[0].exists() else ""
            after = args["content"] if name == "write_file" else before.replace(args["old"], args["new"], 1)
            result["diff"] = "".join(difflib.unified_diff(before.splitlines(True), after.splitlines(True), fromfile=str(paths[0]), tofile=str(paths[0])))[:20000]
        return result

    def execute(self, name, args):
        digest = ""
        try:
            if name not in SPECS:
                raise ValueError(f"Strumento sconosciuto: {name}")
            validate(args, SPECS[name])
            paths = [self.path(args[k]) for k in ("path", "destination", "cwd") if k in args]
            needs, reason = self.decision(name, args, paths)
            digest = hashlib.sha256(json.dumps([name, args], sort_keys=True).encode()).hexdigest()
            if self.cancel.is_set():
                raise RuntimeError("Operazione interrotta.")
            if needs:
                before_hash = hashlib.sha256(paths[0].read_bytes()).hexdigest() if name in WRITE and paths and paths[0].is_file() else None
                preview = self.preview(name, args, paths)
                preview.update({"reason": reason, "digest": digest})
                if not self.approve(preview):
                    self.store.audit(self.run_id, name, "denied", digest)
                    return {"ok": False, "error": "L'utente ha negato l'azione. Non riproporla tramite altri strumenti."}
                if name in WRITE and paths:
                    after_hash = hashlib.sha256(paths[0].read_bytes()).hexdigest() if paths[0].is_file() else None
                    if before_hash != after_hash:
                        raise PermissionError("File cambiato durante l'approvazione: azione annullata.")
            if self.cancel.is_set():
                raise RuntimeError("Operazione interrotta.")
            # Resolve again after approval. Links or paths may have changed.
            new_paths = [self.path(args[k]) for k in ("path", "destination", "cwd") if k in args]
            if new_paths != paths:
                raise PermissionError("Percorso cambiato durante l'approvazione. Riprovare.")
            self.emit("tool_start", {"tool": name, "arguments": args, "reason": reason})
            result = getattr(self, "tool_" + name)(**args)
            self.store.audit(self.run_id, name, "completed", digest)
            self.emit("tool_result", {"tool": name, "result": result})
            return {"ok": True, "result": result}
        except Exception as e:
            self.store.audit(self.run_id, name, "failed", digest)
            result = {"ok": False, "error": str(e)[:2000]}
            self.emit("tool_result", {"tool": name, "result": result})
            return result

    def tool_list_dir(self, path="."):
        target = self.path(path)
        return [{"name": p.name, "kind": "link" if p.is_symlink() else "dir" if p.is_dir() else "file"}
                for p in sorted(target.iterdir(), key=lambda p: p.name.lower()) if not sensitive(p)][:500]

    def tool_read_file(self, path, start_line=1, end_line=300):
        target = self.path(path)
        if target.stat().st_size > 5_000_000:
            raise ValueError("File troppo grande (5 MB).")
        if start_line < 1 or end_line < start_line or end_line - start_line > 1000:
            raise ValueError("Intervallo di righe non valido (massimo 1001).")
        lines = target.read_text(encoding="utf-8").splitlines()
        return {"path": str(target), "total_lines": len(lines), "content": "\n".join(f"{i}: {line}" for i, line in enumerate(lines[start_line-1:end_line], start_line))[:30000]}

    def tool_search_files(self, query, path="."):
        if not query or len(query) > 500:
            raise ValueError("Testo di ricerca non valido.")
        found, scanned = [], 0
        for root, dirs, files in os.walk(self.path(path), followlinks=False):
            dirs[:] = [d for d in dirs if d not in SKIP and not linklike(Path(root, d))]
            for filename in files:
                if self.cancel.is_set():
                    return found
                p = Path(root, filename)
                scanned += 1
                if scanned > 5000:
                    return {"matches": found, "truncated": True}
                if sensitive(p) or p.is_symlink() or p.stat().st_size > 500000:
                    continue
                try:
                    safe = self.path(str(p))
                    for i, line in enumerate(safe.read_text(encoding="utf-8").splitlines(), 1):
                        if query.lower() in line.lower():
                            found.append({"path": str(p.relative_to(self.path(path))), "line": i, "text": line[:500]})
                            if len(found) >= 100:
                                return {"matches": found, "truncated": True}
                except (UnicodeError, PermissionError, OSError):
                    continue
        return {"matches": found, "truncated": False}

    def tool_write_file(self, path, content):
        target = self.path(path)
        backup = self.backup(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=target.parent, delete=False) as f:
            temp = Path(f.name)
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        try:
            os.replace(temp, target)
        finally:
            temp.unlink(missing_ok=True)
        return {"path": str(target), "bytes": len(content.encode()), "backup": backup}

    def tool_edit_file(self, path, old, new):
        target = self.path(path)
        if target.stat().st_size > 500000:
            raise ValueError("Usa un file sotto 500 KB per edit_file.")
        before = target.read_text(encoding="utf-8")
        if not old or before.count(old) != 1:
            raise ValueError("Il testo da sostituire deve comparire esattamente una volta.")
        return self.tool_write_file(path, before.replace(old, new, 1))

    def tool_make_dir(self, path):
        target = self.path(path)
        target.mkdir(parents=True, exist_ok=True)
        return str(target)

    def tool_move_file(self, path, destination):
        source, target = self.path(path), self.path(destination)
        if not source.is_file() or target.exists():
            raise ValueError("Serve un file sorgente e una destinazione libera.")
        backup = self.backup(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        source.rename(target)
        return {"path": str(target), "backup": backup}

    def tool_delete_file(self, path):
        target = self.path(path)
        if not target.is_file():
            raise ValueError("Sono eliminabili solo singoli file regolari.")
        backup = self.backup(target)
        target.unlink()
        return {"deleted": str(target), "backup": backup}

    def stop_process(self):
        proc = self.process
        if proc and proc.poll() is None:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True,
                               creationflags=subprocess.CREATE_NO_WINDOW, timeout=10)
            else:
                os.killpg(proc.pid, signal.SIGKILL)

    def run_process(self, argv, cwd, timeout):
        # Credential env vars are not inherited by the child shell.
        env = {k: v for k, v in os.environ.items() if not re.search(r"(?i)(token|secret|password|api_key|credential)", k)}
        kwargs = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {"start_new_session": True}
        with tempfile.TemporaryFile() as output:
            self.process = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                            stdout=output, stderr=subprocess.STDOUT, **kwargs)
            started = time.monotonic()
            timed_out = False
            try:
                while self.process.poll() is None:
                    if self.cancel.wait(.1) or time.monotonic() - started > timeout:
                        timed_out = not self.cancel.is_set()
                        self.stop_process()
                        break
                    if os.fstat(output.fileno()).st_size > 2_000_000:
                        self.stop_process()
                        raise ValueError("Output del comando oltre 2 MB: processo interrotto.")
                self.process.wait(timeout=10)
                output.seek(0)
                text = output.read(30000).decode("utf-8", errors="replace")
                return {"exit_code": self.process.returncode, "output": text,
                        "cancelled": self.cancel.is_set(), "timed_out": timed_out,
                        "truncated": os.fstat(output.fileno()).st_size > 30000}
            finally:
                self.stop_process()
                self.process = None

    def tool_exec_cmd(self, command, cwd=".", timeout=120):
        if not command.strip() or len(command) > 20000:
            raise ValueError("Comando vuoto o troppo lungo.")
        timeout = max(1, min(timeout, self.settings["command_timeout"], 600))
        argv = ["powershell", "-NoProfile", "-NonInteractive", "-Command", command] if os.name == "nt" else ["/bin/sh", "-c", command]
        return self.run_process(argv, self.path(cwd), timeout)

    def tool_git_status(self, view):
        options = {"status": ["status", "--short", "--branch"],
                   "diff": ["diff", "--no-ext-diff", "--no-textconv", "--", ".", ":(exclude)*.env*", ":(exclude)*.pem", ":(exclude)*.key", ":(exclude)*state.json", ":(exclude)*codex_data.json"],
                   "log": ["log", "-8", "--oneline", "--no-show-signature"]}
        # --no-optional-locks avoids refreshing the index for read-only status.
        argv = ["git", "--no-optional-locks", "-c", "core.fsmonitor=false", "-c", "core.pager=cat", *options[view]]
        return self.run_process(argv, self.workspace, 20)

    def tool_web_search(self, query):
        if not query.strip() or len(query) > 1000:
            raise ValueError("Query di ricerca vuota o troppo lunga.")
        providers = [("https://html.duckduckgo.com/html/?q=", ".result", ".result__a", ".result__snippet"),
                     ("https://www.bing.com/search?q=", "li.b_algo", "h2 a", ".b_caption p")]
        for base, selector, link_selector, snippet_selector in providers:
            try:
                response = public_request(base + quote(query), cancel=self.cancel)
                soup = BeautifulSoup(response["text"], "html.parser")
                results = []
                for item in soup.select(selector)[:8]:
                    link = item.select_one(link_selector)
                    snippet = item.select_one(snippet_selector)
                    if not link:
                        continue
                    href = link.get("href", "")
                    parameters = parse_qs(urlsplit(href).query)
                    href = parameters.get("uddg", [href])[0]
                    encoded = parameters.get("u", [""])[0]
                    if urlsplit(href).hostname == "www.bing.com" and encoded.startswith("a1"):
                        value = encoded[2:]
                        try:
                            href = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)).decode("utf-8")
                        except (ValueError, UnicodeError):
                            pass
                    if urlsplit(href).scheme in {"http", "https"}:
                        results.append({"title": link.get_text(" ", strip=True), "url": href,
                                        "snippet": snippet.get_text(" ", strip=True) if snippet else ""})
                if results:
                    return results
            except Exception:
                if self.cancel.is_set():
                    raise
        return {"results": [], "notice": "Nessun risultato o motori temporaneamente bloccati. Prova una URL diretta."}

    def tool_read_url(self, url):
        response = public_request(url, cancel=self.cancel)
        if not any(t in response["content_type"] for t in ("text/", "json", "xml")):
            raise ValueError("Formato non testuale: usa il terminale autorizzato per gestire il download.")
        soup = BeautifulSoup(response["text"], "html.parser")
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()
        return {"url": response["url"], "content": soup.get_text("\n", strip=True)[:25000], "untrusted": True}

    def tool_github(self, method, endpoint, body=None):
        repo = self.settings.get("github_repo", "")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
            raise ValueError("Imposta prima il repository GitHub owner/repo.")
        if not re.fullmatch(r"(?:issues|pulls|contents|commits|branches|releases)(?:/[A-Za-z0-9_.~/-]+)?(?:\?[A-Za-z0-9_=&%.-]+)?", endpoint) or ".." in endpoint:
            raise ValueError("Endpoint GitHub non ammesso.")
        token = self.store.vault.get("github")
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if token:
            headers["Authorization"] = "Bearer " + token
        if method != "GET" and not token:
            raise ValueError("Token GitHub mancante: salvalo nelle impostazioni.")
        response = public_request(f"https://api.github.com/repos/{repo}/{endpoint}", method, body, headers, cancel=self.cancel)
        data = json.loads(response["text"])
        return data if len(response["text"]) < 25000 else {"content": response["text"][:25000], "truncated": True}

    def tool_update_plan(self, steps):
        with self.store.lock:
            self.session["plan"] = steps
            self.store.save()
        self.emit("plan", {"steps": steps})
        return steps

    def tool_save_memory(self, text):
        from .storage import redact
        if redact(text, [self.store.vault.get("provider"), self.store.vault.get("github")]) != text:
            raise ValueError("Non salvare credenziali in memoria.")
        with self.store.lock:
            self.store.data["memory"] = (self.store.data.get("memory", "") + "\n" + text)[-10000:]
            self.store.save()
        return "Preferenza salvata localmente."
