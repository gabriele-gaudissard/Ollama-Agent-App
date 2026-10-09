"""Windows desktop tools bound to inspected windows and short-lived snapshots."""
import ctypes
import os
import re
import sys
import threading
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
        self._com_thread = None

    def desktop(self):
        if os.name != "nt":
            raise RuntimeError("Desktop control is available on Windows only.")
        owner = threading.get_ident()
        if self._com_thread is None:
            # UI Automation requires COM on every worker thread, including
            # later conversations after pywinauto has already been imported.
            result = ctypes.windll.ole32.CoInitializeEx(None, 0)
            if result not in (0, 1):
                raise RuntimeError('Cannot initialize Windows desktop control on this worker thread.')
            self._com_thread = owner
            sys.coinit_flags = 0
        elif self._com_thread != owner:
            raise RuntimeError('Desktop observations belong to a different worker. Inspect again in the current activity.')
        from pywinauto import Desktop
        return Desktop(backend="uia")

    def close(self):
        if self._com_thread == threading.get_ident():
            self.snapshots.clear()
            ctypes.windll.ole32.CoUninitialize()
            self._com_thread = None

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

    @staticmethod
    def editable(element):
        kind = element.element_info.control_type
        if kind not in {'Edit', 'Document'}: return False
        try:
            readonly = element.iface_value.CurrentIsReadOnly
            if isinstance(readonly, (bool, int)): return not readonly
        except Exception: pass
        if kind == 'Document':
            try:
                readonly = element.iface_text.DocumentRange.GetAttributeValue(40015)  # UIA_IsReadOnlyAttributeId
                return isinstance(readonly, (bool, int)) and not readonly
            except Exception: return False
        return True

    def inspect(self, window_id, screenshot=False):
        window = self.target(window_id)
        elements = []
        saved = []
        pending = deque([(window, 0)])
        inspected = 0
        while pending and inspected < 800:
            element, depth = pending.popleft()
            inspected += 1
            try:
                if depth < 24 and len(pending) < 800:
                    pending.extend((child, depth + 1) for child in element.children()[:800 - len(pending)])
                if not element.is_visible() or self.password(element):
                    continue
                rect = element.rectangle()
                if len(saved) >= 300:
                    continue
                index = len(saved)
                saved.append((element, self.signature(element)))
                elements.append({"index": index, "type": element.element_info.control_type,
                                 "name": element.window_text()[:500], "enabled": element.is_enabled(),
                                 "rect": [rect.left, rect.top, rect.right, rect.bottom]})
            except Exception:
                continue
        token = uuid.uuid4().hex
        rect = window.rectangle()
        self.snapshots = {token: {"window_id": window_id, "pid": window.process_id(), "time": time.monotonic(), "elements": saved,
                                  "rect": [rect.left, rect.top, rect.right, rect.bottom]}}
        result = {"window_id": window_id, "snapshot_id": token, "elements": elements,
                  "window_rect": [rect.left, rect.top, rect.right, rect.bottom],
                  "editable_indexes": [i for i, (e, _) in enumerate(saved) if e.is_enabled() and self.editable(e)],
                  "truncated": bool(pending) or len(saved) >= 300,
                  "note": "Use these element indexes; type only into editable_indexes. Re-inspect after every successful action. If the tree is truncated, focus a relevant pane or use browser tools for websites. An older snapshot can be refreshed only if the same live control identity is verified."}
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

    def checked_element(self, snapshot_id, index):
        snapshot = self.snapshots.get(snapshot_id)
        if not snapshot:
            raise ValueError("Snapshot already used or unavailable. Call computer_inspect again; use its new snapshot_id and indexes.")
        window = self.target(snapshot["window_id"])
        if window.process_id() != snapshot["pid"] or type(index) is not int or not 0 <= index < len(snapshot["elements"]):
            raise ValueError("Window or element changed. Inspect again.")
        element, signature = snapshot["elements"][index]
        if self.signature(element) != signature or not element.is_visible() or not element.is_enabled() or self.password(element):
            raise ValueError("Element changed or is protected. Inspect again.")
        refreshed = time.monotonic() - snapshot["time"] > 120
        if refreshed:
            # Fresh native reads verified the same process and exact control,
            # rather than reusing an old index against an unrelated new view.
            snapshot['time'] = time.monotonic()
        return snapshot, window, element, refreshed

    def action(self, snapshot_id, index, action, text=""):
        if action == 'click':
            return self.pointer(snapshot_id, index, 'click')
        snapshot, window, element, refreshed = self.checked_element(snapshot_id, index)
        if action == 'type' and (not self.editable(element) or not text or len(text) > 20000):
            editable = [i for i, (e, _) in enumerate(snapshot['elements']) if self.editable(e) and e.is_visible() and e.is_enabled() and not self.password(e)]
            raise ValueError('Typing requires an Edit/Document and 1–20000 literal characters. Editable indexes: ' + str(editable) + '. This snapshot remains available; choose one of those indexes.')
        if action not in {'click', 'type', 'key'}:
            raise ValueError('Allowed desktop actions: click, type, key.')
        if action == "type":
            window.set_focus()
            element.set_focus()
            self.verify_focus(getattr(element.element_info, 'process_id', None) or window.process_id())
            from pywinauto.keyboard import send_keys
            literal = "".join("{" + c + "}" if c in "+^%~(){}" else c for c in text)
            self.snapshots.pop(snapshot_id, None)
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
            window.set_focus()
            element.set_focus()
            self.verify_focus(getattr(element.element_info, 'process_id', None) or window.process_id())
            self.snapshots.pop(snapshot_id, None)
            send_keys("".join(modifiers[p] for p in parts[:-1]) + suffix)
        else:
            raise ValueError("Allowed desktop actions: click, type, key.")
        return {"performed": action, "window_id": snapshot["window_id"], "snapshot_refreshed": refreshed, "note": "Re-inspect the window to verify the result."}

    def pointer(self, snapshot_id, index, action, x=None, y=None, end_x=None, end_y=None, delta=0):
        snapshot, window, element, refreshed = self.checked_element(snapshot_id, index)
        rect, control = window.rectangle(), element.rectangle()
        current_rect = [rect.left, rect.top, rect.right, rect.bottom]
        if snapshot.get('rect') != current_rect:
            raise ValueError('Window moved or resized. Inspect again before using mouse coordinates.')
        if (x is None) != (y is None):
            raise ValueError('Supply both x and y, or neither to use the element center.')
        point = ((control.left+control.right)//2, (control.top+control.bottom)//2) if x is None else (rect.left+x, rect.top+y)
        if not (control.left <= point[0] < control.right and control.top <= point[1] < control.bottom):
            raise ValueError('Mouse point must be inside the selected inspected control.')
        end = None
        if action == 'drag':
            if end_x is None or end_y is None or not (0 <= end_x < rect.right-rect.left and 0 <= end_y < rect.bottom-rect.top):
                raise ValueError('Drag destination must be inside the inspected window.')
            end = (rect.left+end_x, rect.top+end_y)
        if action == 'scroll' and (type(delta) is not int or not -10 <= delta <= 10 or not delta):
            raise ValueError('Scroll delta must be a nonzero integer from -10 to 10.')
        if action not in {'click', 'double_click', 'right_click', 'move', 'scroll', 'drag'}:
            raise ValueError('Invalid mouse action.')
        window.set_focus()
        # Hit-test the actual native point after focusing. This catches protected
        # children and other windows covering an inspected container.
        for p in [point, end]:
            if p is None: continue
            hit = self.desktop().from_point(*p)
            if hit.top_level_parent().handle != window.handle or self.password(hit):
                raise PermissionError('Mouse point is outside the selected window or on a protected password control.')
        from pywinauto import mouse
        self.snapshots.pop(snapshot_id, None)
        if action in {'click', 'right_click'}:
            mouse.click(button='right' if action == 'right_click' else 'left', coords=point)
        elif action == 'double_click': mouse.double_click(coords=point)
        elif action == 'move': mouse.move(coords=point)
        elif action == 'scroll': mouse.scroll(coords=point, wheel_dist=delta)
        else:
            mouse.press(coords=point)
            try: mouse.move(coords=end)
            finally: mouse.release(coords=end)
        return {'performed': action, 'window_id': snapshot['window_id'], 'snapshot_refreshed': refreshed, 'note': 'Re-inspect to verify the result.'}

    @staticmethod
    def verify_focus(expected_pid):
        from pywinauto.uia_defines import IUIA
        focused = IUIA().iuia.GetFocusedElement()
        if focused.CurrentProcessId != expected_pid or focused.CurrentIsPassword:
            raise PermissionError("Keyboard focus changed or is a protected password field. Inspect again.")
