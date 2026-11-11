"""Browser subprocesses receive an allowlisted environment, never secrets."""

import importlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from engine._browser_env import browser_env

legacy = importlib.import_module("engine.capture")
url_capture = importlib.import_module("engine.url_capture")

SECRETS = {"SECRET_KEY": "s3cret", "OPENAI_API_KEY": "sk-test", "ANTHROPIC_API_KEY": "x",
           "GITHUB_TOKEN": "ghp_x", "AWS_SECRET_ACCESS_KEY": "aws", "HERMES_HOME": "/h",
           "OPENROUTER_API_KEY": "or"}


class _Stop(Exception):
    pass


class BrowserEnvTests(unittest.TestCase):
    def test_allowlist_excludes_secrets_and_sets_temp(self):
        source = {"PATH": "/bin", "HOME": "/home/u", "LANG": "C.UTF-8", "LC_ALL": "C",
                  "https_proxy": "http://proxy:3128", "ProgramFiles(x86)": "C:\\PF86",
                  "SystemRoot": "C:\\Windows", **SECRETS}
        environment = browser_env("/tmp/profile", source)
        for key in SECRETS:
            self.assertNotIn(key, environment)
        for key in ("PATH", "HOME", "LANG", "LC_ALL", "https_proxy", "ProgramFiles(x86)", "SystemRoot"):
            self.assertIn(key, environment)
        self.assertEqual({environment[k] for k in ("TMP", "TEMP", "TMPDIR")}, {"/tmp/profile"})

    def test_legacy_capture_launches_without_secrets(self):
        seen = {}

        def fake_popen(command, **kwargs):
            seen.update(kwargs["env"])
            raise _Stop

        with tempfile.TemporaryDirectory() as folder, \
                patch.dict(os.environ, SECRETS), \
                patch.object(legacy, "detect_browser", return_value="/bin/true"), \
                patch.object(subprocess, "Popen", side_effect=fake_popen):
            self.assertFalse(legacy.capture("http://127.0.0.1:9/", Path(folder) / "a.png"))
        self.assertTrue(seen)
        for key in SECRETS:
            self.assertNotIn(key, seen)

    def test_url_capture_launches_without_secrets(self):
        seen = {}

        def fake_popen(command, **kwargs):
            seen.update(kwargs["env"])
            raise OSError("stop")

        with tempfile.TemporaryDirectory() as folder, \
                patch.dict(os.environ, SECRETS), \
                patch.object(url_capture, "destination", return_value=None), \
                patch.object(url_capture, "detect_browser", return_value="/bin/true"), \
                patch.object(subprocess, "Popen", side_effect=fake_popen):
            with self.assertRaises(url_capture.CaptureError):
                url_capture.capture("https://example.com/", Path(folder) / "a.png")
        self.assertTrue(seen)
        for key in SECRETS:
            self.assertNotIn(key, seen)

    def test_no_environ_copy_in_plugin(self):
        root = Path(__file__).resolve().parents[1]
        for path in [*root.glob("*.py"), *(root / "engine").glob("*.py")]:
            self.assertNotIn("os.environ.copy()", path.read_text(encoding="utf-8"), path.name)


if __name__ == "__main__":
    unittest.main()
