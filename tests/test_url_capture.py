"""URL policy, failure/adapter contracts, and real local-HTTP screenshots."""

from contextlib import contextmanager
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from PIL import Image, ImageChops

from engine import capture_pair, capture_url
from engine import _url_network as network
from engine.url_capture import BrowserNotFound, CaptureError, CaptureTimeout, validate_url

url_capture = importlib.import_module("engine.url_capture")
PUBLIC = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 80))]


class URLValidationTests(unittest.TestCase):
    def test_public_http_and_https(self):
        with patch.object(network, "resolve", return_value=PUBLIC):
            for url in ("https://example.com/preview?q=1", "http://example.com:8080/", "https://EXAMPLE.com./"):
                self.assertIsNone(validate_url(url), url)

    def test_bad_schemes_credentials_ports_and_syntax(self):
        for url in (None, 3, "", "example.com", "file:///tmp/a.html", "javascript:alert(1)",
                    "data:text/html,hi", "ftp://example.com", "https://", "https://example.com:0",
                    "https://example.com:99999", "https://example.com:bad", "https://[oops",
                    "https://u:secret@example.com/", "https://example.com/a\nb", "https://example.com\\a",
                    "http://[fe80::1%25eth0]/"):
            with self.subTest(url=url):
                for allow in (False, True):
                    self.assertIsInstance(validate_url(url, allow_local=allow), str)

    def test_private_loopback_metadata_and_obscure_numeric_forms(self):
        for host in ("localhost", "localhost.", "foo.localhost", "box.local", "box.internal",
                     "127.0.0.1", "127.1", "2130706433", "0177.0.0.1", "0x7f000001",
                     "10.2.3.4", "172.16.2.3", "192.168.2.3", "169.254.169.254",
                     "0.0.0.0", "224.0.0.1", "[::1]", "[fc00::1]", "[fe80::1]",
                     "[::ffff:127.0.0.1]"):
            with self.subTest(host=host):
                self.assertIn("allow_local", validate_url("http://" + host + "/"))

    def test_public_hostname_resolving_to_private_or_mixed_addresses_is_blocked(self):
        local = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", 80))]
        with patch.object(network, "resolve", return_value=PUBLIC + local):
            self.assertIn("allow_local", validate_url("https://public.example"))

    def test_allow_local_is_explicit_boolean(self):
        self.assertIsNone(validate_url("http://127.0.0.1/", allow_local=True))
        self.assertIn("boolean", validate_url("http://127.0.0.1/", allow_local="true"))

    def test_errors_never_echo_query_or_password(self):
        for url in ("file:///tmp/SECRET_QUERY", "http://user:SECRET_QUERY@example.com/", "http://127.0.0.1/?token=SECRET_QUERY"):
            self.assertNotIn("SECRET_QUERY", validate_url(url))

    def test_dns_failure_and_timeout_are_bounded_and_safe(self):
        with patch.object(network.socket, "getaddrinfo", side_effect=socket.gaierror("SECRET_QUERY")):
            self.assertEqual(validate_url("https://example.com/?SECRET_QUERY"), "URL host could not be resolved")
        release = threading.Event()
        with patch.object(network.socket, "getaddrinfo", side_effect=lambda *a, **k: release.wait(1)):
            started = time.monotonic()
            self.assertIn("timed out", validate_url("https://example.com", timeout=0.02))
            self.assertLess(time.monotonic() - started, 0.5)
            release.set()


