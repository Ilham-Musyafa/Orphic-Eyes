"""Synchronous /orphic commands; diagnostics never print to stdout."""

import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

if __package__:
    from . import orphic_tools as tools
else:
    import orphic_tools as tools

HELP = """/orphic help    Show commands
/orphic doctor  Check Python, Pillow, browser, data directory and engine
/orphic demo    Capture two offline demo pages and compare a 40 px button move

Tools: orphic_baseline, orphic_compare, orphic_loop_step,
orphic_approve, orphic_accept, orphic_ignore.
Baseline/legacy compare: local http://localhost, http://127.0.0.1 or file://.
Compare URL pairs and loop steps: HTTP/HTTPS; private destinations require allow_local=true.
HTML requires an optional template.
Demo replaces only the target named demo; its files live under the data directory.
"""


def _browser_version(path, root):
    if os.name == "nt":
        # Chromium's --version can launch a GUI on Windows. Read the executable's
        # version resource instead; no shell or extra browser process is needed.
        import ctypes
        from ctypes import wintypes

        api = ctypes.WinDLL("version", use_last_error=True)
        api.GetFileVersionInfoSizeW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD)]
        api.GetFileVersionInfoSizeW.restype = wintypes.DWORD
        api.GetFileVersionInfoW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD,
                                          wintypes.DWORD, wintypes.LPVOID]
        api.VerQueryValueW.argtypes = [wintypes.LPCVOID, wintypes.LPCWSTR,
                                      ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wintypes.UINT)]
        size = api.GetFileVersionInfoSizeW(str(path), None)
        if not size:
            raise RuntimeError("browser version resource unavailable")
        data = ctypes.create_string_buffer(size)
        pointer, length = ctypes.c_void_p(), wintypes.UINT()
        if not api.GetFileVersionInfoW(str(path), 0, size, data) or not api.VerQueryValueW(
                data, "\\", ctypes.byref(pointer), ctypes.byref(length)) or length.value < 16:
            raise RuntimeError("browser version resource unreadable")
        words = ctypes.cast(pointer, ctypes.POINTER(wintypes.DWORD))
        return ".".join(str(part) for part in (words[2] >> 16, words[2] & 65535,
                                              words[3] >> 16, words[3] & 65535))
    environment = os.environ.copy()
    environment.update(TMP=str(root), TEMP=str(root), TMPDIR=str(root))
    result = subprocess.run([str(path), "--version"], capture_output=True, text=True,
                            timeout=10, env=environment, check=True)
    version = " ".join(result.stdout.split())[:180]
    if not version:
        raise RuntimeError("browser returned no version")
    return version


def doctor():
    lines = []
    supported = sys.version_info >= (3, 12)
    lines.append(("✓" if supported else "✗") + " Python " + sys.version.split()[0]
                 + ("" if supported else " — Fix: use Python 3.12 or later."))
    try:
        pillow = importlib.import_module("PIL")
        lines.append("✓ Pillow " + pillow.__version__)
    except Exception:
        lines.append("✗ Pillow unavailable — Fix: install the declared Pillow dependency in Hermes' Python environment.")
    root = None
    try:
        root = tools.resolve_data_dir()
        root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryFile(dir=root) as probe:
            probe.write(b"orphic doctor")
            probe.flush()
        lines.append("✓ Data directory writable: " + str(root))
    except Exception as exc:
        lines.append("✗ Data directory: " + str(exc)
                     + " — Fix: set HERMES_HOME to a writable directory without redirected data paths.")
    try:
        for module in ("capture", "compare", "regions", "report_json", "store", "cli"):
            tools._module(module)
        lines.append("✓ Engine importable")
    except Exception as exc:
        lines.append("✗ Engine: " + str(exc)
                     + " — Fix: restore the plugin's engine package and install its Pillow dependency.")
    try:
        browser = tools._module("capture").detect_browser()
        if browser is None:
            raise RuntimeError("no supported browser found")
        version = _browser_version(browser, root) if root is not None else "unknown (data directory unavailable)"
        lines.append("✓ Browser: " + str(browser) + " — " + version)
    except Exception as exc:
        lines.append("✗ Browser: " + str(exc)
                     + " — Fix: install Edge, Chrome or Chromium and make the executable discoverable.")
    return "\n".join(lines)


def demo():
    root = tools.resolve_data_dir()
    folder = tools._case(root, "demo", create=True)
    page = """<!doctype html><html lang="en"><meta charset="utf-8">
<title>Orphic Eyes offline demo</title><style>
*{box-sizing:border-box}body{margin:0;background:#f4f6fb;font-family:Arial,sans-serif}
main{padding:64px}h1{margin:0;color:#202939;font-size:32px}
p{color:#526078}button{position:absolute;left:LEFTpx;top:180px;width:160px;
height:48px;background:#5145cd;color:white;border:0;border-radius:12px;
font:700 16px Arial,sans-serif}
</style><main><h1>Orphic Eyes</h1><p>A local, offline visual check.</p>
<button>Start trial</button></main></html>"""
    before = tools._safe_file(folder, "before.html")
    after = tools._safe_file(folder, "after.html")
    before.write_text(page.replace("LEFT", "64"), encoding="utf-8")
    after.write_text(page.replace("LEFT", "104"), encoding="utf-8")
    baseline = json.loads(tools.handle_baseline({"name": "demo", "url": before.as_uri()}))
    if not baseline["success"]:
        return "Demo baseline failed: " + baseline["error"] + "\nFix: " + baseline["fix"]
    result = json.loads(tools.handle_compare({"name": "demo", "url": after.as_uri()}))
    if not result["success"]:
        return "Demo compare failed: " + result["error"] + "\nFix: " + result["fix"]
    lines = ["Demo: " + result["status"] + " — Start trial moved 40 px right.",
             "Changed: " + str(result["changed_percent"]) + "%", "Before page: " + str(before),
             "After page: " + str(after)]
    lines += [key + ": " + str(path) for key, path in result["paths"].items()]
    lines.append("Review the PNGs; approve if intended. paths.html is included only when a report page was generated.")
    return "\n".join(lines)


def handle_command(raw_args: str, **_kw) -> str:
    try:
        if not isinstance(raw_args, str):
            return HELP
        command = raw_args.strip() or "help"
        if command in ("help", "-h", "--help"):
            return HELP
        if command == "doctor":
            return doctor()
        if command == "demo":
            return demo()
        return "Unknown command.\n" + HELP
    except Exception as exc:
        failure = json.loads(tools._failure(exc))
        return "Orphic Eyes: " + failure["error"] + "\nFix: " + failure["fix"]
