# Hermes plugin discovery (Stage 5)

## Confirmed before implementation

Source root on this machine: `C:/Users/User/AppData/Local/hermes/hermes-agent`.
Paths below are relative to that root unless absolute.

- `hermes plugins --help` and `hermes plugins validate --help` succeeded on
  2026-11-06 outside the restricted execution sandbox. The first sandboxed
  attempts exited 1 with empty stdout/stderr. Python executables were likewise
  denied by the sandbox; this was an execution permission issue, not a CLI defect.
- `hermes_cli/plugins.py:463`: `register_tool(self, name: str, toolset: str,
  schema: dict, handler: Callable, check_fn: Callable | None = None,
  requires_env: list | None = None, is_async: bool = False, description: str = "",
  emoji: str = "", override: bool = False) -> Optional[PluginRegistration]`.
- `hermes_cli/plugins.py:649`: `register_command(self, name: str,
  handler: Callable, description: str = "", args_hint: str = "",
  argument_mode: str | None = None) -> Optional[PluginRegistration]`.
- `hermes_cli/plugins.py:935`: `register_hook(self, hook_name: str,
  callback: Callable, *, hold_stream: bool = False) -> PluginRegistration`.
- `hermes_cli/plugin_command_dispatch.py:11`: command handlers receive the raw
  argument string as their first positional argument, plus only context keywords
  they declare (or all context if they accept `**kwargs`). The registration
  contract documents a sync/async `str | None` return. This plugin returns text.
- Read both `plugins/disk-cleanup/{plugin.yaml,__init__.py}` and
  `plugins/google_meet/{plugin.yaml,__init__.py}`. Disk-cleanup uses a relative
  import and a raw-string slash handler; google_meet registers tool schemas and
  handlers separately with keyword arguments. Neither is copied into this repo.
- `pm/plugin_declarations.py:118-173` accepts `python_dependencies: [Pillow]`
  or `pip_dependencies` in the manifest; a packaging `pyproject.toml` would take
  precedence. `hermes_cli/plugins_loader.py:235` uses this same declaration.
  No dependency installation is needed: Hermes Python already imports Pillow.
- `hermes_cli/plugins_loader.py:809-839` loads directory plugins as packages
  under `hermes_plugins.<slug>`, with `submodule_search_locations=[plugin_dir]`.
  Relative imports of plugin-owned modules are supported. The validator uses
  the same package mechanism (`hermes_cli/plugin_validate.py:295`).
- `hermes_constants.py:194`: `get_hermes_home() -> Path` is importable from an
  external Python process with the Hermes source on its import path. Confirmed
  by running Python 3.12 with bytecode disabled. It resolved this installation's
  home to `C:/Users/User/AppData/Local/hermes`. The validator's public-import
  allowlist also includes `hermes_constants`.
- Hermes interpreter:
  `C:/Users/User/AppData/Local/hermes/installs/6b17de8c14938a10/environments/5b0d085f340941ce8b4edc40ec61485e/venv/Scripts/python.exe`.
  Confirmed version **3.14.9**, installed Pillow **13.0.0**, import succeeded.
- `hermes plugins validate PATH --json` does not install dependencies unless
  `--install-deps` is supplied. Do not supply that flag for this task.
- `hermes_cli/plugin_dev.py` stages a temporary copy for doctor, uses a temporary
  Hermes home, blocks socket connections, and restores runtime registration.
  It does not install or enable the plugin in the user's Hermes home.

## Existing engine facts and implementation decisions

- `engine/store.py`: the store root is already configurable on every public
  store function. No new store-root option is needed.
- `engine/store.py:baseline` currently fixes the baseline viewport at 1280x800;
  `engine/capture.py:capture` already accepts width/height. Add optional keyword
  dimensions to baseline while preserving the existing defaults and CLI behavior.
- `engine/store.py:ignore_remove` takes a region label, not coordinates. The
  adapter must find the stored region matching the supplied rectangle and pass
  its existing label; do not invent an engine removal-by-rectangle option.
- `engine/report_json.py` uses `name`, `summary.changed_percent`, flat box
  coordinates, `label`, and `approved`. Preserve these names in tool results and
  add the requested convenience fields, `bbox` and `kind`.
- Persist the baseline URL in a plugin-owned sidecar because engine metadata
  does not store URLs. Explicit compare URL overrides do not change that default
  until accept promotes the latest capture and its URL to the new baseline.
- Reject invalid target names rather than silently mapping distinct names to
  one directory. Limit ASCII letters/digits/dash/underscore to 40 characters,
  retaining the engine's leading-character and Windows reserved-name checks.
- Local file input pages may reside outside the data directory (as required by
  fixture tests). Writes, browser profiles, and generated demo pages are confined
  to the data root. Browser dependencies/runtime and requested pages are read
  outside it; README must describe that boundary honestly.
- URL validation constrains the initial URL, not page subresources or redirects.
  An arbitrary local page can itself load network resources. Do not advertise
  this as a browser-level network sandbox; the embedded demo is fully offline.

