# Orphic SightDiff engine

Python 3.12 or later, with Pillow as the only dependency. No Hermes integration.
Use an installed Edge or Chrome; automatic detection prefers Edge in the same
order as `reference_capture_test.py`.

```powershell
python -m engine.cli baseline demo file:///C:/path/to/page.html --store ./store
python -m engine.cli compare demo http://localhost:8000/ --store ./store --tolerance 0
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
