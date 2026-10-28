"""Local HTTP API used by the browser extension (127.0.0.1 only).

Only requests from browser extensions (or local programs) are accepted: requests carrying a web
page Origin are refused, and POSTs must carry the custom X-Fetchly-Client header, which ordinary web
pages cannot send cross-origin without a CORS preflight that this server never approves.
"""
import json
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .config import VERSION

EXT_ORIGINS = ("chrome-extension://", "moz-extension://", "extension://", "safari-web-extension://")


def make_handler(manager):
    class Handler(BaseHTTPRequestHandler):
        server_version = f"Fetchly/{VERSION}"

        def log_message(self, *args):
            pass

        def _origin_ok(self):
            origin = self.headers.get("Origin", "")
            return not origin or origin.startswith(EXT_ORIGINS)

        def _json(self, code, obj):
            body = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self):
            self.send_response(403)
            self.end_headers()

        def do_GET(self):
            if not self._origin_ok():
                return self._json(403, {"error": "forbidden"})
            path = urllib.parse.urlsplit(self.path).path
            if path == "/ping":
                s = manager.settings
                if self.headers.get("Origin", "").startswith(EXT_ORIGINS):
                    import time
                    manager.extension_seen = time.time()
                    ua = self.headers.get("User-Agent", "")
                    manager.extension_browser = ("Edge" if "Edg/" in ua else "Opera" if "OPR/" in ua else
                                                 "Brave" if "Brave" in ua else "Chrome")
                return self._json(200, {"app": "Fetchly", "version": VERSION, "enabled": s.browser_integration,
                                        "types": s.intercept_types, "minSizeKB": s.min_intercept_kb})
            self._json(404, {"error": "not found"})

        def do_POST(self):
            if not self._origin_ok() or self.headers.get("X-Fetchly-Client") != "extension":
                return self._json(403, {"error": "forbidden"})
            try:
                n = int(self.headers.get("Content-Length", "0"))
                data = json.loads(self.rfile.read(min(n, 5_000_000)) or b"{}")
            except (ValueError, OSError):
                return self._json(400, {"error": "bad request"})
            path = urllib.parse.urlsplit(self.path).path
            if path == "/download":
                url = str(data.get("url", ""))
                if not url.lower().startswith(("http://", "https://")):
                    return self._json(400, {"error": "unsupported url"})
                manager.events.put(("catch", data))
                return self._json(200, {"ok": True})
            if path == "/batch":
                links = [l for l in data.get("links", []) if str(l.get("url", "")).lower().startswith("http")]
                manager.events.put(("catch_batch", {**data, "links": links}))
                return self._json(200, {"ok": True, "count": len(links)})
            if path == "/show":
                manager.events.put(("show",))
                return self._json(200, {"ok": True})
            self._json(404, {"error": "not found"})

    return Handler


class ApiServer:
    def __init__(self, manager, port):
        self.manager = manager
        self.port = port
        self.httpd = None
        self.thread = None

    def start(self):
        """Raises OSError if the port is taken (usually: Fetchly is already running)."""
        self.httpd = ThreadingHTTPServer(("127.0.0.1", self.port), make_handler(self.manager))
        self.httpd.daemon_threads = True
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True, name="fetchly-api")
        self.thread.start()

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None


def notify_running_instance(port, payload=None):
    """Ask an already running Fetchly to show itself (or catch a URL). Returns True if it answered."""
    import urllib.request
    path, body = ("/download", payload) if payload else ("/show", {})
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "X-Fetchly-Client": "extension"})
    try:
        with urllib.request.urlopen(req, timeout=2) as r:
            return r.status == 200
    except OSError:
        return False
