"""Local report HTTP serving, confinement, discovery and shutdown."""

import http.client
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

from PIL import Image

from engine.serve import REGISTRY, ReportServer, latest_report, report_link, running_server
from engine.url_capture import capture_pair
from unittest.mock import patch


class ReportServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="oe_serve_")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "store"
        self.root.mkdir()
        self.case = self.root / "sample"
        self.case.mkdir()
        (self.case / "report.html").write_text('<html><img src="baseline.png"></html>')
        (self.case / "report.json").write_text('{"schema_version":1}')
        Image.new("RGB", (4, 4), "red").save(self.case / "baseline.png")

    def request(self, server, path, method="GET", headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", server.httpd.server_port, timeout=2)
        try:
            connection.request(method, path, headers=headers or {})
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def test_latest_named_report_html_images_and_head(self):
        with ReportServer(self.root) as server:
            self.assertEqual(server.httpd.server_address[0], "127.0.0.1")
            self.assertGreater(server.httpd.server_port, 0)
            self.assertEqual(server.url("sample"), server.base_url + "/sample/report.html")
            self.assertEqual(latest_report(self.root), self.case / "report.html")
            status, headers, _ = self.request(server, "/")
            self.assertEqual(status, 302)
            self.assertEqual(headers["Location"], "/sample/report.html")
            for path in ("/sample/report.html", "/sample/report.json", "/sample/baseline.png"):
                status, headers, content = self.request(server, path)
                self.assertEqual(status, 200, path)
                self.assertTrue(content)
                self.assertEqual(headers["Cache-Control"], "no-store")
            self.assertEqual(self.request(server, "/sample/baseline.png")[1]["Content-Type"], "image/png")
            status, _, content = self.request(server, "/sample/report.html", method="HEAD")
            self.assertEqual((status, content), (200, b""))

    def test_no_listings_hidden_files_arbitrary_files_or_traversal(self):
        (self.root.parent / "report.html").write_text("OUTSIDE_SECRET")
        (self.case / "private.txt").write_text("PRIVATE_SECRET")
        with ReportServer(self.root) as server:
            for path in ("/sample/", "/missing/", "/sample/private.txt", "/.env", "/.env.local",
                         "/.orphic-server.json", "/../report.html", "/%2e%2e/report.html",
                         "/sample/%2e%2e/%2e%2e/report.html", "/%5c..%5creport.html", "/%00report.html"):
                with self.subTest(path=path):
                    status, _, body = self.request(server, path)
                    self.assertEqual(status, 404)
                    self.assertNotIn(b"OUTSIDE_SECRET", body)
                    self.assertNotIn(b"PRIVATE_SECRET", body)

    def test_read_only_and_rebinding_cross_origin_defenses(self):
        original = (self.case / "report.json").read_bytes()
        with ReportServer(self.root) as server:
            for method in ("POST", "PUT", "PATCH", "DELETE"):
                self.assertEqual(self.request(server, "/sample/report.json", method=method)[0], 405)
            for headers in ({"Host": "evil.example"}, {"Origin": "https://evil.example"}, {"Sec-Fetch-Site": "cross-site"}):
                self.assertEqual(self.request(server, "/sample/report.html", headers=headers)[0], 403)
        self.assertEqual((self.case / "report.json").read_bytes(), original)

    def test_symlink_files_directories_and_hard_links_are_refused(self):
        outside = self.root.parent / "outside"
        outside.mkdir()
        Image.new("RGB", (4, 4), "blue").save(outside / "secret.png")
        try:
            (self.case / "linked.png").symlink_to(outside / "secret.png")
            (self.root / "linked").symlink_to(outside, target_is_directory=True)
        except OSError as exc:
            self.skipTest("Symlinks unavailable: " + str(exc))
        os.link(outside / "secret.png", self.case / "hard.png")
        with ReportServer(self.root) as server:
            for path in ("/sample/linked.png", "/linked/secret.png", "/sample/hard.png"):
                self.assertEqual(self.request(server, path)[0], 404)

    def test_registry_discovery_across_processes_and_stale_cleanup(self):
        self.assertIsNone(running_server(self.root))
        hint = report_link(self.root, self.case / "report.html")
        self.assertIsNone(hint["report_url"])
        self.assertIn("engine.cli serve", hint["serve_hint"])
        with ReportServer(self.root) as server:
            self.assertEqual(running_server(self.root), server.base_url)
            self.assertEqual(report_link(self.root, self.case / "report.html")["report_url"], server.url())
            script = "import sys; from engine.serve import running_server; print(running_server(sys.argv[1]))"
            completed = subprocess.run([sys.executable, "-B", "-c", script, str(self.root)], capture_output=True, text=True, timeout=5)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(completed.stdout.strip(), server.base_url)
            with self.assertRaisesRegex(ValueError, "already running"):
                ReportServer(self.root)
        self.assertIsNone(running_server(self.root))
        self.assertFalse((self.root / REGISTRY).exists())

    def test_timeout_stops_server_and_registry_cleanly(self):
        server = ReportServer(self.root, timeout=0.1)
        self.addCleanup(server.close)
        self.assertTrue(server.closed.wait(2))
        self.assertIsNone(running_server(self.root))
        self.assertFalse((self.root / REGISTRY).exists())
        server.close()  # Idempotent after timer shutdown.

    def test_latest_round_and_bad_names(self):
        round_folder = self.case / "loop" / "round-001"
        round_folder.mkdir(parents=True)
        (round_folder / "report.html").write_text("round one")
        os.utime(round_folder / "report.html", ns=(time.time_ns() + 1000000, time.time_ns() + 1000000))
        self.assertEqual(latest_report(self.root, "sample"), round_folder / "report.html")
        for name in ("../outside", "sample/loop", ".hidden", "missing"):
            with self.assertRaises(ValueError):
                latest_report(self.root, name)

    def test_capture_pair_returns_live_report_url_or_startup_hint(self):
        def shot(url, path, width, height, **kwargs):
            Image.new("RGB", (width, height), "white").save(path)
        with patch("engine.url_capture.detect_browser", return_value="browser"), patch("engine.url_capture.capture", side_effect=shot):
            first = capture_pair("http://127.0.0.1/a", "http://127.0.0.1/b", self.root, name="offline", allow_local=True)
            self.assertIsNone(first["report_url"])
            self.assertIn("serve", first["serve_hint"])
            with ReportServer(self.root) as server:
                result = capture_pair("http://127.0.0.1/a", "http://127.0.0.1/b", self.root, name="online", allow_local=True)
                self.assertEqual(result["report_url"], server.base_url + "/online/report.html")
                self.assertEqual(self.request(server, "/online/report.html")[0], 200)
                persisted = json.loads(Path(result["paths"]["report"]).read_text())
                self.assertNotIn("report_url", persisted)

    def test_invalid_configuration_and_registry_links(self):
        for kwargs in ({"port": True}, {"port": -1}, {"timeout": 0}, {"timeout": float("nan")}):
            with self.assertRaises(ValueError):
                ReportServer(self.root, **kwargs)
        (self.root / REGISTRY).write_text("unrecognized")
        with self.assertRaisesRegex(ValueError, "Invalid report server registry"):
            ReportServer(self.root)


if __name__ == "__main__":
    unittest.main()
