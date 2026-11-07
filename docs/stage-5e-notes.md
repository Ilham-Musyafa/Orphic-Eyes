# Stage 5e — Orphic Eyes, 2026-11-07

Branch stage-5e from stage-5d at abc6f75. The checkout folder was not renamed.
Counts are tests run, including two Windows symlink-privilege skips.

## Applied rename mapping

| Before | After |
| --- | --- |
| Orphic SightDiff / SightDiff (human text) | Orphic Eyes |
| orphic-sightdiff (plugin id, installed/catalog name, data directory) | orphic-eyes |
| sightdiff_baseline, sightdiff_compare, sightdiff_approve, sightdiff_accept, sightdiff_ignore | orphic_baseline, orphic_compare, orphic_approve, orphic_accept, orphic_ignore |
| sightdiff toolset, /sightdiff | orphic toolset, /orphic |
| sightdiff_tools.py | orphic_tools.py (git mv) |
| .sightdiff_, sightdiff_profile_, other temporary prefixes | .orphic_, orphic_profile_, orphic prefixes |
| sightdiff_out (reference script) | orphic_out |
| 0.2.0 | 0.3.0 |

README tagline: “See it. Point at it. Tell the agent.” Engine package and
`python -m engine.cli` remain unchanged. No separate catalog file exists here.
No data migration, root-directory rename, new UI, or default template.

## Rename checklist: before → final

Case-insensitive `git grep -i -c -e sightdiff -e 'sight diff'` counts matching
lines, not occurrences. Baseline: 103 lines, 118 occurrences, 20 files.
Each nonhistorical row below has zero final matching lines.

| File at baseline | Before lines | Final lines |
| --- | ---: | ---: |
| README.md | 12 | 0 |
| __init__.py | 3 | 0 |
| commands.py | 12 | 0 |
| docs/hermes-plugin-notes.md | 8 | 0 |
| docs/report-contract.md | 5 | 0 |
| docs/stage-5c-notes.md | 2 | 2 (unchanged) |
| docs/stage-5d-notes.md | 3 | 3 (unchanged) |
| engine/__init__.py | 1 | 0 |
| engine/capture.py | 1 | 0 |
| engine/store.py | 2 | 0 |
| plugin.yaml | 6 | 0 |
| reference_capture_test.py | 8 | 0 |
| sightdiff_tools.py → orphic_tools.py | 17 | 0 |
| tests/__init__.py | 1 | 0 |
| tests/benchmark_roundtrip.py | 1 | 0 |
| tests/fixtures/page_a.html | 1 | 0 |
| tests/fixtures/page_b.html | 1 | 0 |
| tests/test_plugin.py | 13 | 0 |
| tests/test_roundtrip.py | 5 | 0 |
| tests/test_stage5d.py | 1 | 0 |

Zero matches outside the three exempt notes. This record intentionally contains
old names as rename evidence and owner instructions; the other two are untouched.

## Step checkpoints

| Step | Commit | Changed files | Suite |
| --- | --- | --- | --- |
| 0 | cd3bd7b | Empty baseline record | 114, OK (2 skipped), 3.12 |
| 1 | cc6b8bb | module git mv; __init__.py; commands.py; three importing tests | 114, OK (2 skipped), 3.12 |
| 2 | 7fce487 | 17 source, fixture, manifest and documentation files | 114, OK (2 skipped), 3.12 |
| 3 | 275f61f | tests/test_stage5e.py | 116, OK (2 skipped), 3.12 |
| 4 | a1ca846 | engine/compare.py; engine/report_json.py; engine/store.py; tests/test_stage5e.py | 120, OK (2 skipped), 3.12 |
| 5 | 4a2255b | commands.py; orphic_tools.py; docs/hermes-plugin-notes.md; docs/report-contract.md; this record | 120, OK (2 skipped), 3.12 |
| 6 | Commit containing this record | tests/manual_stage5d.py → tests/manual_stage5e.py; this record | 120, OK (2 skipped), both runtimes |

