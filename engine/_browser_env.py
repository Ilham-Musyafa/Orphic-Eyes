"""Minimal environment for browser subprocesses.

The browser never needs the agent's secrets. Only variables required to find
system libraries, render headlessly and honour the user's proxy are passed;
API keys, tokens and provider settings are never forwarded.
"""

import os

_ALLOWED = frozenset({
    "PATH", "HOME", "USERPROFILE", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT",
    "LOCALAPPDATA", "APPDATA",
    "DISPLAY", "WAYLAND_DISPLAY", "XDG_RUNTIME_DIR", "XAUTHORITY", "LANG", "TZ",
    "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "ALL_PROXY",
})
_PREFIXES = ("PROGRAMFILES", "LC_")


def browser_env(tmp_dir, source=None):
    """Return an allowlisted copy of the environment with temp dirs at tmp_dir."""
    source = os.environ if source is None else source
    environment = {}
    for key, value in source.items():
        upper = key.upper()
        if upper in _ALLOWED or upper.startswith(_PREFIXES):
            environment[key] = value
    tmp = os.fspath(tmp_dir)
    environment.update(TMP=tmp, TEMP=tmp, TMPDIR=tmp)
    return environment
