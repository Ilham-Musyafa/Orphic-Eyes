"""Bounded shutdown for the browser process tree owned by one capture."""

import os
import errno
import signal
import shutil
import subprocess
import time


def launch_options():
    # A dedicated session lets cleanup reach renderers even if the leader exits.
    return {"start_new_session": True} if os.name == "posix" else {}


def _signal_tree(process, force=False, *, timeout=0.5):
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGKILL if force else signal.SIGTERM)
        except ProcessLookupError:
            pass
    elif process.poll() is None:
        # Chromium is multiprocess on Windows too. Do not kill unrelated browsers.
        try:
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=timeout, check=False)
        except (OSError, subprocess.TimeoutExpired):
            process.kill()


def stop_browser(process, client=None):
    """Close DevTools, then terminate/kill owned children before profile removal.

    The capture's navigation deadline may have expired; cleanup gets its own
    small allowance, never the remaining navigation timeout (or an unbounded wait).
    """
    deadline = time.monotonic() + 1.75

    def allowance():
        return max(0.001, min(0.5, deadline - time.monotonic()))

    try:
        if client is not None:
            client.deadline = time.monotonic() + 0.25
            try:
                client.call("Browser.close")
            except (RuntimeError, OSError, TimeoutError):
                pass
            finally:
                client.close()
            try:
                process.wait(timeout=allowance())
            except subprocess.TimeoutExpired:
                pass
    finally:
        try:
            _signal_tree(process, timeout=allowance())
            if process.poll() is None:
                try:
                    process.wait(timeout=allowance())
                except subprocess.TimeoutExpired:
                    pass
        finally:
            # Also catch children still writing to the profile after root exit.
            _signal_tree(process, force=True, timeout=allowance())
            if process.poll() is None:
                process.wait(timeout=allowance())


def remove_profile(profile):
    """Allow killed children a bounded moment to release profile files."""
    deadline = time.monotonic() + 0.25
    while True:
        try:
            shutil.rmtree(profile)
            return
        except OSError as exc:
            if exc.errno == errno.ENOENT and not os.path.exists(profile):
                return
            if exc.errno not in (errno.ENOENT, errno.ENOTEMPTY, errno.EACCES, errno.EBUSY) or time.monotonic() >= deadline:
                raise
            time.sleep(0.01)
