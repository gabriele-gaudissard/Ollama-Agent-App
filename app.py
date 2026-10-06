import os
import sys
import subprocess
import requests
import urllib.parse
import webview
import json
import webbrowser
from html.parser import HTMLParser

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "codex_data.json")

def load_db():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f: return json.load(f)
        except: pass
    return {"memory": "", "sessions": [], "settings": {"lang": "it", "url": "http://localhost:11434", "token": "", "model": "qwen2.5-coder:14b"}}

def save_db(data):
    with open(DATA_FILE, 'w') as f: json.dump(data, f, indent=2)

class AgentAPI:
    def __init__(self):
        self._window = None
        self.stop_flag = False
        self.db = load_db()
        if "settings" not in self.db:
            self.db["settings"] = {"lang": "it", "url": "http://localhost:11434", "token": "", "model": "qwen2.5-coder:14b"}
        if "model" not in self.db["settings"]:
            self.db["settings"]["model"] = "qwen2.5-coder:14b"
        self.current_cwd = os.getcwd()

    def set_window(self, window):
        self._window = window

    def stop_generation(self):
        self.stop_flag = True
        return "Generation stopped by user."

    def open_external_url(self, url):
        """Apre un URL nel browser predefinito del sistema operativo."""
        try:
            webbrowser.open(url)
            return True
        except: return False

    # --- SETTINGS E OLLAMA CONFIG ---
    def get_settings(self): return self.db.get("settings", {})
    
    def save_settings(self, lang, url, token, model):
        self.db["settings"] = {"lang": lang, "url": url, "token": token, "model": model}
        save_db(self.db)
        return "Settings saved."

    def _get_ollama_config(self):
        s = self.db.get("settings", {})
        base_url = s.get("url", "http://localhost:11434").rstrip('/')
        token = s.get("token", "").strip()
        headers = {}
        if token: headers["Authorization"] = f"Bearer {token}"
        return base_url, headers

    # --- GESTIONE MODELLI OLLAMA (API) ---
    def get_models(self):
        base_url, headers = self._get_ollama_config()
        try:
            res = requests.get(f"{base_url}/api/tags", headers=headers, timeout=5)
            if res.status_code == 200:
                models = [m["name"] for m in res.json().get("models", [])]
                return {"success": True, "models": models}
            return {"success": False, "error": f"HTTP {res.status_code}"}
        except Exception: return {"success": False, "error": "Cannot connect to Ollama."}

    def delete_model(self, model_name):
        base_url, headers = self._get_ollama_config()
        try:
            res = requests.delete(f"{base_url}/api/delete", headers=headers, json={"name": model_name}, timeout=10)
            if res.status_code == 200: return {"success": True}
            return {"success": False, "error": f"HTTP {res.status_code}: {res.text}"}
        except Exception as e: return {"success": False, "error": str(e)}

    def pull_model(self, model_name):
        base_url, headers = self._get_ollama_config()
        try:
            res = requests.post(f"{base_url}/api/pull", headers=headers, json={"name": model_name}, stream=True)
            for line in res.iter_lines():
                if line:
                    data = json.loads(line)
                    status = data.get("status", "Downloading...")
                    self._window.evaluate_js(f"window.updatePullProgress({json.dumps(status)})")
            return {"success": True}
        except Exception as e: return {"success": False, "error": str(e)}

    # --- SESSIONI E MEMORIA ---
    def get_sessions(self): return self.db.get("sessions", [])
    
    def save_session(self, session_id, title, history):
        sessions = self.db.get("sessions", [])
        for s in sessions:
            if s["id"] == session_id:
                s["history"] = history
                s["title"] = title
                save_db(self.db)
                return
        sessions.insert(0, {"id": session_id, "title": title, "history": history})
        self.db["sessions"] = sessions
        save_db(self.db)

    def delete_session(self, session_id):
        self.db["sessions"] = [s for s in self.db.get("sessions", []) if s["id"] != session_id]
        save_db(self.db)

    def rename_session(self, session_id, new_title):
        for s in self.db.get("sessions", []):
            if s["id"] == session_id:
                s["title"] = new_title
                save_db(self.db)
                return True
        return False

    def save_memory(self, text):
        self.db["memory"] = self.db.get("memory", "") + f"\n- {text}"
        save_db(self.db)
        return "[MEMORY] Information registered permanently."

    # --- TOOLS DI SISTEMA ---
    def select_file(self):
        if not self._window: return None
        result = self._window.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=False)
        if result and len(result) > 0:
            with open(result[0], 'r', encoding='utf-8', errors='ignore') as f: return {"success": True, "name": os.path.basename(result[0]), "content": f.read()}
        return None

    def execute_terminal(self, command):
        try:
            hooked_cmd = f"{command}\nWrite-Output '---CWD_HOOK---'\n(Get-Location).Path"
            res = subprocess.run(["powershell", "-NoProfile", "-Command", hooked_cmd], capture_output=True, text=True, timeout=120, cwd=self.current_cwd)
            stdout_parts = res.stdout.split('---CWD_HOOK---')
            out_text = stdout_parts[0].strip() if len(stdout_parts) > 0 else ""
            if len(stdout_parts) > 1:
                new_cwd = stdout_parts[1].strip()
                if os.path.exists(new_cwd): self.current_cwd = new_cwd
            final_output = out_text
            if res.stderr.strip(): final_output += f"\n[ERROR/WARNING]:\n{res.stderr.strip()}"
            return final_output if final_output else "[Command executed without console output]"
        except Exception as e: return f"[TERMINAL EXCEPTION]: {str(e)}"

    def get_cwd(self): return self.current_cwd

    def create_or_update_file(self, filename, content):
        try:
            target = os.path.abspath(os.path.join(self.current_cwd, filename))
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, 'w', encoding='utf-8') as f: f.write(content)
            return f"[SUCCESS] File saved: {target}"
        except Exception as e: return f"[SAVE ERROR]: {str(e)}"

    def read_file_disk(self, filepath):
        try:
            target = os.path.abspath(os.path.join(self.current_cwd, filepath))
            with open(target, 'r', encoding='utf-8', errors='ignore') as f: return f"CONTENT OF {target}:\n" + f.read()
        except Exception as e: return f"[FILE READ ERROR]: {str(e)}"

    def list_dir(self, path="."):
        try:
            target = os.path.abspath(os.path.join(self.current_cwd, path))
            return f"DIRECTORY CONTENT {target}:\n" + "\n".join(os.listdir(target))
        except Exception as e: return f"[DIRECTORY ERROR]: {str(e)}"

    def web_search(self, query):
        try:
            url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
            headers = {"User-Agent": "Mozilla/5.0"}
            res = requests.get(url, headers=headers, timeout=10)
            class Extractor(HTMLParser):
                def __init__(self):
                    super().__init__(); self.text = []; self.in_snip = False
                def handle_starttag(self, tag, attrs):
                    if tag == 'a' and dict(attrs).get('class') == 'result__snippet': self.in_snip = True
                def handle_endtag(self, tag):
                    if tag == 'a': self.in_snip = False
                def handle_data(self, data):
                    if self.in_snip: self.text.append(data.strip())
            p = Extractor(); p.feed(res.text)
            results = "\n- ".join([t for t in p.text if t][:6])
            return f"[WEB RESULTS FOR '{query}']:\n- {results}" if results else "No relevant results found."
        except Exception as e: return f"[WEB SEARCH ERROR]: {str(e)}"

    def read_url(self, url):
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            res = requests.get(url, headers=headers, timeout=15)
            if BeautifulSoup:
                soup = BeautifulSoup(res.text, 'html.parser')
                for script in soup(["script", "style", "nav", "footer"]): script.extract()
                return soup.get_text(separator='\n', strip=True)[:15000]
            return "BeautifulSoup not installed. Cannot parse URL."
        except Exception as e: return f"[URL READ ERROR]: {str(e)}"

    # --- LLM ENGINE ---
    def chat_stream(self, messages_json, msg_id):
        self.stop_flag = False
        memory_context = self.db.get("memory", "")
        
        s = self.db.get("settings", {})
        lang = s.get("lang", "en")
        active_model = s.get("model", "qwen2.5-coder:14b")
        
        system_prompt = {
            "role": "system",
            "content": (
                f"YOU ARE 'CODEX', AN AUTONOMOUS SOFTWARE AGENT. YOU MUST REASON AND RESPOND IN THIS LANGUAGE: {lang.upper()}.\n"
                f"LONG-TERM MEMORY:\n{memory_context if memory_context else 'Empty.'}\n"
                f"CURRENT WORKING DIRECTORY (CWD): {self.current_cwd}\n\n"
                "ARCHITECTURAL RULES:\n"
                "1. Use the exact markdown blocks to execute actions. Execute immediately without asking permission.\n"
                "2. Read files or web docs before drawing conclusions.\n\n"
                "AVAILABLE TOOLS:\n"
                "```exec_cmd\n<powershell or git command>\n```\n"
                "```create_file:filename.ext\n<exact content>\n```\n"
                "```read_file:filename.ext\n```\n"
                "```list_dir:path\n```\n"
                "```web_search:query\n```\n"
                "```read_url:https://link...\n```\n"
                "```save_memory:information to remember\n```"
            )
        }
        
        base_url, headers = self._get_ollama_config()
        try:
            r = requests.post(f"{base_url}/api/chat", headers=headers, json={"model": active_model, "messages": [system_prompt] + messages_json, "stream": True}, stream=True, timeout=120)
            if r.status_code != 200:
                err = f"API Error ({r.status_code}). Model '{active_model}' might not be installed."
                self._window.evaluate_js(f"appendStream('{msg_id}', {json.dumps(err)})"); self._window.evaluate_js(f"finalizeStream('{msg_id}')")
                return err
            full_text = ""
            for line in r.iter_lines():
                if self.stop_flag: break
                if line:
                    chunk = json.loads(line).get("message", {}).get("content", "")
                    full_text += chunk
                    self._window.evaluate_js(f"appendStream('{msg_id}', {json.dumps(chunk)})")
            self._window.evaluate_js(f"finalizeStream('{msg_id}')")
            return full_text
        except Exception as e:
            err = f"Connection Error: {str(e)}"
            self._window.evaluate_js(f"appendStream('{msg_id}', {json.dumps(err)})"); self._window.evaluate_js(f"finalizeStream('{msg_id}')")
            return err

if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    window = webview.create_window("Codex Professional Agent", url=os.path.join(current_dir, "index.html"), js_api=AgentAPI(), width=1400, height=900, resizable=True, text_select=True)
    window._js_api.set_window(window)
    webview.start(debug=False)