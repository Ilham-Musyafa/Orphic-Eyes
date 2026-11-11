"""One native startup probe, shared by pytest and unittest browser tests.

Probe only browser availability. Screenshot, proxy, matching and JS assertions
remain in the tests and must fail normally once startup succeeds.
"""

from functools import lru_cache
import http.client
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

from engine.capture import detect_browser
from engine._browser_process import launch_options, stop_browser


@lru_cache(maxsize=None)
def probe_browser(executable):
    if executable is None:
        return "No installed Edge/Chrome/Chromium; install one or set ORPHIC_BROWSER"
    with tempfile.TemporaryDirectory(prefix="oe_probe_") as profile:
        process = None
        try:
            process = subprocess.Popen(
                [executable, "--headless=new", "--disable-gpu", "--no-first-run",
                 "--disable-background-networking", "--remote-debugging-port=0",
                 "--user-data-dir=" + profile, "about:blank"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **launch_options())
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    return f"No usable system browser: {executable} exited {process.returncode} during headless startup; check sandbox/launch permissions"
                try:
                    port = int((Path(profile) / "DevToolsActivePort").read_text().splitlines()[0])
                    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=0.2)
                    try:
                        connection.request("GET", "/json/version")
                        version = json.loads(connection.getresponse().read())
                        if version.get("webSocketDebuggerUrl"):
                            return None
                    finally:
                        connection.close()
                except (OSError, ValueError, IndexError, http.client.HTTPException):
                    pass
                time.sleep(0.02)
            return f"No usable system browser: {executable} did not expose DevTools within the 5s startup probe; check sandbox/launch permissions"
        except OSError:
            return f"No usable system browser: cannot launch {executable}; check executable/permissions"
        finally:
            if process is not None:
                stop_browser(process)


def require_browser(executable=None):
    executable = executable or detect_browser(os.environ.get("ORPHIC_BROWSER"))
    reason = probe_browser(executable)
    if reason:
        raise unittest.SkipTest(reason)
    return executable
