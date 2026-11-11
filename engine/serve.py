"""Read-only, loopback-only serving of generated report artifacts.

Only report HTML/JSON and PNG images are exposed, never directory listings,
hidden files, links, credentials or arbitrary store files. A small private
registry permits CLI and Hermes processes to discover a live server.
"""

import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import subprocess
import threading
from urllib.parse import quote, unquote, urlsplit

REGISTRY = ".orphic-server.json"


def default_store():
    try:
        from hermes_constants import get_hermes_home
    except ImportError:
        home = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
    else:
        home = Path(get_hermes_home())
    return home.expanduser().resolve() / "orphic-eyes"


def _artifact(root, relative):
    parts = Path(relative).parts
    if not parts or any(part in (".", "..") or part.startswith(".") or ":" in part for part in parts):
        raise ValueError("Report path is not allowed")
    path = root.joinpath(*parts)
    if path.name not in ("report.html", "report.json") and path.suffix.lower() != ".png":
        raise ValueError("Only generated reports and PNG images are served")
    for index in range(1, len(parts) + 1):
        if root.joinpath(*parts[:index]).is_symlink():
            raise ValueError("Linked report paths are not served")
    if (not path.resolve().is_relative_to(root) or not path.is_file() or path.stat().st_nlink != 1):
        raise ValueError("Report file is unavailable")
    return path


def latest_report(store, name=None):
    root = Path(store).resolve()
    folder = root
    if name is not None:
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,39}", name):
            raise ValueError("name must be a target name, not a path")
        folder = root / name
        if folder.is_symlink() or not folder.is_dir():
            raise ValueError("Named report target is unavailable")
    found = []
    for current, folders, files in os.walk(folder, followlinks=False):
        folders[:] = [item for item in folders if not item.startswith(".") and not (Path(current) / item).is_symlink()]
        for filename in ("report.html", "report.json"):
            if filename not in files or filename == "report.json" and "report.html" in files:
                continue
            try:
                path = _artifact(root, (Path(current) / filename).relative_to(root))
                found.append(path)
            except ValueError:
                pass
    return max(found, key=lambda path: (path.stat().st_mtime_ns, str(path)), default=None)


def _registry(root):
    path = root / REGISTRY
    if path.is_symlink() or path.exists() and (not path.is_file() or path.stat().st_nlink != 1):
        raise ValueError("Server registry must be a regular file without links")
    if not path.exists():
        return None
    if path.stat().st_size > 4096:
        raise ValueError("Invalid report server registry")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if (value["version"] != 1 or value["store"] != str(root) or
                isinstance(value["port"], bool) or not isinstance(value["port"], int) or
                not 1 <= value["port"] <= 65535 or not re.fullmatch(r"[a-f0-9]{32}", value["token"])):
            raise ValueError
        return value
    except (KeyError, TypeError, ValueError):
        raise ValueError("Invalid report server registry; remove it after checking no server is running") from None


def running_server(store):
    root = Path(store).resolve()
    try:
        value = _registry(root)
        if value is None:
            return None
        connection = http.client.HTTPConnection("127.0.0.1", value["port"], timeout=0.3)
        try:
            connection.request("GET", "/_orphic_health/" + value["token"])
            response = connection.getresponse()
            if response.status == 200 and response.read(256) == value["token"].encode("ascii"):
                return "http://127.0.0.1:" + str(value["port"])
        finally:
            connection.close()
    except (OSError, ValueError, http.client.HTTPException):
        pass
    return None


def report_link(store, report):
    root = Path(store).resolve()
    base = running_server(root)
    try:
        path = _artifact(root, Path(report).absolute().relative_to(root))
    except (ValueError, OSError):
        path = None
    if base and path:
        return {"report_url": base + "/" + quote(path.relative_to(root).as_posix()),
                "serve_hint": "Open report_url over HTTP so images and Verify share the report origin."}
    command = ["python", "-m", "engine.cli", "serve", "--store", str(root)]
    formatted = subprocess.list2cmdline(command) if os.name == "nt" else shlex.join(command)
    return {"report_url": None, "serve_hint": "Start a local report server: " + formatted}


def attach_report_link(result, store, case):
    if result.get("status") == "error":
        return result
    case = Path(case)
    report = case / ("report.html" if (case / "report.html").is_file() else "report.json")
    return {**result, **report_link(store, report)}


