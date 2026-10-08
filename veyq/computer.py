"""Windows desktop tools bound to inspected windows and short-lived snapshots."""
import ctypes
import os
import re
import time
import uuid
from collections import deque
from pathlib import Path

BLOCKED = {"lsass.exe", "logonui.exe", "lockapp.exe", "credentialuibroker.exe", "securityhealthsystray.exe",
           "sechealthui.exe", "consent.exe", "keepass.exe", "keepassxc.exe", "1password.exe", "bitwarden.exe",
           "cmd.exe", "powershell.exe", "pwsh.exe", "windowsterminal.exe", "conhost.exe"}


def process_name(pid):
    kernel = ctypes.windll.kernel32
    kernel.OpenProcess.restype = ctypes.c_void_p
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        raise PermissionError("Cannot inspect this Windows process.")
    try:
        size = ctypes.c_ulong(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if not kernel.QueryFullProcessImageNameW(ctypes.c_void_p(handle), 0, buffer, ctypes.byref(size)):
            raise PermissionError("Cannot identify the target application.")
        return Path(buffer.value).name.lower()
    finally:
        kernel.CloseHandle(ctypes.c_void_p(handle))


class Computer:
    def __init__(self, data_root):
        self.data_root = Path(data_root)
        self.snapshots = {}

    def desktop(self):
        if os.name != "nt":
            raise RuntimeError("Desktop control is available on Windows only.")
        from pywinauto import Desktop
        return Desktop(backend="uia")

    def target(self, handle):
        if type(handle) is not int or handle <= 0:
            raise ValueError("Use a window_id returned by computer_windows.")
        window = self.desktop().window(handle=handle).wrapper_object()
        pid = window.process_id()
        if pid == os.getpid() or window.window_text().startswith("Veynuq") or process_name(pid) in BLOCKED:
            raise PermissionError("This application's controls are protected. Use exec_cmd for terminal commands; Veynuq cannot approve its own actions.")
        if not window.is_visible():
            raise ValueError("Window is not visible. Inspect a currently open window.")
        return window

    def windows(self):
        result = []
        for window in self.desktop().windows(visible_only=True):
            try:
                safe = self.target(window.handle)
                title = safe.window_text()
                if title:
                    result.append({"window_id": safe.handle, "title": title[:200], "application": process_name(safe.process_id())})
            except (OSError, RuntimeError, PermissionError, ValueError):
                continue
        return result[:100]

    @staticmethod
    def password(element):
        try:
            return bool(element.element_info.element.CurrentIsPassword)
        except Exception:
            # Elements without editable values can lack this property.
            return element.element_info.control_type == "Edit"

    @staticmethod
    def signature(element):
        info = element.element_info
        return (tuple(info.runtime_id), info.control_type, info.name)

    def inspect(self, window_id, screenshot=False):
        window = self.target(window_id)
        elements = []
        saved = []
        pending = deque([(window, 0)])
        inspected = 0
        while pending and inspected < 300:
            element, depth = pending.popleft()
            inspected += 1
            try:
                if depth < 7 and len(pending) < 300:
                    pending.extend((child, depth + 1) for child in element.children()[:300 - len(pending)])
                if not element.is_visible() or self.password(element):
                    continue
                rect = element.rectangle()
                index = len(saved)
                saved.append((element, self.signature(element)))
                elements.append({"index": index, "type": element.element_info.control_type,
                                 "name": element.window_text()[:500], "enabled": element.is_enabled(),
                                 "rect": [rect.left, rect.top, rect.right, rect.bottom]})
            except Exception:
                continue
        token = uuid.uuid4().hex
        self.snapshots = {token: {"window_id": window_id, "pid": window.process_id(), "time": time.monotonic(), "elements": saved}}
        result = {"window_id": window_id, "snapshot_id": token, "elements": elements,
                  "note": "Use element indexes from this snapshot. Re-inspect after every action; snapshots expire after 120 seconds."}
        if screenshot:
            folder = self.data_root / "computer-observations"
            folder.mkdir(exist_ok=True)
            path = folder / (token + ".png")
            image = window.capture_as_image()
            if image is None:
                raise RuntimeError("Window capture is unavailable.")
            image.thumbnail((1600, 1000))
            image.save(path, format="PNG")
            result["image_path"] = str(path)
        return result

    def action(self, snapshot_id, index, action, text=""):
        snapshot = self.snapshots.pop(snapshot_id, None)
        if not snapshot or time.monotonic() - snapshot["time"] > 120:
            raise ValueError("Desktop snapshot expired. Inspect the window again.")
        window = self.target(snapshot["window_id"])
        if window.process_id() != snapshot["pid"] or type(index) is not int or not 0 <= index < len(snapshot["elements"]):
            raise ValueError("Window or element changed. Inspect again.")
        element, signature = snapshot["elements"][index]
        if self.signature(element) != signature or not element.is_visible() or not element.is_enabled() or self.password(element):
            raise ValueError("Element changed or is protected. Inspect again.")
        window.set_focus()
        if action == "click":
            element.click_input()
        elif action == "type":
            if element.element_info.control_type not in {"Edit", "Document"} or not text or len(text) > 20000:
                raise ValueError("Select an editable element and provide 1–20000 literal characters.")
            element.set_focus()
            self.verify_focus(window.process_id())
            from pywinauto.keyboard import send_keys
            literal = "".join("{" + c + "}" if c in "+^%~(){}" else c for c in text)
            send_keys(literal, with_spaces=True, with_tabs=True, with_newlines=True, vk_packet=True)
        elif action == "key":
            from pywinauto.keyboard import send_keys
            parts = text.upper().split("+")
            modifiers = {"CTRL": "^", "ALT": "%", "SHIFT": "+"}
            names = {"ENTER": "ENTER", "ESC": "ESC", "TAB": "TAB", "BACKSPACE": "BACKSPACE", "DELETE": "DELETE",
                     "UP": "UP", "DOWN": "DOWN", "LEFT": "LEFT", "RIGHT": "RIGHT", "HOME": "HOME", "END": "END", "PAGEUP": "PGUP", "PAGEDOWN": "PGDN"}
            if any(p not in modifiers for p in parts[:-1]) or len(parts) > 4:
                raise ValueError("Invalid shortcut modifiers.")
            key = parts[-1]
            if re.fullmatch(r"[A-Z0-9]", key):
                suffix = key.lower()
            elif key in names or re.fullmatch(r"F(?:[1-9]|1[0-2])", key):
                suffix = "{" + names.get(key, key) + "}"
            else:
                raise ValueError("Use a letter, digit, navigation key or F1–F12.")
            element.set_focus()
            self.verify_focus(window.process_id())
            send_keys("".join(modifiers[p] for p in parts[:-1]) + suffix)
        else:
            raise ValueError("Allowed desktop actions: click, type, key.")
        return {"performed": action, "window_id": snapshot["window_id"], "note": "Re-inspect the window to verify the result."}

    @staticmethod
    def verify_focus(expected_pid):
        from pywinauto.uia_defines import IUIA
        focused = IUIA().iuia.GetFocusedElement()
        if focused.CurrentProcessId != expected_pid or focused.CurrentIsPassword:
            raise PermissionError("Keyboard focus changed or is a protected password field. Inspect again.")
