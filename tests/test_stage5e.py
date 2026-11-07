"""Product naming and optional report-page freshness regressions."""

from pathlib import Path
import subprocess
import sys
import unittest

from tests.test_plugin import FakeContext, ROOT, load_package


class NamingTests(unittest.TestCase):
    def test_tracked_runtime_and_documentation_use_current_name(self):
        excluded = {f"docs/stage-5{stage}-notes.md" for stage in ("c", "d", "e")}
        tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
        matches = []
        for filename in tracked.decode("utf-8").split("\0"):
            if filename in excluded or Path(filename).suffix.lower() not in {
                    ".py", ".yaml", ".md", ".txt", ".html"}:
                continue
            if ("sight" + "diff") in (ROOT / filename).read_text(encoding="utf-8").lower():
                matches.append(filename)
        self.assertEqual(matches, [])

    def test_manifest_and_registration_identifiers(self):
        manifest = (ROOT / "plugin.yaml").read_text(encoding="utf-8")
        self.assertEqual(manifest.splitlines()[0], "name: orphic-eyes")
        block = manifest.split("provides_tools:\n", 1)[1].split("provides_hooks:", 1)[0]
        names = [line.strip()[2:] for line in block.splitlines() if line.strip().startswith("- ")]
        expected = ["orphic_" + action for action in ("baseline", "compare", "approve", "accept", "ignore")]
        self.assertCountEqual(names, expected)
        package = "_orphic_naming_test"
        self.addCleanup(lambda: [sys.modules.pop(key, None) for key in list(sys.modules)
                                if key == package or key.startswith(package + ".")])
        context = FakeContext()
        load_package(package).register(context)
        self.assertEqual(set(context.tools), set(expected))
        self.assertTrue(all(entry[0] == "orphic" for entry in context.tools.values()))
        self.assertEqual(set(context.commands), {"orphic"})
