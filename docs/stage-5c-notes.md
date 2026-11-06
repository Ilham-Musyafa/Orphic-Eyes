# Stage 5c evidence

## Step 0: exact horizontal move

Baseline `tests/fixtures/move_104.html` and after `move_74.html`: a flat-color,
borderless, square-corner 190x48 button, y=180, left 104 -> 74. Captured through
`baseline` then `compare` using local file URLs in Edge 156.0.4314.58.

Raw boxes:
```json
[{"id":1,"x":74,"y":180,"w":30,"h":48,"zone":"top-left","percent":0.141,"label":"unexpected","approved":false},{"id":2,"x":264,"y":180,"w":30,"h":48,"zone":"top-left","percent":0.141,"label":"unexpected","approved":false}]
```

Changed pixels: 2880. The union's bounds are x=74..294, width=220. Boxes bound
changed pixel clusters, not DOM elements: the overlapping flat interior does not
change. No too-narrow-box engine bug was reproduced, so no box algorithm change
was made. The original observed page/capture is unavailable: its contents and
the cause of its single 190px box are **UNVERIFIED**. Regression tests pin the
two edge strips, not an invented DOM-element union box.

Before changes: 73 tests, OK (1 Windows symlink privilege skip), Python 3.12.10.

## Steps and green checkpoints

| Step | Commit | Suite after step (Python 3.12) |
| --- | --- | --- |
| 0: reproduce pixel-box bounds | `6a55472` | 74 tests, 1 skip |
| 1: bounded crop locate + full-resolution ambiguity certification | `275c00f` | 78 tests, 1 skip |
| 2: request verification, CLI input, independent verdicts and compact output | `aca0eb7` | 90 tests, 1 skip |
| 3: safe focus crops and scale metadata | `ac011bd` | 94 tests, 2 skips |
| 4: small-box shift hints | `c2ec04a` | 96 tests, 2 skips |
| 5: presets with real PNG dimension checks | `1feff5f` | 100 tests, 2 skips |
| 6: contract, descriptions, dependency alignment, final guards/tests | Current Stage 5c final commit | 106 tests, 2 skips |

Final suites: Python 3.12.10 **106 tests, OK (2 skipped), 37.707s**;
Hermes Python 3.14.9 / Pillow 13.0.0 **106 tests, OK (2 skipped), 37.664s**.
These final runs overlapped; neither reported failures or request-budget misses.
All original tests remain unchanged. Both skips concern real Windows symlink
creation (WinError 1314); real hard-link guards pass. No plugin installation or
activation was performed.

## Matching thresholds, boundaries and timing

Final thresholds remain `MATCH_MIN=0.92`, `UNIQUE_GAP=0.03`, `SEARCH_PAD=64`.
Uniqueness distance: 4 Euclidean pixels. Exact tolerance: 2 px per axis;
approximate: 8 px per axis. Score uses mean absolute grayscale error / 255.
Flat or repeated content does not establish a unique location. The matcher uses
coarse candidates, full-resolution refinement and conservative block-error
bounds to check remaining plausible competitors. Low-score numbers are best
observed scores, with threshold absence checked, not claimed locations.

Eight repeated 190x48 matches on 1280x720, before final crop integration:
0.8223 / 0.8180 / 0.8137 seconds. The earlier coarse-only 0.43s measurement was
superseded by full-resolution ambiguity certification.

Reproducible final benchmark: `python -m tests.benchmark_roundtrip`. It mocks
browser capture to exclude browser startup, creates eight *distinct* 190x48
textures on a 1280x720 image, moves each left 30px, and times the entire engine
compare including PNG I/O, request checks, enabled shifts, focus crops and JSON
report writes. Every request completed in every trial:

| Trial | Legacy compare | Enhanced compare | Extra |
| --- | --- | --- | --- |
| 1 | 0.0471s | 0.9030s | 0.8560s |
| 2 | 0.0617s | 0.8958s | 0.8341s |
| 3 | 0.0632s | 0.8984s | 0.8352s |

