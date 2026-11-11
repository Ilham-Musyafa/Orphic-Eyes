"""file:// pages must stay inside the configured file_root and outside protected paths."""

import json
import os
from pathlib import Path
import importlib
import tempfile
import unittest
from unittest.mock import patch

import orphic_tools as tools

capture = importlib.import_module("engine.capture")


class FileRootTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="oe_sec_")
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name).resolve()
        self.root = self.base / "project"
        self.home = self.base / "home"
        for folder in (self.root, self.home / ".hermes", self.home / ".ssh", self.root / ".git"):
            folder.mkdir(parents=True)
        self.page = self.root / "index.html"
        self.page.write_text("<p>ok</p>")
        self.outside = self.base / "outside.html"
        self.outside.write_text("<p>no</p>")
        patcher = patch.object(Path, "home", return_value=self.home)
        patcher.start()
        self.addCleanup(patcher.stop)

    def check(self, path, **kwargs):
        return capture.confine_file_url(Path(path).as_uri(), self.root,
                                        hermes_home=self.home / ".hermes", **kwargs)

    def test_inside_root_allowed(self):
        self.assertIsNone(self.check(self.page))

    def test_outside_root_refused(self):
        self.assertIn("file_root", self.check(self.outside))

    def test_hermes_home_and_ssh_refused_even_inside_root(self):
        for folder in (".hermes", ".ssh"):
            secret = self.home / folder / "config.html"
            secret.write_text("x")
            error = capture.confine_file_url(secret.as_uri(), self.home,
                                             hermes_home=self.home / ".hermes")
            self.assertIsNotNone(error)
            self.assertNotIn(str(secret), error)

    def test_dotfiles_and_env_refused(self):
        for name in (".env", "prod.env"):
            (self.root / name).write_text("SECRET=1")
            self.assertIsNotNone(self.check(self.root / name))
        (self.root / ".git" / "config").write_text("x")
        self.assertIn("dot", self.check(self.root / ".git" / "config"))

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks unavailable")
    def test_symlink_escape_refused(self):
        link = self.root / "escape.html"
        try:
            link.symlink_to(self.outside)
        except OSError:
            self.skipTest("symlink creation not permitted")
        self.assertIn("file_root", self.check(link))
        folder_link = self.root / "linked"
        folder_link.symlink_to(self.home / ".ssh", target_is_directory=True)
        (self.home / ".ssh" / "id.html").write_text("x")
        self.assertIsNotNone(self.check(folder_link / "id.html"))

    def test_missing_file_and_directory_refused(self):
        self.assertIsNotNone(self.check(self.root / "missing.html"))
        self.assertIsNotNone(self.check(self.root))

    def test_tool_layer_uses_configured_file_root(self):
        with patch.dict(os.environ, {"HERMES_HOME": str(self.home / ".hermes")}), \
                patch.object(tools, "plugin_config", return_value={"file_root": str(self.root)}):
            self.assertEqual(tools._url(self.page.as_uri()), self.page.as_uri())
            with self.assertRaises(ValueError) as caught:
                tools._url(self.outside.as_uri())
            self.assertIn("file_root", str(caught.exception))
            self.assertNotIn(str(self.outside), str(caught.exception))
            result = json.loads(tools.handle_baseline({"url": self.outside.as_uri()}))
            self.assertFalse(result["success"])
            self.assertIn("file_root", result["fix"])

    def test_default_file_root_is_working_directory(self):
        with patch.object(tools, "plugin_config", return_value={}):
            self.assertEqual(tools.file_root(), Path.cwd())

if __name__ == "__main__":
    unittest.main()