Step 2 files: README.md, __init__.py, commands.py, docs/hermes-plugin-notes.md,
docs/report-contract.md, engine/__init__.py, engine/capture.py, engine/store.py,
orphic_tools.py, plugin.yaml, reference_capture_test.py, tests/__init__.py,
tests/benchmark_roundtrip.py, tests/fixtures/page_a.html,
tests/fixtures/page_b.html, tests/test_plugin.py, tests/test_roundtrip.py.

## Final verification

- Python 3.12.10 / Pillow 13.0.0: 120 tests, OK (2 skipped), 30.108s.
- Installed Hermes Python 3.14.9 / Pillow 13.0.0: 120 tests, OK (2 skipped), 31.134s.
- `hermes plugins validate .`: exit 0, all 15 checks green, security scan safe.
- `hermes plugins doctor --ci`: exit 0, orphic-eyes 0.3.0 standalone,
  runtime discovery/import/registration passed, 5 tools, 0 hooks.
- Both Hermes commands used normal-shell TEMP/TMP
  `C:/Users/User/AppData/Local/Temp`; no plugin install or enable was run.
- `python -B -m tests.manual_stage5e`: exit 0, real
  `C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe`;
  baseline pass, compare pass, one move request done, accept pass.
- Final tracked grep: 16 matching lines / 24 occurrences, only the three exempt
  notes. Excluding them: 0 lines / 0 occurrences (before: 98 / 113).
  Generated/ignored artifacts and .git are not source rename targets.
- Historical 5c/5d notes have no diff against stage-5d. `git diff --check` passed.

Final report.json printed by the real Edge script (temporary case removed):

```json
{
  "schema_version": 1,
  "name": "manual",
  "status": "pass",
  "summary": {"changed_px": 0, "changed_percent": 0.0, "box_count": 0, "unexpected_count": 0},
  "size": {"width": 1280, "height": 800},
  "images": {"before": "baseline.png", "after": "baseline.png", "diff": null},
  "boxes": [],
  "ignore_regions": [],
  "meta": {
    "browser": "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
    "os": "Windows",
    "viewport": {"width": 1280, "height": 800},
    "created_at": "2026-11-07T10:29:28.622879+07:00",
    "tolerance": 0
  },
  "note": "baseline_accepted"
}
```

All suites run sequentially. The first Step 1 attempt ran before a sandbox-blocked
git mv completed and had three import errors; the completed rename rerun passed.
No timing test or deadline was changed.

## Correctness and assumptions

Report writes found by source search: compare and approve call `write_report`;
accept uses `_atomic_json`. The shared report writer now refreshes optional HTML;
accept refreshes immediately after its atomic write. Baseline/report deletion
removes HTML in both engine and adapter paths. No report schema, statuses, CLI
exit codes, persisted field names or Pillow-only dependency changes.

ASSUMPTIONS: contrary to the review premise, ignore add/remove write config.json,
not report.json. Preserve their existing compare-again semantics and refresh HTML
from the current report when one exists. Missing template remains a no-op, with
no paths.html result. The requested normal-shell validator/doctor are the explicit
exception to repo-only artifacts: doctor creates its own disposable staging
directory under normal TEMP/TMP outside this checkout. No manual writes outside
the repo are performed.

UNVERIFIED: real symlink creation on this Windows account (2 privilege skips),
other operating systems, and actual installed-plugin/gateway refresh.

## Owner steps in Hermes

A running gateway keeps old tool schemas until it is stopped. Replace
`<repo path>` with this checkout's actual path; its root folder is unchanged.

1) `hermes plugins disable orphic-sightdiff`
2) `hermes gateway stop`
3) `Remove-Item -Recurse -Force "$env:LOCALAPPDATA\hermes\plugins\orphic-sightdiff"`
4) `robocopy "<repo path>" "$env:LOCALAPPDATA\hermes\plugins\orphic-eyes" /MIR /XD .git __pycache__ .stage5 tests docs /XF *.pyc *.log /NFL /NDL`
5) `hermes plugins enable orphic-eyes`
6) start a NEW Hermes session

These are owner instructions only; installation, enable/disable, deletion and
gateway restart are deliberately not executed in this task.