class CaptureFailureTests(unittest.TestCase):
    def test_browser_endpoint_waits_for_complete_port_file_and_page_target(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as temporary, \
                patch.object(Path, "read_text", side_effect=["", "1234\n", "1234\n"]), \
                patch.object(url_capture.http.client, "HTTPConnection") as connection:
            response = connection.return_value.getresponse.return_value
            response.status = 200
            response.read.side_effect = [b"[]", b'[{"type":"page","webSocketDebuggerUrl":"ws://127.0.0.1:1234/devtools/page/test"}]']
            browser = Mock()
            browser.poll.return_value = None
            endpoint = url_capture._endpoint(Path(temporary), browser, time.monotonic() + 1)
            self.assertEqual(endpoint, "ws://127.0.0.1:1234/devtools/page/test")
            self.assertEqual(connection.return_value.close.call_count, 2)

    def test_no_browser_has_clear_error_and_preserves_output(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "existing.png"
            output.write_bytes(b"original")
            with patch.object(url_capture, "detect_browser", return_value=None):
                with self.assertRaisesRegex(BrowserNotFound, "Browser not found"):
                    capture_url("http://127.0.0.1/", output, allow_local=True)
            self.assertEqual(output.read_bytes(), b"original")

    def test_invalid_options_and_urls_never_launch_browser(self):
        with patch.object(url_capture.subprocess, "Popen") as process:
            for kwargs in ({"width": 0}, {"height": True}, {"full_page": 1}, {"wait_ms": -1},
                           {"timeout_ms": 250}, {"allow_local": "yes"}):
                with self.assertRaises(CaptureError):
                    capture_url("http://127.0.0.1/", "/tmp/never-created.png", **kwargs)
            with self.assertRaisesRegex(CaptureError, "http or https"):
                capture_url("file:///tmp/SECRET_QUERY", "/tmp/never-created.png")
            process.assert_not_called()

    def test_timeout_closes_browser_and_preserves_output(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "shot.png"
            output.write_bytes(b"original")
            with patch.object(url_capture, "detect_browser", return_value="browser"), \
                    patch.object(url_capture.subprocess, "Popen") as launched, \
                    patch.object(url_capture, "_endpoint", side_effect=TimeoutError):
                process = launched.return_value
                process.poll.return_value = None
                with self.assertRaisesRegex(CaptureTimeout, "timed out"):
                    capture_url("http://127.0.0.1/", output, allow_local=True)
                process.terminate.assert_called_once()
            self.assertEqual(output.read_bytes(), b"original")

    def test_output_links_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            original = Path(folder) / "original"
            original.write_bytes(b"original")
            alias = Path(folder) / "alias.png"
            os.link(original, alias)
            with patch.object(url_capture, "detect_browser", return_value="browser"):
                with self.assertRaisesRegex(CaptureError, "without links"):
                    capture_url("http://127.0.0.1/", alias, allow_local=True)
            self.assertEqual(original.read_bytes(), b"original")

    def test_pair_uses_real_pixel_pipeline_and_existing_report_schema(self):
        def shots(url, path, width, height, **kwargs):
            image = Image.new("RGB", (width, height), "white")
            if url.endswith("/b"):
                image.paste("red", (40, 80, 100, 120))
            image.save(path)
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(url_capture, "detect_browser", return_value="browser"), \
                patch.object(url_capture, "capture", side_effect=shots):
            result = capture_pair("http://127.0.0.1/a", "http://127.0.0.1/b", folder, allow_local=True)
            self.assertEqual(result["status"], "check", result)
            self.assertEqual(result["summary"]["box_count"], 1)
            self.assertEqual(result["size"], {"width": 1440, "height": 900})
            persisted = json.loads(Path(result["paths"]["report"]).read_text())
            self.assertEqual(persisted, {key: value for key, value in result.items()
                                        if key not in ("paths", "report_url", "serve_hint")})
            self.assertEqual(persisted["schema_version"], 1)

    def test_failed_second_capture_publishes_no_partial_report(self):
        calls = 0
        def shots(url, path, *args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise CaptureError("URL navigation failed")
            Image.new("RGB", (1440, 900), "white").save(path)
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(url_capture, "detect_browser", return_value="browser"), \
                patch.object(url_capture, "capture", side_effect=shots):
            result = capture_pair("http://127.0.0.1/a", "http://127.0.0.1/b", folder, allow_local=True)
            self.assertEqual(result["status"], "error")
            self.assertEqual(list((Path(folder) / "urls").iterdir()), [])
            self.assertEqual(list(Path(folder).iterdir()), [Path(folder) / "urls"])

    def test_pair_preserves_existing_target_and_rejects_bad_url_before_writing(self):
        with tempfile.TemporaryDirectory() as folder:
            result = capture_pair("file:///SECRET_QUERY", "https://example.com", folder)
            self.assertEqual(result["status"], "error")
            self.assertNotIn("SECRET_QUERY", result["error"])
            self.assertEqual(list(Path(folder).iterdir()), [])
            case = Path(folder) / "urls"
            case.mkdir()
            (case / "existing.txt").write_text("preserve")
            result = capture_pair("http://127.0.0.1/a", "http://127.0.0.1/b", folder, allow_local=True)
            self.assertIn("fresh name", result["error"])
            self.assertEqual((case / "existing.txt").read_text(), "preserve")

    def test_pair_rejects_target_redirect_inside_store(self):
        with tempfile.TemporaryDirectory() as folder:
            real = Path(folder) / "real"
            real.mkdir()
            try:
                (Path(folder) / "urls").symlink_to(real, target_is_directory=True)
            except OSError as exc:
                self.skipTest("Directory symlinks unavailable: " + str(exc))
            result = capture_pair("http://127.0.0.1/a", "http://127.0.0.1/b", folder, allow_local=True)
            self.assertEqual(result["status"], "error")
            self.assertIn("redirect", result["error"])
            self.assertEqual(list(real.iterdir()), [])


class _Pages(BaseHTTPRequestHandler):
    hits = []
    stop_wait = threading.Event()

    def log_message(self, *args):
        pass

    def do_GET(self):
        type(self).hits.append(self.path)
        if self.path == "/hang":
            self.stop_wait.wait(5)
            return
        if self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", f"http://127.0.0.1:{self.server.server_port}/private")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        color = "blue" if self.path.startswith("/b") else "red"
        extra = ""
        if self.path == "/resource":
            extra = f'<img src="http://127.0.0.1:{self.server.server_port}/private">'
        page = ("<!doctype html><style>body{margin:0;background:white;height:1600px}"
                ".box{position:absolute;left:40px;top:80px;width:60px;height:40px;background:" + color + ";"
                "animation:move 1s infinite;transition:all 1s}@keyframes move{to{transform:translateX(500px)}}"
                "</style><div class=box></div>" + extra).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(page)))
        self.end_headers()
        try:
            self.wfile.write(page)
        except (BrokenPipeError, ConnectionResetError):
            pass


@contextmanager
def local_pages():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Pages)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        _Pages.stop_wait.set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)


