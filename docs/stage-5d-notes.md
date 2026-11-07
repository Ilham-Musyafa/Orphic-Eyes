# Stage 5d verification — 2026-11-07

Branch: stage-5d, created from stage-5c at e1d5ef7. Counts below are tests run,
including two Windows symlink-privilege skips (not additional passing tests).

| Step | Commit | Changed files | Green checkpoint |
| --- | --- | --- | --- |
| 0 | f24c1dd | Empty baseline record | 106, 2 skipped; Hermes 3.14 |
| 1 | 7d0a909 | sightdiff_tools.py; tests/test_plugin.py | 106, 2 skipped; Hermes 3.14 |
| 2 | ba0a33d | engine/report_json.py; sightdiff_tools.py; tests/test_stage5d.py; docs/report-contract.md | 108, 2 skipped; 3.12 |
| 3 | b44fcaf | engine/store.py; tests/test_stage5d.py; docs/report-contract.md | 109, 2 skipped; 3.12 |
| 4 | 3ac69f3 | engine/report_html.py; engine/compare.py; engine/store.py; sightdiff_tools.py; tests/test_stage5d.py; tests/fixtures/report_embed.html | 114, 2 skipped; 3.12 |
| 5 | fc3990e | plugin.yaml; README.md; docs/report-contract.md; docs/hermes-plugin-notes.md | 114, 2 skipped; 3.12 |
| 6 | Commit containing this record | tests/manual_stage5d.py; docs/stage-5d-notes.md | 114, 2 skipped; both runtimes |

Message formats (omit every zero count):
- Requests complete: `<visual text> | Requests: N done, N not_done, N unknown, N skipped`.
- Incomplete: `Requests incomplete (N not_done, N unknown) | <visual text>`.
- Actual examples: `No unexpected changes | Requests: 1 done`;
  `Requests incomplete (1 not_done) | No unexpected changes`;
  `Requests incomplete (1 unknown) | No unexpected changes`;
  `No unexpected changes | Requests: 1 skipped`.
- No requests/empty list: original visual text unchanged. success means execution
  without error, independent of requests_ok and visual severity. Hints preserved.

Final sequential `-m unittest` runs, Pillow 13.0.0 on both:
- Python 3.12.14: 114 tests, OK (2 skipped), 30.694s.
- Hermes Python 3.14.9: 114 tests, OK (2 skipped), 34.302s.
- Earlier concurrent runs each failed the existing eight-request assertion under
  CPU contention and request deadlines; no deadline or assertion was changed.
  An earlier sandboxed 3.12 run could not capture browsers; normal-shell reruns passed.
- `hermes plugins validate .`: exit 0; all checks green, security scan safe.
- `hermes plugins doctor --ci`: exit 0; 0.2.0 standalone, 5 tools, 0 hooks.
  Both used normal TEMP/TMP C:/Users/User/AppData/Local/Temp. An earlier doctor
  overlapped tests and failed copying transient profiles; rerun after tests passed.
- `python -m tests.manual_stage5d`: real Edge baseline -> compare (1 request done)
  -> accept passed and printed the final report: schema_version 1, pass, zero
  summary, boxes [], no requests, baseline/baseline images, diff null,
  note baseline_accepted. Old diff/crops removed. No Hermes installation.

ASSUMPTIONS: `<\!--` contains invalid JSON escape `\!`; embedding instead uses
`\u003c!--`, which blocks HTML comments and round-trips identical strings.
Existing report messages are updated when present; no message field is required.
UNVERIFIED: real symlink rejection on this Windows account (2 privilege skips),
other operating systems, and running gateway refresh after an actual plugin copy.
Deliberately omitted: UI/default template, plugin install/enable, gateway restart,
tool-description change. Update the compare description's "no HTML yet" once a
real template exists. CLI exit codes and schema version remain unchanged.
