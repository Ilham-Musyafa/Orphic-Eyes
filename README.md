# Orphic SightDiff engine

Python 3.12 or later, with Pillow as the only dependency. No Hermes integration.
Use an installed Edge or Chrome; automatic detection prefers Edge in the same
order as `reference_capture_test.py`.

```powershell
python -m engine.cli baseline demo file:///C:/path/to/page.html --store ./store
python -m engine.cli compare demo http://localhost:8000/ --store ./store --tolerance 0
python -m engine.cli ignore add demo --store ./store --region 30,150,330,190 --label button
python -m engine.cli ignore list demo --store ./store
python -m engine.cli ignore remove demo --store ./store --label button
python -m engine.cli compare demo http://localhost:8000/ --store ./store --expect 30,150,330,190 --expect 900,0,100,100
python -m engine.cli approve demo --store ./store --box 1 --box 2
python -m engine.cli approve demo --store ./store --all
python -m engine.cli accept demo --store ./store
python -m unittest -v
```

CLI exit codes are 0 (pass), 1 (check), 2 (fail), and 3 (error). Successful
commands print JSON; errors print one line on stderr. Baseline creation returns
pass. Reports always follow schema version 1 in `engine/report_json.py`.

The package exports `capture`, `baseline`, and `compare`. Capture returns a bool;
baseline and compare return dictionaries, with `{"status": "error", "error":
"reason"}` on failure. Pixel comparison is also available as
`engine.compare.compare_images(before_png, after_png, diff_png, tolerance=0)`.

Each case is stored in `<store>/<name>/`. Names contain ASCII letters, digits,
underscores, and hyphens, start with a letter or digit, and cannot be Windows
device names. Store outputs cannot be symbolic links, external junction targets,
or hard links. The store root is resolved before checking case paths. Callers
must not concurrently modify or replace store paths during an operation.

Implementation choices where the brief left details open:

- `viewport` is `{"width": 1280, "height": 800}`; `browser` is the executable
  path and `os` is `platform.system()`. Baselines use tolerance 0. Comparisons
  reuse the recorded browser and viewport and record their own time/tolerance.
- Tolerance is an integer from 0 to 255. PNG inputs are converted to RGB, as in
  the reference. Status uses the unrounded pixel percentage; reported page and
  box percentages are rounded to three decimals.
- The unchanged background of a diff is the after image at 35 percent brightness.
  Changed pixels are solid red.
- A size mismatch reports the after-image size, zero counted pixels, zero percent,
  no boxes, and `note: "size_mismatch"`. Its diff is the dimmed after image.
- For low-level output APIs, the supplied output parent is the caller-designated
  store location. Capture creates its isolated profile there and gives the browser
  that same directory for TEMP/TMP/TMPDIR. It removes stale screenshots before
  launching and verifies a resulting PNG before returning true. Browser command
  flags and timeout/kill behavior are unchanged from the reference.

The three HTML fixtures are copied from the reference constants, with shifts of
0 and 8 pixels for page_a/page_b. Tests require an installed browser and fail
explicitly if capture is unavailable; they do not silently skip integration tests.
Test outputs and profiles are temporary directories under this project and are
removed after testing. On execution environments that restrict browser child
processes, run tests with permission to launch the installed browser normally.

Stage 3 adds `ignore_add(name, store_dir, region, label=None)`, `ignore_list`,
`ignore_remove(name, store_dir, label)`, `approve(name, store_dir, boxes=None,
all_boxes=False)`, and `accept(name, store_dir)` to the public package. Like the
existing APIs, these return dictionaries and never raise on bad input.
`compare(..., expected_regions=[(x, y, w, h), ...])` accepts per-run expected
regions; rectangle dictionaries are also accepted. Low-level `compare_images`
also accepts `ignore_regions`, `expected_regions`, and `approvals` keyword lists.

Ignore configuration is a JSON list of `{name, x, y, w, h}` in `config.json`.
Coordinates must be nonnegative integers and sizes positive integers. Ignore
regions are clipped to the baseline when added; a wholly outside region is an
error. Omitted labels use the first available `region-N`; labels are unique and
case-sensitive. Missing labels on removal are errors. At most 50 ignores are
allowed. Comparisons clip all regions to the after image and omit regions with
no intersection. Expected regions have no persistence or count limit.

Approvals are a JSON list of `{x, y, w, h, sha256}` in `approvals.json`; hashes
are lowercase hexadecimal SHA-256 of the entire RGB crop, including unchanged
pixels inside its bounds. Repeating an identical approval does not duplicate it;
different crop hashes at the same coordinates can coexist. Both JSON files use
a same-directory temporary file and atomic replacement. Commands require an
existing case. Invalid inputs are rejected before any output is changed.

Approval uses the last report's tolerance and retains expected labels for boxes
with matching geometry during that report regeneration. If the box layout has
changed, run compare again before approving IDs. Subsequent compare calls need
their own expected regions. Accept preserves ignore configuration, copies the
current PNG exactly, clears approvals, and updates baseline time and viewport to
the accepted image. It leaves report/diff regeneration to the next compare.
Individual file replacements are atomic; a command updating several files is
not a multi-file transaction.

Only unexpected, unapproved tile-cluster pixels contribute to the 5 percent fail
threshold; this avoids counting pixels twice when box bounds overlap. Any
remaining unexpected, unapproved box gives check. Otherwise status is pass,
with `only_expected_changes` when boxes remain (including approved boxes).
Changed-pixel summaries still include expected and approved changes. Report
keys and schema version are unchanged. Approval CLI exit codes reflect the
regenerated report status; ignore and accept commands return 0 on success.
