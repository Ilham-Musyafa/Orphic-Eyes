"""Deterministic HTTP/HTTPS screenshots and paired-URL pixel reports.

The older engine.capture module remains the local-file compatibility API.
This API never reads page source, DOM contents or computed styles. DevTools is
used only for navigation, browser rendering settings and PNG capture.
"""

import base64
from contextlib import ExitStack
import http.client
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time

from PIL import Image

from ._devtools import DevTools
from ._url_network import GuardedProxy, URLPolicyError, URLResolutionError, destination
from .capture import detect_browser


class CaptureError(RuntimeError):
    """Capture failure safe to show to users (no source URL or browser log)."""


class BrowserNotFound(CaptureError):
    pass


class CaptureTimeout(CaptureError):
    pass


# Install a rendering override, not a page inspection. No page content is read.
_DISABLE_MOTION = """(() => {
  const install = () => {
    const style = document.createElement('style');
    style.textContent = '*,*::before,*::after{animation:none!important;transition:none!important;caret-color:transparent!important;scroll-behavior:auto!important}::-webkit-scrollbar{display:none!important}';
    document.documentElement.appendChild(style);
  };
  if (document.documentElement) install();
  else document.addEventListener('DOMContentLoaded', install, {once:true});
})();"""


def validate_url(url, *, allow_local=False, timeout=5):
    """Return None, or a URL-free error; validate DNS as well as URL syntax."""
    if not isinstance(allow_local, bool):
        return "allow_local must be a boolean"
    try:
        destination(url, allow_local, timeout)
        return None
    except (URLPolicyError, URLResolutionError, TimeoutError) as exc:
        return str(exc)


def _options(width, height, full_page, wait_ms, timeout_ms, allow_local):
    if any(isinstance(v, bool) or not isinstance(v, int) or v <= 0 for v in (width, height)):
        raise CaptureError("width and height must be positive integers")
    if not isinstance(full_page, bool) or not isinstance(allow_local, bool):
        raise CaptureError("full_page and allow_local must be booleans")
    if isinstance(wait_ms, bool) or not isinstance(wait_ms, int) or wait_ms < 0:
        raise CaptureError("wait_ms must be a nonnegative integer")
    if isinstance(timeout_ms, bool) or not isinstance(timeout_ms, int) or timeout_ms <= wait_ms:
        raise CaptureError("timeout_ms must be an integer greater than wait_ms")


def _remaining(deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise CaptureTimeout("URL capture timed out")
    return remaining


def _stop(browser, client=None):
    if client is not None:
        try:
            client.call("Browser.close")
        except (RuntimeError, OSError):
            pass  # The browser may close its debugging socket before replying.
        finally:
            client.close()
        try:
            browser.wait(timeout=0.5)
            return
        except subprocess.TimeoutExpired:
            pass
    if browser.poll() is None:
        browser.terminate()
        try:
            browser.wait(timeout=0.5 if client is not None else 1)
        except subprocess.TimeoutExpired:
            browser.kill()
            browser.wait(timeout=1)


def _endpoint(profile, browser, deadline):
    port_file = profile / "DevToolsActivePort"
    # The port file and the first page target become available separately.
    # Do not mistake a partial file or an empty /json/list for capture failure.
    while True:
        if browser.poll() is not None:
            raise CaptureError("Browser could not start; check browser sandbox/launch permissions")
        connection = None
        try:
            lines = port_file.read_text(encoding="ascii").splitlines()
            port = int(lines[0])
            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=_remaining(deadline))
            connection.request("GET", "/json/list")
            response = connection.getresponse()
            if response.status == 200:
                targets = json.loads(response.read(1024 * 1024))
                for target in targets:
                    if target.get("type") == "page" and target.get("webSocketDebuggerUrl"):
                        return target["webSocketDebuggerUrl"]
        except (OSError, ValueError, IndexError, http.client.HTTPException):
            _remaining(deadline)
        finally:
            if connection is not None:
                connection.close()
        time.sleep(min(0.02, _remaining(deadline)))


def _events(client, loader_id, frame_id, proxy, seen):
    if proxy.violation:
        raise CaptureError(proxy.violation)
    pending, client.events = client.events, []
    for event in pending:
        method, data = event["method"], event.get("params", {})
        if method == "Page.lifecycleEvent" and data.get("loaderId") == loader_id:
            seen.add(data.get("name"))
        if method == "Network.responseReceived" and data.get("type") == "Document" and data.get("frameId") == frame_id:
            status = data["response"]["status"]
            if status >= 400:
                raise CaptureError(proxy.violation or f"URL navigation failed (HTTP {int(status)})")
        if method == "Page.frameNavigated" and data["frame"].get("id") == frame_id:
            from ._url_network import parse_url
            parse_url(data["frame"]["url"])
        if method == "Page.javascriptDialogOpening":
            client.call("Page.handleJavaScriptDialog", {"accept": False})
    if proxy.violation:
        raise CaptureError(proxy.violation)


