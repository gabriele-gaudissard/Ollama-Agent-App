"""Bounded public HTTP with DNS-pinned connections and redirect checks."""
import http.client
import ipaddress
import json
import socket
import ssl
from urllib.parse import urljoin, urlsplit


def public_target(url):
    p = urlsplit(url)
    if p.scheme not in ("http", "https") or not p.hostname or p.username or p.password:
        raise ValueError("Sono ammessi solo URL HTTP(S) senza credenziali.")
    port = p.port or (443 if p.scheme == "https" else 80)
    if port != (443 if p.scheme == "https" else 80):
        raise ValueError("Porta web non ammessa.")
    addresses = sorted({row[4][0] for row in socket.getaddrinfo(p.hostname, port, type=socket.SOCK_STREAM)})
    if not addresses or any(not ipaddress.ip_address(ip).is_global or ipaddress.ip_address(ip).is_multicast or ipaddress.ip_address(ip).is_reserved for ip in addresses):
        raise ValueError("Rete privata, loopback o indirizzo riservato bloccato.")
    return p, port, addresses[0]


class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host, port, address):
        super().__init__(host, port, timeout=15, context=ssl.create_default_context())
        self.address = address

    def connect(self):
        raw = socket.create_connection((self.address, self.port), self.timeout)
        try:
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except Exception:
            raw.close()
            raise


def public_request(url, method="GET", body=None, headers=None, limit=1_000_000, cancel=None):
    for _ in range(6):
        if cancel and cancel.is_set():
            raise RuntimeError("Operazione interrotta.")
        parsed, port, address = public_target(url)
        if parsed.scheme == "https":
            conn = PinnedHTTPS(parsed.hostname, port, address)
        else:
            conn = http.client.HTTPConnection(address, port, timeout=15)
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query
        request_headers = {"User-Agent": "Veynuq/4.0", "Host": parsed.hostname, **(headers or {})}
        payload = json.dumps(body).encode() if body is not None else None
        if payload:
            request_headers["Content-Type"] = "application/json"
        try:
            conn.request(method, path, body=payload, headers=request_headers)
            r = conn.getresponse()
            if r.status in (301, 302, 303, 307, 308):
                next_url = urljoin(url, r.getheader("Location", ""))
                if headers and "Authorization" in headers:
                    # Never forward an authenticated request through redirects.
                    raise ValueError("Redirect autenticato bloccato.")
                if parsed.scheme == "https" and urlsplit(next_url).scheme != "https":
                    raise ValueError("Redirect HTTPS verso HTTP bloccato.")
                url = next_url
                continue
            chunks, total = [], 0
            while True:
                if cancel and cancel.is_set():
                    raise RuntimeError("Operazione interrotta.")
                block = r.read(min(65536, limit + 1 - total))
                if not block:
                    break
                chunks.append(block)
                total += len(block)
                if total > limit:
                    raise ValueError("Risposta web troppo grande.")
            raw_data = b"".join(chunks)
            text = raw_data.decode("utf-8", errors="replace")
            if r.status >= 400:
                raise RuntimeError(f"HTTP {r.status}: {text[:500]}")
            return {"url": url, "status": r.status, "text": text, "data": raw_data,
                    "content_type": r.getheader("Content-Type", "")}
        finally:
            conn.close()
    raise ValueError("Troppi redirect.")