class _HTTP(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False

    def handle_error(self, request, client_address):
        pass


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # Report paths and queries may be sensitive.

    def do_HEAD(self):
        self.do_GET(head=True)

    def do_GET(self, head=False):
        self.connection.settimeout(2)
        host = self.headers.get("Host", "")
        if host not in {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}:
            self.send_error(403, "Loopback Host required")
            return
        origin = self.headers.get("Origin")
        if (self.headers.get("Sec-Fetch-Site") == "cross-site" or
                origin and origin not in {"http://" + host}):
            self.send_error(403, "Cross-origin access refused")
            return
        try:
            path = unquote(urlsplit(self.path).path, errors="strict")
            if path == "/_orphic_health/" + self.server.token:
                content = self.server.token.encode("ascii")
                self.send_response(200)
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                if not head:
                    self.wfile.write(content)
                return
            if "\\" in path or "\x00" in path or not path.startswith("/"):
                raise ValueError
            if path == "/":
                report = latest_report(self.server.root)
                if report is None:
                    raise ValueError
                # Keep relative PNG URLs beside the selected report, including
                # when a server was started before the first capture existed.
                self.send_response(302)
                self.send_header("Location", "/" + quote(report.relative_to(self.server.root).as_posix()))
                self.send_header("Content-Length", "0")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                return
            else:
                report = _artifact(self.server.root, path.lstrip("/"))
            # Validate immediately before opening, and reject final symlinks on
            # platforms providing O_NOFOLLOW. Store contents are locally trusted.
            descriptor = os.open(report, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            with os.fdopen(descriptor, "rb") as stream:
                stat = os.fstat(stream.fileno())
                if stat.st_nlink != 1:
                    raise ValueError
                self.send_response(200)
                self.send_header("Content-Type", {".html": "text/html; charset=utf-8", ".json": "application/json", ".png": "image/png"}[report.suffix.lower()])
                self.send_header("Content-Length", str(stat.st_size))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                if not head:
                    import shutil
                    shutil.copyfileobj(stream, self.wfile)
        except (ValueError, UnicodeError, OSError):
            self.send_error(404, "Report artifact unavailable")

    def do_POST(self):
        self.send_error(405, "Read-only report server")

    do_PUT = do_PATCH = do_DELETE = do_POST


class ReportServer:
    def __init__(self, store, port=0, timeout=None):
        if isinstance(port, bool) or not isinstance(port, int) or not 0 <= port <= 65535:
            raise ValueError("port must be an integer from 0 to 65535")
        if timeout is not None and (isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0 < timeout < float("inf")):
            raise ValueError("timeout must be a finite positive number of seconds")
        self.root = Path(store).resolve()
        if not self.root.is_dir():
            raise ValueError("Report store must be an existing directory")
        if running_server(self.root):
            raise ValueError("A report server is already running for this store")
        _registry(self.root)  # Do not overwrite invalid or linked registry files.
        self.token = secrets.token_hex(16)
        self.httpd = _HTTP(("127.0.0.1", port), _Handler)
        self.httpd.root, self.httpd.token = self.root, self.token
        self.base_url = f"http://127.0.0.1:{self.httpd.server_port}"
        self.closed = threading.Event()
        self.lock = threading.Lock()
        self.timer = None
        try:
            from .store import _atomic_json
            _atomic_json(self.root / REGISTRY, {"version": 1, "store": str(self.root),
                         "port": self.httpd.server_port, "token": self.token})
            os.chmod(self.root / REGISTRY, 0o600)
            self.thread = threading.Thread(target=self.httpd.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
            self.thread.start()
            if timeout is not None:
                self.timer = threading.Timer(timeout, self.close)
                self.timer.daemon = True
                self.timer.start()
        except Exception:
            self.httpd.server_close()
            (self.root / REGISTRY).unlink(missing_ok=True)
            raise

    def url(self, name=None):
        report = latest_report(self.root, name)
        return self.base_url + ("/" + quote(report.relative_to(self.root).as_posix()) if report else "/")

    def wait(self):
        self.closed.wait()

    def close(self):
        with self.lock:
            if self.closed.is_set():
                return
            if self.timer:
                self.timer.cancel()
            self.httpd.shutdown()
            self.httpd.server_close()
            try:
                value = _registry(self.root)
                if value and value["token"] == self.token:
                    (self.root / REGISTRY).unlink()
            except (ValueError, OSError):
                pass
            self.closed.set()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
