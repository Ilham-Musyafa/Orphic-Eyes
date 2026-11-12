"""Lifecycle regressions use real child processes, without requiring a browser."""

import os
import errno
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from engine._browser_process import launch_options, remove_profile, stop_browser


class BrowserProcessTests(unittest.TestCase):
    def test_profile_removal_retries_racing_browser_write(self):
        import shutil
        with tempfile.TemporaryDirectory(prefix="oe_cleanup_") as folder:
            profile = Path(folder) / "profile"
            profile.mkdir()
            (profile / "Local State").write_text("browser state", encoding="utf-8")
            original = shutil.rmtree
            attempts = 0

            def racing_remove(path):
                nonlocal attempts
                attempts += 1
                if attempts == 1:
                    raise OSError(errno.ENOTEMPTY, "browser still releasing profile")
                original(path)

            with patch("engine._browser_process.shutil.rmtree", side_effect=racing_remove) as remove:
                remove_profile(profile)
                self.assertEqual(remove.call_count, 2)
            self.assertFalse(profile.exists())

    def test_expired_navigation_deadline_gets_bounded_cleanup_and_fallback(self):
        process, client = Mock(), Mock()
        process.poll.return_value = 0
        client.deadline = time.monotonic() - 1
        client.call.side_effect = TimeoutError("Browser.close did not reply")
        started = time.monotonic()
        with patch("engine._browser_process._signal_tree") as signal_tree:
            stop_browser(process, client)
        self.assertGreater(client.deadline, started)
        self.assertLessEqual(client.deadline, started + 0.3)
        client.close.assert_called_once()
        self.assertEqual(signal_tree.call_count, 2)

    def test_kill_fallback_is_bounded_when_terminate_is_ignored(self):
        process = Mock()
        process.poll.side_effect = [None, None]
        process.wait.side_effect = [subprocess.TimeoutExpired("browser", 0.5), 0]
        with patch("engine._browser_process._signal_tree") as signal_tree:
            stop_browser(process)
        self.assertTrue(signal_tree.call_args_list[-1].kwargs["force"])
        self.assertTrue(all(0 < call.kwargs["timeout"] <= 0.5 for call in process.wait.call_args_list))

    @unittest.skipUnless(sys.platform == "linux", "Linux /proc process-tree regression")
    def test_kills_renderer_even_after_browser_leader_exits(self):
        with tempfile.TemporaryDirectory(prefix="oe_tree_") as folder:
            ready = Path(folder) / "ready"
            child_code = ("import os,signal,time; from pathlib import Path; "
                          "signal.signal(signal.SIGTERM,signal.SIG_IGN); "
                          f"Path({str(ready)!r}).write_text(str(os.getpid())); time.sleep(30)")
            parent_code = ("import subprocess,sys; "
                           f"subprocess.Popen([sys.executable,'-c',{child_code!r}])")
            process = subprocess.Popen([sys.executable, "-c", parent_code], **launch_options())
            try:
                process.wait(timeout=5)
                deadline = time.monotonic() + 5
                while not ready.exists() and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertTrue(ready.exists(), "renderer did not start")
                renderer = int(ready.read_text(encoding="utf-8"))
                stop_browser(process)
                deadline = time.monotonic() + 1
                while time.monotonic() < deadline:
                    try:
                        state = Path(f"/proc/{renderer}/stat").read_text(encoding="utf-8").split()[2]
                    except FileNotFoundError:
                        break
                    if state == "Z":  # Awaiting the system reaper; cannot write to a profile.
                        break
                    time.sleep(0.01)
                else:
                    self.fail("renderer survived cleanup after leader exit")
            finally:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