def capture(url, out_path, width=1440, height=900, full_page=False, wait_ms=250,
            *, timeout_ms=30000, allow_local=False, browser=None):
    """Save a PNG and return its Path, or raise a clear CaptureError.

    timeout_ms bounds DNS, browser startup, navigation/network idle, extra wait
    and screenshot capture together (plus at most two seconds for cleanup).
    allow_local permits private HTTP(S) destinations, never file/data/javascript.
    ORPHIC_BROWSER or browser can select an installed executable explicitly.
    Existing output is replaced only after a complete, validated PNG is ready.
    """
    _options(width, height, full_page, wait_ms, timeout_ms, allow_local)
    deadline = time.monotonic() + timeout_ms / 1000
    phase = "startup"
    try:
        destination(url, allow_local, min(5, _remaining(deadline)))
        executable = detect_browser(browser or os.environ.get("ORPHIC_BROWSER"))
        if executable is None:
            raise BrowserNotFound("Browser not found: install Edge, Chrome or Chromium, or set ORPHIC_BROWSER")
        output = Path(out_path).absolute()
        if output.is_symlink() or (output.exists() and (not output.is_file() or output.stat().st_nlink > 1)):
            raise CaptureError("PNG output must be a regular file without links")
        output.parent.mkdir(parents=True, exist_ok=True)
        with ExitStack() as cleanup:
            # A short system-temp profile avoids the Linux Unix-socket limit.
            profile = Path(cleanup.enter_context(tempfile.TemporaryDirectory(prefix="oe_")))
            proxy = GuardedProxy(allow_local, deadline)
            cleanup.callback(proxy.close)
            environment = os.environ.copy()
            environment.update(TMP=str(profile), TEMP=str(profile), TMPDIR=str(profile))
            command = [executable, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                       "--force-device-scale-factor=1", "--force-prefers-reduced-motion",
                       "--no-first-run", "--no-default-browser-check", "--disable-extensions",
                       "--disable-background-networking", "--disable-component-update",
                       "--disable-sync", "--disable-quic",
                       "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
                       "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1",
                       f"--proxy-server=http://127.0.0.1:{proxy.server_port}",
                       "--proxy-bypass-list=<-loopback>", "--remote-debugging-port=0",
                       "--remote-debugging-address=127.0.0.1",
                       f"--user-data-dir={profile}", f"--window-size={width},{height}", "about:blank"]
            try:
                process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=environment)
            except OSError:
                raise BrowserNotFound("Browser could not be launched; check executable and permissions") from None
            clients = []
            cleanup.callback(lambda: _stop(process, clients[0] if clients else None))
            client = DevTools(_endpoint(profile, process, deadline), deadline)
            clients.append(client)
            client.call("Page.enable")
            client.call("Network.enable")
            client.call("Network.setCacheDisabled", {"cacheDisabled": True})
            client.call("Network.setBypassServiceWorker", {"bypass": True})
            client.call("Page.setLifecycleEventsEnabled", {"enabled": True})
            client.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": height,
                                                             "deviceScaleFactor": 1, "mobile": False})
            client.call("Emulation.setEmulatedMedia", {"features": [
                {"name": "prefers-reduced-motion", "value": "reduce"},
                {"name": "prefers-color-scheme", "value": "light"}]})
            client.call("Animation.enable")
            client.call("Animation.setPlaybackRate", {"playbackRate": 0})
            client.call("Page.addScriptToEvaluateOnNewDocument", {"source": _DISABLE_MOTION})
            client.call("Browser.setDownloadBehavior", {"behavior": "deny"})
            phase = "navigation"
            navigation = client.call("Page.navigate", {"url": url})
            if navigation.get("errorText"):
                raise CaptureError(proxy.violation or "URL navigation failed; check destination access and TLS trust")
            seen = set()
            loader_id, frame_id = navigation.get("loaderId"), navigation["frameId"]
            while "networkIdle" not in seen:
                _events(client, loader_id, frame_id, proxy, seen)
                if "networkIdle" in seen:
                    break
                if client.events:
                    continue
                event = client.receive()
                if "method" in event:
                    client.events.append(event)
            # Consume events while waiting; this also detects late blocked loads.
            finish = time.monotonic() + wait_ms / 1000
            while time.monotonic() < finish:
                _remaining(deadline)
                client.call("Page.getLayoutMetrics")
                _events(client, loader_id, frame_id, proxy, seen)
                time.sleep(min(0.02, max(0, finish - time.monotonic())))
            size = {"width": width, "height": height}
            if full_page:
                import math
                content = client.call("Page.getLayoutMetrics")["cssContentSize"]
                size = {key: max(size[key], math.ceil(content[key])) for key in size}
            phase = "screenshot"
            png = client.call("Page.captureScreenshot", {"format": "png", "fromSurface": True,
                              "captureBeyondViewport": full_page,
                              "clip": {"x": 0, "y": 0, **size, "scale": 1}})
            _events(client, loader_id, frame_id, proxy, seen)
            temporary = cleanup.enter_context(tempfile.NamedTemporaryFile(dir=output.parent, suffix=".png", delete=False))
            candidate = Path(temporary.name)
            cleanup.callback(lambda: candidate.unlink(missing_ok=True))
            temporary.write(base64.b64decode(png["data"], validate=True))
            temporary.close()
            with Image.open(candidate) as image:
                if image.format != "PNG" or image.size != (size["width"], size["height"]):
                    raise CaptureError("Browser returned an invalid PNG or unexpected screenshot dimensions")
                image.verify()
            os.replace(candidate, output)
            phase = "browser cleanup"
        return output
    except CaptureError:
        raise
    except (TimeoutError, socket.timeout):
        raise CaptureTimeout("URL capture timed out during DNS, navigation/network idle or screenshot") from None
    except (URLPolicyError, URLResolutionError) as exc:
        raise CaptureError(str(exc)) from None
    except Exception:
        # OS/browser errors can include source URLs, query tokens or paths.
        raise CaptureError("URL capture failed during " + phase + "; check browser launch permissions, output access and destination availability") from None


