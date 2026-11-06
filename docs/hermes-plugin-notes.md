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
  does not store URLs. Explicit compare URL overrides do not change that default.
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

## UNVERIFIED / pending validation

- macOS/Linux browser paths and execution are untested on this Windows machine.
- Test counts, CLI admission validation, runtime doctor, slash doctor/demo and
  installed-package imports will be recorded after implementation.
