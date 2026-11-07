"""Plugin contract, confinement, compact output and real-browser workflows."""

import contextlib
import importlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

import commands
import orphic_tools as tools

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
HANDLERS = [entry[2] for entry in tools.TOOL_DEFINITIONS]


class FakeContext:
    def __init__(self):
        self.tools, self.hooks, self.commands = {}, [], {}

    def register_tool(self, name, toolset, schema, handler, **kwargs):
        if name in self.tools:
            raise AssertionError("duplicate tool registration")
        self.tools[name] = (toolset, schema, handler)

    def register_hook(self, hook_name, callback, *, hold_stream=False):
        self.hooks.append(hook_name)

    def register_command(self, name, handler, description="", args_hint="", argument_mode=None):
        self.commands[name] = handler


def load_package(name, root=ROOT):
    spec = importlib.util.spec_from_file_location(name, root / "__init__.py",
                                                 submodule_search_locations=[str(root)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class PluginTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT, prefix="test_plugin_")
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        environment = patch.dict(os.environ, {"HERMES_HOME": str(self.home)})
        environment.start()
        self.addCleanup(environment.stop)
        # Exercise the env fallback even when running in Hermes' interpreter.
        constants = patch.dict(sys.modules, {"hermes_constants": None})
        constants.start()
        self.addCleanup(constants.stop)
        self.image = Image.new("RGB", (1280, 720), "white")

        def capture(url, output, **kwargs):
            self.image.resize((kwargs.get("width", 1280), kwargs.get("height", 720))).save(output)
            return True

        for target, kwargs in (("engine.store.detect_browser", {"return_value": "browser.exe"}),
                               ("engine.store.capture", {"side_effect": capture}),
                               ("engine.capture.capture", {"side_effect": capture})):
            mocked = patch(target, **kwargs)
            mocked.start()
            self.addCleanup(mocked.stop)

    def call(self, handler, args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            text = handler(args, session_id="test-runtime-keyword")
        self.assertEqual(output.getvalue(), "")
        self.assertIsInstance(text, str)
        self.assertLess(len(text.encode()), tools.MAX_RESULT_BYTES)
        self.assertNotIn("base64", text.lower())
        return json.loads(text)

    def baseline(self, **kwargs):
        result = self.call(tools.handle_baseline, {"url": "http://localhost:3000/", **kwargs})
        self.assertTrue(result["success"], result)
        self.assertIsNone(result["paths"]["report"])
        return result

    def test_register_matches_manifest_and_schemas(self):
        plugin = load_package("_orphic_registration_test")
        self.addCleanup(lambda: [sys.modules.pop(key, None) for key in list(sys.modules)
                                if key.startswith("_orphic_registration_test")])
        ctx = FakeContext()
        plugin.register(ctx)
        # JSON is valid YAML 1.2; parse this simple list without adding PyYAML.
        manifest = (ROOT / "plugin.yaml").read_text()
        block = manifest.split("provides_tools:\n", 1)[1].split("provides_hooks:", 1)[0]
        names = {line.strip()[2:] for line in block.splitlines() if line.strip().startswith("- ")}
        self.assertEqual(set(ctx.tools), names)
        self.assertIn("provides_hooks: []", manifest)
        self.assertEqual(ctx.hooks, [])
        self.assertEqual(set(ctx.commands), {"orphic"})
        self.assertIn("doctor", ctx.commands["orphic"]("help"))
        for name, (toolset, schema, handler) in ctx.tools.items():
            self.assertEqual(toolset, "orphic")
            self.assertEqual(schema["name"], name)
            self.assertEqual(schema["parameters"]["type"], "object")
            self.assertEqual(schema["parameters"]["additionalProperties"], False)
            self.assertTrue(callable(handler))

    def test_package_import_without_repo_on_path(self):
        script = """import importlib.util, sys
from pathlib import Path
root = Path(sys.argv[1])
spec = importlib.util.spec_from_file_location('hermes_test_plugin', root/'__init__.py', submodule_search_locations=[str(root)])
p = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = p
spec.loader.exec_module(p)
class C:
 def register_tool(self, **kw):
  assert kw['toolset'] == 'orphic'
  assert isinstance(kw['handler'](None), str)
 def register_command(self, *args, **kw): pass
p.register(C())
import hermes_test_plugin.engine.cli
assert 'engine' not in sys.modules
"""
        proc = subprocess.run([sys.executable, "-I", "-B", "-c", script, str(ROOT)],
                              cwd=self.home, capture_output=True, text=True, timeout=20)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, "")

    def test_env_and_fallback_home_resolution_without_writes(self):
        self.assertEqual(tools.resolve_data_dir(), self.home / "orphic-eyes")
        self.assertFalse(tools.resolve_data_dir().exists())
        with patch.dict(os.environ, {}, clear=True), patch.object(Path, "home", return_value=self.home):
            self.assertEqual(tools.resolve_data_dir(), self.home / ".hermes" / "orphic-eyes")

    def test_hermes_context_home_precedes_environment(self):
        from types import SimpleNamespace
        selected = self.home / "selected-profile"
        module = SimpleNamespace(get_hermes_home=lambda: selected)
        with patch.dict(sys.modules, {"hermes_constants": module}):
            self.assertEqual(tools.resolve_data_dir(), selected / "orphic-eyes")

    def test_all_handlers_invalid_inputs_never_raise(self):
        for handler in HANDLERS:
            for args in ({}, None, [], "bad", 1, True, {"name": 12}, {"name": "missing"},
                         {"url": "https://example.com"}, {"name": "../escape"},
                         {"name": "a" * 41}, {"name": "CON"}, {"unknown": 1}):
                with self.subTest(handler=handler.__name__, args=args):
                    result = self.call(handler, args)
                    self.assertFalse(result["success"], result)
                    self.assertEqual(set(result), {"success", "error", "fix"})
                    self.assertTrue(result["error"] and result["fix"])

    def test_all_handlers_unwritable_root(self):
        self.baseline()
        arguments = [{"url": "http://localhost"}, {}, {"all": True}, {},
                     {"action": "add", "region": {"x": 0, "y": 0, "w": 10, "h": 10}}]
        with patch.object(tools, "resolve_data_dir", side_effect=PermissionError("data directory permission denied")):
            for handler, args in zip(HANDLERS, arguments):
                result = self.call(handler, args)
                self.assertFalse(result["success"])
                self.assertIn("writable", result["fix"])
        # A root that is a file is an actual OS failure, not just a mocked ACL.
        other = self.home / "blocked"
        other.mkdir()
        (other / "orphic-eyes").write_text("blocked")
        with patch.dict(os.environ, {"HERMES_HOME": str(other)}):
            for handler, args in zip(HANDLERS, arguments):
                self.assertFalse(self.call(handler, args)["success"])

    def test_parameter_types_and_missing_required_fields(self):
        self.baseline()
        cases = [(tools.handle_baseline, {"url": "http://localhost", "width": True}),
                 (tools.handle_baseline, {"url": "http://localhost", "height": "720"}),
                 (tools.handle_compare, {"expect": None}),
                 (tools.handle_compare, {"expect": [{"x": False, "y": 0, "w": 5, "h": 5}]}),
                 (tools.handle_compare, {"url": None}),
                 (tools.handle_approve, {"boxes": [True]}),
                 (tools.handle_approve, {"all": "true"}),
                 (tools.handle_approve, {"all": True, "boxes": [1]}),
                 (tools.handle_ignore, {"action": "add"}),
                 (tools.handle_ignore, {"action": [], "region": {"x": 0, "y": 0, "w": 5, "h": 5}})]
        for handler, args in cases:
            with self.subTest(handler=handler.__name__, args=args):
                self.assertFalse(self.call(handler, args)["success"])

    def test_bad_url_does_not_create_storage(self):
        result = self.call(tools.handle_baseline, {"url": "https://example.com"})
        self.assertFalse(result["success"])
        self.assertFalse(tools.resolve_data_dir().exists())

    def test_dimensions_and_saved_url(self):
        result = self.baseline(width=960, height=600)
        self.assertEqual(result["viewport"], {"width": 960, "height": 600, "dpr": 1})
        with patch("engine.capture.capture", wraps=importlib.import_module("engine.capture").capture) as capture:
            result = self.call(tools.handle_compare, {})
            self.assertTrue(result["success"], result)
            self.assertEqual(capture.call_args.args[0], "http://localhost:3000/")
            self.assertEqual(capture.call_args.kwargs["width"], 960)
        self.assertEqual(result["paths"]["report"],
                         str(tools.resolve_data_dir() / "default" / "report.json"))

    def test_url_override_changes_default_only_when_accepted(self):
        self.baseline()
        self.call(tools.handle_compare, {"url": "http://localhost:4000/after"})
        state_file = tools.resolve_data_dir() / "default" / tools.STATE_FILE
        self.assertEqual(json.loads(state_file.read_text())["url"], "http://localhost:3000/")
        self.call(tools.handle_accept, {})
        self.assertEqual(json.loads(state_file.read_text())["url"], "http://localhost:4000/after")
        with patch("engine.capture.capture", wraps=importlib.import_module("engine.capture").capture) as capture:
            result = self.call(tools.handle_compare, {})
            self.assertTrue(result["success"], result)
            self.assertEqual(capture.call_args.args[0], "http://localhost:4000/after")

    def test_ignore_add_remove_clips_and_preserves_contract(self):
        self.baseline()
        region = {"x": 1270, "y": 710, "w": 100, "h": 100}
        result = self.call(tools.handle_ignore, {"action": "add", "region": region})
        self.assertTrue(result["success"], result)
        self.assertEqual(result["ignore_regions"][0]["w"], 10)
        result = self.call(tools.handle_ignore, {"action": "remove", "region": region})
        self.assertTrue(result["success"], result)
        self.assertEqual(result["ignore_regions"], [])
        self.assertFalse(self.call(tools.handle_ignore, {"action": "remove", "region": region})["success"])

    def test_expected_and_approved_boxes_keep_engine_fields(self):
        self.baseline()
        self.image.paste("black", (10, 10, 30, 30))
        result = self.call(tools.handle_compare, {"expect": [{"x": 0, "y": 0, "w": 40, "h": 40}]})
        self.assertEqual(result["status"], "pass", result)
        self.assertEqual(result["boxes"][0]["kind"], "expected")
        self.assertEqual(result["changed_percent"], result["summary"]["changed_percent"])
        for box in result["boxes"]:
            self.assertEqual(box["bbox"], {key: box[key] for key in ("x", "y", "w", "h")})
            self.assertIn("approved", box)
            self.assertIn("label", box)
        result = self.call(tools.handle_compare, {})
        self.assertEqual(result["status"], "check")
        result = self.call(tools.handle_approve, {"boxes": [result["boxes"][0]["id"]]})
        self.assertEqual(result["status"], "pass", result)
        self.assertEqual(result["boxes"][0]["kind"], "approved")
        self.assertEqual(result["paths"]["report"],
                         str(tools.resolve_data_dir() / "default" / "report.json"))

    def test_result_budget_with_many_boxes(self):
        self.baseline()
        for y in range(10, 700, 96):
            for x in range(10, 1260, 96):
                self.image.putpixel((x, y), (0, 0, 0))
        result = self.call(tools.handle_compare, {})
        self.assertTrue(result["success"], result)
        self.assertGreater(result["summary"]["box_count"], 20)
        self.assertLessEqual(len(result["boxes"]), 20)
        self.assertEqual(len(result["boxes"]) + result["boxes_omitted"], result["summary"]["box_count"])

    def test_fresh_baseline_invalidates_old_comparison(self):
        self.baseline()
        self.call(tools.handle_compare, {})
        self.baseline()
        self.assertFalse(self.call(tools.handle_accept, {})["success"])
        self.assertFalse(self.call(tools.handle_approve, {"all": True})["success"])

    def test_redirected_data_root_is_rejected(self):
        outside = self.home / "other"
        outside.mkdir()
        link = self.home / "orphic-eyes"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except OSError as exc:
            self.skipTest("symlinks unavailable: " + str(exc))
        self.assertFalse(self.call(tools.handle_baseline, {"url": "http://localhost"})["success"])
        self.assertEqual(list(outside.iterdir()), [])

    def test_linked_sidecar_is_rejected_without_overwrite(self):
        self.baseline()
        state = tools.resolve_data_dir() / "default" / tools.STATE_FILE
        state.unlink()
        other = self.home / "other.json"
        other.write_text('{"url":"http://localhost"}')
        os.link(other, state)
        self.assertFalse(self.call(tools.handle_baseline, {"url": "http://localhost"})["success"])
        self.assertEqual(other.read_text(), '{"url":"http://localhost"}')

    def test_no_browser_returns_actionable_error(self):
        with patch("engine.store.detect_browser", return_value=None):
            result = self.call(tools.handle_baseline, {"url": "http://localhost"})
        self.assertFalse(result["success"])
        self.assertIn("browser", result["fix"].lower())

    def test_cli_still_runs_without_hermes(self):
        proc = subprocess.run([sys.executable, "-B", "-m", "engine.cli", "--help"],
                              cwd=ROOT, capture_output=True, text=True, timeout=20)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("baseline", proc.stdout)

    def test_commands_help_unknown_and_doctor_failures(self):
        self.assertIn("/orphic demo", commands.handle_command("help"))
        self.assertIn("Unknown command", commands.handle_command("unknown"))
        with patch.object(tools, "resolve_data_dir", side_effect=PermissionError("denied")), \
                patch("engine.capture.detect_browser", return_value=None):
            result = commands.handle_command("doctor")
        self.assertIn("✗ Data directory", result)
        self.assertIn("✗ Browser", result)
        self.assertIn("Fix:", result)


class PluginBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if importlib.import_module("engine.capture").detect_browser() is None:
            raise unittest.SkipTest("Plugin E2E requires installed Edge, Chrome or Chromium")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT, prefix="test_plugin_browser_")
        self.addCleanup(self.temp.cleanup)
        patcher = patch.dict(os.environ, {"HERMES_HOME": self.temp.name})
        patcher.start()
        self.addCleanup(patcher.stop)

    def call(self, handler, args):
        result = json.loads(handler(args))
        self.assertTrue(result["success"], result)
        return result

    def test_real_handler_workflow(self):
        before = (FIXTURES / "page_a.html").as_uri()
        after = (FIXTURES / "page_b.html").as_uri()
        result = self.call(tools.handle_baseline, {"url": before})
        self.assertEqual(result["viewport"], {"width": 1280, "height": 720, "dpr": 1})
        self.assertEqual(self.call(tools.handle_compare, {})["status"], "pass")
        changed = self.call(tools.handle_compare, {"url": after})
        self.assertIn(changed["status"], ("check", "fail"))
        self.assertTrue(changed["boxes"])
        self.assertEqual(self.call(tools.handle_approve, {"all": True})["status"], "pass")
        self.assertEqual(self.call(tools.handle_accept, {})["status"], "pass")
        self.assertEqual(self.call(tools.handle_compare, {})["status"], "pass")

    def test_real_slash_doctor_and_offline_demo(self):
        diagnosis = commands.handle_command("doctor")
        self.assertNotIn("✗", diagnosis, diagnosis)
        for label in ("Python", "Pillow", "Browser", "Data directory", "Engine"):
            self.assertIn(label, diagnosis)
        result = commands.handle_command("demo")
        self.assertIn("Demo: check", result, result)
        folder = tools.resolve_data_dir() / "demo"
        self.assertTrue((folder / "baseline.png").is_file())
        self.assertTrue((folder / "current.png").is_file())
        self.assertTrue((folder / "diff.png").is_file())
        self.assertFalse((folder / "report.html").exists())
        report = json.loads((folder / "report.json").read_text())
        self.assertEqual(report["status"], "check")


if __name__ == "__main__":
    unittest.main()