def capture_pair(before_url, after_url, store_dir, *, name="urls", width=1440, height=900,
                 wait_ms=250, timeout_ms=30000, allow_local=False, browser=None):
    """Capture equal viewports, then use the existing diff/report pipeline.

    Each capture has its own timeout_ms deadline. A nonempty target is rejected
    to preserve prior baselines, approvals and reports; choose a fresh name.
    Source URLs and queries are never persisted in report metadata or logs.
    Return the existing report dictionary (including paths), or status=error.
    """
    from .compare import compare_images
    from .report_json import build_report, write_report
    from .store import _atomic_json, _case_dir, _metadata

    try:
        _options(width, height, False, wait_ms, timeout_ms, allow_local)
        for url in (before_url, after_url):
            error = validate_url(url, allow_local=allow_local, timeout=min(5, timeout_ms / 1000))
            if error:
                raise CaptureError(error)
        case = _case_dir(store_dir, name, create=True)
        if case.is_symlink() or case.resolve() != Path(store_dir).resolve() / name:
            raise CaptureError("URL capture target must not redirect to another directory")
        if any(case.iterdir()):
            raise CaptureError("URL capture target is not empty; choose a fresh name to preserve existing artifacts")
        executable = detect_browser(browser or os.environ.get("ORPHIC_BROWSER"))
        if executable is None:
            raise BrowserNotFound("Browser not found: install Edge, Chrome or Chromium, or set ORPHIC_BROWSER")
        # Build in staging so a failed second capture never publishes half a pair.
        with tempfile.TemporaryDirectory(prefix=".url_", dir=case.parent) as folder:
            stage = Path(folder)
            for url, filename in ((before_url, "baseline.png"), (after_url, "current.png")):
                capture(url, stage / filename, width, height, wait_ms=wait_ms,
                        timeout_ms=timeout_ms, allow_local=allow_local, browser=executable)
            comparison = compare_images(stage / "baseline.png", stage / "current.png", stage / "diff.png")
            if comparison["status"] == "error":
                raise CaptureError("Captured image comparison failed")
            metadata = _metadata(executable, width, height, 0)
            report = build_report(name, comparison, metadata)
            saved = write_report(report, stage / "report.json")
            if saved.get("status") == "error":
                raise CaptureError("URL comparison report could not be written")
            _atomic_json(stage / "metadata.json", metadata)
            for artifact in stage.iterdir():
                os.replace(artifact, case / artifact.name)
            paths = {"report": str(case / "report.json"), "baseline": str(case / "baseline.png"),
                     "after": str(case / "current.png"), "diff": str(case / "diff.png")}
            if (case / "report.html").is_file():
                paths["html"] = str(case / "report.html")
            from .serve import attach_report_link
            return attach_report_link({**saved, "paths": paths}, store_dir, case)
    except (CaptureError, ValueError) as exc:
        return {"status": "error", "error": str(exc)}
    except Exception:
        return {"status": "error", "error": "URL comparison failed; check output access and browser availability"}