## Verification results (2026-11-06)

- Before changes: Python 3.12.10, **52 tests passed** (14.554 s).
- Final Python 3.12.10 run: **73 tests run, OK, 1 skipped** (20.110 s).
  The skip is a real symlink creation test: Windows returns WinError 1314
  without the necessary privilege. Hard-link rejection is tested successfully.
- Final Python 3.14.9 run: **73 tests run, OK, 1 skipped** (20.198 s),
  with the same Windows symlink-privilege skip.
- An isolated package import with the repository absent from `sys.path` passes,
  including registering all handlers and importing the packaged engine CLI.
  Direct `python -m engine.cli --help` also passes without Hermes imports.
- Real handler workflow passes: baseline (1280x720), unchanged compare, changed
  fixture compare, approve all, accept, compare against the accepted URL.
- `/sightdiff doctor` via its handler, in Hermes Python, reports:

```text
✓ Python 3.14.9
✓ Pillow 13.0.0
✓ Data directory writable: C:\Users\User\Documents\ChatGPT\Orphic SightDiff\.stage5\handler-home\orphic-sightdiff
✓ Engine importable
✓ Browser: C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe — 156.0.4314.58
```

- `/sightdiff demo` via its handler passes offline: `Demo: check — Start trial
  moved 40 px right.`, `Changed: 0.515%`. Baseline/current/diff PNGs and input
  pages exist under the disposable home inside `.stage5/`; no HTML report exists.
- Catalog validation succeeds: `ok: true`, all 15 checks pass, no warnings,
  capability probe matches all five tools and zero hooks, security scan `safe`,
  no core overrides, isolation `host_ready: true`.

### Hermes launcher limitation (not a plugin failure)

Invoking the `hermes` launcher with a new temporary `HERMES_HOME` unexpectedly
starts dependency/runtime preparation. The attempt exited 1 after failing to
copy Hermes' own long conformance paths (WinError 3). It did not install/enable
this plugin. The scratch runtime was removed, after verifying its absolute path
was the repository's `.stage5/` directory. Visible output excerpts, verbatim:

```text
hermes: preparing dependencies for this data root (the checkout's updates belong to C:\Users\User\AppData\Local\hermes)...
Preparing the isolated Hermes runtime…
  → Installing Python dependencies…
  ✓ Installing Python dependencies
hermes: no dependency environment is committed for this install; run `hermes pm repair`
```

Subsequent checks invoke the **existing installed Hermes interpreter** with
`-B -m hermes_cli.main plugins ...`. This runs the same CLI implementation without
the launcher's environment setup, uses the existing Pillow installation, and
does not modify Hermes source or install dependencies. `PYTHONDONTWRITEBYTECODE=1`
is inherited by child probes; `HERMES_HOME`, `TEMP`, `TMP`, and `TMPDIR` point
inside `.stage5/` to respect the user's no-outside-repo-writes instruction.

### Runtime doctor limitation / permission pending

`plugins doctor --ci` rejects a temporary directory inside the plugin, by design:
`hermes_cli/plugin_dev.py:31-56` refuses the resulting recursive staging copy.
The following is the exact output (exit 1) from the installed-interpreter CLI:

```text
Plugin Doctor: C:\Users\User\Documents\ChatGPT\Orphic SightDiff
  ERROR: Refusing to stage C:\Users\User\Documents\ChatGPT\Orphic SightDiff:
C:\Users\User\Documents\ChatGPT\Orphic SightDiff leads into Doctor's temporary
directory C:\Users\User\Documents\ChatGPT\Orphic
SightDiff\.stage5\tmp\hermes-plugin-doctor-xjfpukt6\plugins, so the copy would
recurse into itself. Point TMPDIR outside the plugin and remove links to it.
  registrations: 0 tool(s), 0 hook(s)
```

No workaround or Hermes modification was applied. Asked the user whether to
permit doctor's automatically removed temporary staging folder outside the repo;
this exception is needed to complete the runtime check on the actual checkout.
The catalog validator and plugin's own `/sightdiff doctor` are independently green.

## Additive engine changes

- Only `engine/store.py:baseline` changed: optional keyword-only `width=1280`,
  `height=800`, dimension validation, forwarding those values to capture and
  metadata. Existing calls, CLI defaults, statuses, JSON names, exit codes and
  all 52 original tests remain unchanged. Store roots were already configurable.
- Browser detection already includes Windows, macOS and Linux candidates; no
  detection changes were needed. macOS/Linux execution remains **UNVERIFIED**.

## Remaining UNVERIFIED / open question

- Runtime doctor awaits the requested temporary-directory exception; no plugin
  is installed or enabled in the user's Hermes.
- Real symlink behavior could not be exercised without Windows symlink privilege;
  confinement checks and real hard-link rejection are covered.
- No network install of Pillow was attempted. Its existing 13.0.0 installation
  imports and runs image/browser tests under Hermes Python 3.14.9.