The measured extra work is below 2s. To prevent pathological large/ambiguous
searches consuming unbounded time, request matching has a cooperative **1.2s
batch deadline**, and optional shifts a **0.5s batch deadline**. An unfinished
request (including hide) is unknown; unfinished shifts are absent. Checks occur
between bounded work chunks; this is not a hard real-time promise for arbitrary
CPU speed, filesystem latency or screenshots. Matching never guesses completion
on timeout. Bounds, pixels and scores determine completed verdicts.

## Mobile capture evidence

Unmodified detector selected
`C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe`, version
156.0.4314.58. Requested **390x844**; actual PNG **390x844** (DPR=1). The full
plugin baseline -> compare -> accept test also verifies those exact dimensions
and retains `viewport.preset="mobile"`.

Capture options were unchanged:
```text
--headless=new --disable-gpu --hide-scrollbars
--force-device-scale-factor=1 --force-prefers-reduced-motion
--run-all-compositor-stages-before-draw --virtual-time-budget=2000
--window-size=390,844 --user-data-dir=<temporary profile>
--screenshot=<temporary PNG> file://<move_104.html>
```
No mobile-width workaround, screenshot rescaling or browser flag change was
needed. Plugin calls check actual PNG dimensions; a mocked 500x844 result for
390x844 is rejected with the exact discrepancy and an actionable fix.

## Normal-shell Hermes validation

Ran from the actual checkout with normal Windows TEMP/TMP (not inside the repo),
the existing Hermes home and no install flags. No workaround or core changes.
`hermes plugins validate .` and `hermes plugins doctor --ci` both exit 0.
Exact successful output:

```text
✓ manifest — plugin.yaml parses
✓ manifest fields — name, version, description present
✓ requires_hermes — not declared
✓ config schema — not declared
✓ requires_env — all entries UPPER_SNAKE
✓ oauth — not declared
✓ loadable — entry: __init__.py
✓ python dependencies — 1 requirements from manifest
✓ capability probe — register() ran in isolation
✓ declared tools — matches registrations
✓ declared hooks — matches registrations
✓ declared middleware — matches registrations
✓ built-in tool collisions — no collisions
✓ security scan — safe
✓ no core override — no runtime rebinds of Hermes core
◆ Isolation — runs in the plugin host (plugins.isolation: host)

Validation passed.
Plugin Doctor: C:\Users\User\Documents\ChatGPT\Orphic SightDiff
  manifest: orphic-sightdiff 0.1.0 (standalone)
  OK: runtime discovery, manifest parsing, import, and registration passed
  registrations: 5 tool(s), 0 hook(s)
```

## Compatibility and deliberate limits

- No existing argument, field, status or tool removed. Plain standalone compare
  retains its original JSON field shape; enhancements are opt-in there. The
  Hermes adapter always supplies focus/shift enhancements. Original box/status
  rules and CLI 0/1/2/3 meanings remain unchanged.
- Tool JSON stays under 4000 bytes, including Unicode error messages. Budget
  degradation preserves every request id/status; the full report is untouched.
- Comments have no image region and therefore no request crops. Hide/revert's
  after crop falls back to from if no unique found rectangle exists. No pixels
  can be cropped for an area wholly outside a mismatched image; that side is null.
- Presets are returned only when explicitly supplied, preserving old exact
  viewport objects. Preset metadata is stored in both plugin state and engine
  metadata for the report reader. Accept preserves it.
- `plugin.yaml` dependency remains unchanged; requirements.txt now matches it.
- Cooperative deadlines and every successful-search score are local; no service,
  extra dependency, background worker, hook, new tool or HTML report was added.

## UNVERIFIED

- macOS/Linux execution and mobile capture in browsers other than the detected
  Windows Edge installation.
- Real symlink rejection on this Windows account (privilege unavailable);
  actual hard-link rejection and path checks are covered.
- The original one-box observation, because its actual HTML/images were absent.
- Real interactive Hermes conversation/agent code editing: runtime registration
  and handlers are verified, but the plugin was not installed/enabled in Hermes.
- A hard <2s guarantee on arbitrary machines/inputs; measured benchmark and
  conservative cooperative deadlines are recorded above.
