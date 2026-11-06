"""Local screenshot capture using the reference script's browser flags."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from urllib.parse import unquote, urlsplit

from PIL import Image


def validate_url(url):
    """Return None for an allowed local URL; otherwise return an error string."""
    try:
        if not isinstance(url, str) or not url or any(ord(c) <= 32 or ord(c) == 127 for c in url):
            return "URL must be a nonempty string without spaces or control characters"
        parts = urlsplit(url)
        if "\\" in url or parts.username is not None or parts.password is not None:
            return "URL must not contain credentials or backslashes"
        if parts.scheme == "http":
            if parts.hostname not in ("localhost", "127.0.0.1"):
                return "only http://localhost, http://127.0.0.1 and local file:// URLs are allowed"
            if parts.port is not None and not 1 <= parts.port <= 65535:
                return "URL port must be from 1 to 65535"
            return None
        if parts.scheme == "file":
            path = unquote(parts.path)
            if parts.netloc.lower() not in ("", "localhost") or not path.startswith("/"):
                return "file:// URL must refer to a local absolute path"
            if path.startswith("//") or "\\" in path or "\x00" in path:
                return "network file paths are not allowed"
            return None
        return "only http://localhost, http://127.0.0.1 and local file:// URLs are allowed"
    except Exception as exc:
        return "invalid URL: " + str(exc)


def detect_browser(browser=None):
    """Return a browser path or None, using the reference detection order."""
    try:
        if browser:
            return os.fspath(browser) if Path(browser).is_file() else None
        candidates = [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            "/usr/bin/google-chrome",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ]
        for candidate in candidates:
            if Path(candidate).is_file():
                return candidate
        for name in ("msedge", "chrome", "google-chrome", "chromium"):
            found = shutil.which(name)
            if found:
                return found
        return None
    except Exception:
        return None


def capture(url, out_png, browser=None, width=1280, height=800):
    """Capture a local URL, returning False for any bad input or capture failure.

    out_png's parent is the caller-supplied store for this low-level API.
    Browser profiles and child-process temporary files stay in that directory.
    """
    profile = None
    proc = None
    try:
        if validate_url(url) is not None:
            return False
        if any(isinstance(v, bool) or not isinstance(v, int) or v <= 0
               for v in (width, height)):
            return False
        executable = detect_browser(browser)
        if executable is None:
            return False
        output = Path(out_png)
        if output.is_symlink() or (output.exists() and output.stat().st_nlink > 1):
            return False
        output = output.absolute()
        output.parent.mkdir(parents=True, exist_ok=True)
        if output.exists():
            output.unlink()
        profile = tempfile.mkdtemp(prefix="sightdiff_profile_", dir=output.parent)
        cmd = [
            executable,
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            "--force-device-scale-factor=1",
            "--force-prefers-reduced-motion",
            "--run-all-compositor-stages-before-draw",
            "--virtual-time-budget=2000",
            f"--window-size={width},{height}",
            f"--user-data-dir={profile}",
            f"--screenshot={output}",
            url,
        ]
        environment = os.environ.copy()
        environment.update(TMP=profile, TEMP=profile, TMPDIR=profile)
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, env=environment)
        try:
            proc.wait(timeout=45)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        if not output.is_file() or output.stat().st_size == 0:
            return False
        with Image.open(output) as screenshot:
            if screenshot.format != "PNG":
                return False
            screenshot.verify()
        return True
    except Exception:
        return False
    finally:
        if proc is not None and proc.poll() is None:
            try:
                proc.kill()
                proc.wait()
            except OSError:
                pass
        if profile is not None:
            shutil.rmtree(profile, ignore_errors=True)