class ProxyPolicyTests(unittest.TestCase):
    def test_upstream_connect_pins_public_ip_instead_of_resolving_again(self):
        proxy = network.GuardedProxy(False, time.monotonic() + 5)
        proxy.proxies = {"https": "http://proxy.invalid:8080"}
        try:
            with patch.object(network, "resolve", return_value=PUBLIC), \
                    patch.object(network, "proxy_bypass", return_value=False), \
                    patch.object(network.socket, "create_connection") as connect:
                sock = connect.return_value
                sock.recv.side_effect = [bytes((byte,)) for byte in b"HTTP/1.1 200 Connection established\r\n\r\n"]
                proxy.connect("https://public.example/?SECRET_QUERY")
                request = sock.sendall.call_args.args[0]
                self.assertIn(b"CONNECT 93.184.216.34:443 HTTP/1.1", request)
                self.assertNotIn(b"public.example", request)
                self.assertNotIn(b"SECRET_QUERY", request)
        finally:
            proxy.close()

    def test_proxy_blocks_private_requests_before_contacting_server(self):
        with local_pages() as server:
            _Pages.hits.clear()
            proxy = network.GuardedProxy(False, time.monotonic() + 5)
            try:
                connection = http.client.HTTPConnection("127.0.0.1", proxy.server_port, timeout=2)
                connection.request("GET", f"http://127.0.0.1:{server.server_port}/private?SECRET_QUERY")
                response = connection.getresponse()
                self.assertEqual(response.status, 403)
                self.assertNotIn(b"SECRET_QUERY", response.read())
                connection.close()
                self.assertEqual(_Pages.hits, [])
                self.assertIn("allow_local", proxy.violation)
            finally:
                proxy.close()

    def test_direct_connection_uses_validated_numeric_address(self):
        proxy = network.GuardedProxy(False, time.monotonic() + 5)
        proxy.proxies = {}
        try:
            with patch.object(network, "resolve", return_value=PUBLIC), \
                    patch.object(network.socket, "socket") as socket_type:
                proxy.connect("http://public.example/")
                socket_type.return_value.connect.assert_called_once_with(("93.184.216.34", 80))
        finally:
            proxy.close()


class URLBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.browser = url_capture.detect_browser(os.environ.get("ORPHIC_BROWSER"))
        if cls.browser is None:
            raise unittest.SkipTest("URL capture requires installed Edge, Chrome or Chromium")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="oe_url_test_")
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)

    def test_default_viewport_repeated_pixels_and_motion_disabled(self):
        with local_pages() as server:
            url = f"http://127.0.0.1:{server.server_port}/a"
            for name in ("first", "second"):
                capture_url(url, self.folder / (name + ".png"), allow_local=True)
            with Image.open(self.folder / "first.png") as first, Image.open(self.folder / "second.png") as second:
                self.assertEqual(first.size, (1440, 900))
                self.assertIsNone(ImageChops.difference(first.convert("RGB"), second.convert("RGB")).getbbox())
                self.assertEqual(first.convert("RGB").getpixel((45, 85)), (255, 0, 0))
                self.assertEqual(first.convert("RGB").getpixel((550, 85)), (255, 255, 255))

    def test_full_page_and_custom_viewport(self):
        with local_pages() as server:
            capture_url(f"http://127.0.0.1:{server.server_port}/a", self.folder / "full.png",
                        width=800, height=600, full_page=True, allow_local=True)
            with Image.open(self.folder / "full.png") as image:
                self.assertEqual(image.size, (800, 1600))

    def test_cli_pair_uses_existing_status_exit_code_and_writes_report(self):
        with local_pages() as server:
            base = f"http://127.0.0.1:{server.server_port}"
            completed = subprocess.run([sys.executable, "-B", "-m", "engine.cli", "capture-pair",
                                        base + "/a", base + "/b", "--store", str(self.folder),
                                        "--name", "cli", "--allow-local"],
                                       capture_output=True, text=True, timeout=20)
            self.assertEqual(completed.returncode, 1, completed.stderr)
            report = json.loads(completed.stdout)
            self.assertEqual(report["status"], "check")
            self.assertEqual(report["summary"]["box_count"], 1)
            self.assertTrue(Path(report["paths"]["report"]).is_file())

    def test_pair_report_from_two_local_pages(self):
        with local_pages() as server:
            base = f"http://127.0.0.1:{server.server_port}"
            result = capture_pair(base + "/a?token=SECRET_QUERY", base + "/b", self.folder, allow_local=True)
            self.assertEqual(result["status"], "check", result)
            self.assertEqual(result["summary"]["box_count"], 1)
            self.assertEqual({key: result["boxes"][0][key] for key in ("x", "y", "w", "h")},
                             {"x": 40, "y": 80, "w": 60, "h": 40})
            report_path = Path(result["paths"]["report"])
            report = json.loads(report_path.read_text())
            self.assertNotIn("SECRET_QUERY", report_path.read_text())
            for path in report["images"].values():
                self.assertTrue((report_path.parent / path).is_file())
            if "html" in result["paths"]:
                html = Path(result["paths"]["html"]).read_text()
                embedded = html.split('<script type="application/json" id="orphic-report">', 1)[1].split('</script>', 1)[0]
                self.assertEqual(json.loads(embedded), report)
                self.assertNotIn("SECRET_QUERY", html)

    def test_navigation_timeout_does_not_hang_or_publish_screenshot(self):
        _Pages.stop_wait.clear()
        with local_pages() as server:
            started = time.monotonic()
            with self.assertRaises(CaptureTimeout):
                capture_url(f"http://127.0.0.1:{server.server_port}/hang", self.folder / "timeout.png",
                            allow_local=True, wait_ms=0, timeout_ms=1200)
            self.assertLess(time.monotonic() - started, 4)
            self.assertFalse((self.folder / "timeout.png").exists())

    def test_public_page_cannot_redirect_or_load_resource_from_private_network(self):
        # Simulate a public website at the local fixture server, preserving the
        # actual guard for its redirect/subresource requests to loopback.
        original_connect = network.GuardedProxy.connect
        original_resolve = network.resolve
        with local_pages() as server:
            def resolve(host, port, timeout):
                return PUBLIC if host == "public.example" else original_resolve(host, port, timeout)
            def connect(proxy, url):
                if network.parse_url(url)[1] == "public.example":
                    network.destination(url, False, 1)
                    return socket.create_connection(("127.0.0.1", server.server_port), timeout=2)
                return original_connect(proxy, url)
            with patch.object(network, "resolve", side_effect=resolve), patch.object(network.GuardedProxy, "connect", connect):
                for path in ("redirect", "resource"):
                    _Pages.hits.clear()
                    with self.subTest(path=path), self.assertRaisesRegex(CaptureError, "allow_local"):
                        capture_url("http://public.example/" + path, self.folder / (path + ".png"))
                    self.assertNotIn("/private", _Pages.hits)
                    self.assertFalse((self.folder / (path + ".png")).exists())


if __name__ == "__main__":
    unittest.main()
