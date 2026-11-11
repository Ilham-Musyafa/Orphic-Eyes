# HANDOFF

## Current task: Local report server and Hermes-driven auto loop

Branch: `feat/auto-loop`, from pushed `feat/url-capture` at `d92bbaa83782cbbc8300ee54bde7dbe427c38e93`.

### Plan
1. Push only feat/url-capture and confirm with ls-remote. Done: `d92bbaa83782cbbc8300ee54bde7dbe427c38e93 refs/heads/feat/url-capture`.
2. Implement a loopback-only, read-only report server with random default port, confined file access, clean shutdown/timeout, CLI latest/named selection, and cross-process server discovery. Return report_url (or startup instructions) from captures/compares without changing report schema/templates.
3. Implement immutable loop session anchors and per-round captures/reports. Compare each new image with the prior round, while checking fixed goals: existing Point & Tell requests anchored to the original baseline, or exact restoration of initial changed areas to the original baseline when requests are absent. Recompute persistent unexpected zones against that fixed anchor. Do not confuse no new changes with goal completion. Return continue/done/max_rounds/needs_human and a neutral, pixel-only follow-up prompt. Reuse existing diff/matching thresholds and limits.
4. Register orphic_loop_step using the existing Hermes adapter pattern (requires the minimal plugin.yaml tool declaration as well as Python registration). Test serving confinement and actual HTTP image access, two-round correction, unchanged failure, unexpected changes, max-round and unclear paths, missing-browser skips, and full regression suite. Document examples/limits in docs/AUTO-LOOP.md and update this handoff after every step.
5. Commit in small steps, push only feat/auto-loop, confirm both feature refs with ls-remote. No PRs, merges or deployments.

### Progress
- Report-serving core implemented in engine/serve.py: loopback/random port, read-only artifact allowlist, no directory listings, traversal/symlink/hard-link refusal, Host/Origin defenses, private registry discovery and bounded shutdown. Nine server tests passed, including cross-process discovery, timeout cleanup and capture-pair report_url behavior. Output metadata stays outside persisted report.json.
- Eleven loop unit tests passed: unchanged-but-wrong stays unresolved, round 2 can finish, immutable anchors survive original target changes, persistent unexpected zones remain visible, explicit move requests reuse existing matching, max_rounds/needs_human stop paths, link/lock protection and failed-round cleanup. Integration and final regression verification are ongoing.

- Engine loop implemented in engine/loop.py with fixed baseline/initial snapshots, immutable session goals, consecutive per-round folders, an exclusive session lock, transactional round publication and persisted stop results. The session never saves after_url or executes/sends prompt text. Existing compare_images, 32px clustering, 3x3 zone names, 5% threshold and bounded request matcher are reused unchanged.
- Eleven loop unit tests pass after reducing one explicit-move test fixture's dimensions to fit comfortably within the existing matcher budget on shared CI. The combined browser integration run passed HTTP same-origin canvas access and the real two-round Hermes path; final suite verification remains pending.
- Added a bounded browser-startup readiness fix after an intermittent capture error: DevToolsActivePort can be partial and /json/list can initially contain no page. Discovery now waits under the existing timeout rather than raising from incomplete state; a regression test covers both conditions. No timeout/matching budgets or screenshot thresholds changed.
- CLI integration implemented: `serve --store/--name/--port/--timeout` and `loop-step NAME AFTER_URL --store/--requests/--max-rounds/--allow-local`. Server URLs point to the latest/named report. Ctrl+C and timeout paths close the server and remove its discovery registry.
- Hermes integration implemented: orphic_loop_step is registered in Python and declared in plugin.yaml (the minimal manifest change required for the requested new tool). orphic_compare returns report_url/serve_hint. Loop responses preserve full counts and explicitly flag omitted entries/truncated prompts under the existing 4KB response budget; full results/prompt remain in round.json/prompt.txt.
- docs/AUTO-LOOP.md now describes choosing goals, initialization, serving, schemas, tool/CLI examples, stop semantics, evidence, URL restrictions and pixel-only/Windows limits. Targeted startup/adapter/CLI unit checks passed; final full-suite and recorded example runs follow.
- Shared-runner regression checks exposed pre-existing timing sensitivity in crop matching. Kept every matcher threshold, search limit and deadline unchanged; optimized the identical grayscale MAE/block-bound arithmetic and reused completed identical region searches only within one verify_requests call. Reference-statistics and cache-isolation tests were added. All 29 locate/request checks now pass with the original assertions, including all-eight-intent output and shift hints.
### Constraints and starting state
- Never edit/stage engine/templates/report.html, README.md or any UI file; Claude owns report.html on release/hackathon.
- Source template starting SHA-256: e3b41a17a0dbb5b15fa30e1675e8f8afa2a32cf216be6e07b8278b71480b41e2. README starting SHA-256: c1cb30ccf91990d01faea7ac4ed989d2154150ef3f4a809329ee04036d9ae0ae.
- Keep diff thresholds, matching budgets/limits and report schema unchanged. No new dependency planned. Never read .env or log source URL values.
- Repository was clean at the start. No pushes to main/stage-5e/release branches.
- Current runtime: Python `/workspace/.venvs/orphic-eyes/bin/python`, browser-enabled command prefix `/workspace/.orphic-eyes/run`. Normal browser-launch permissions are required; keep browser sandbox and TLS validation enabled.

## Previous task: URL capture engine

Branch: `feat/url-capture`, from `origin/stage-5e` at `6bde560c28f05d7d50d66e69fb1a47849be4612a`.

### Plan
1. Add a strict HTTP/HTTPS capture API in `engine/url_capture.py`, retaining the existing local-file capture API for compatibility. Use installed Edge/Chrome/Chromium via DevTools with the Python standard library: no new dependency. Fix viewport/DPR, disable motion, wait for network idle with bounded timeouts, and support full-page PNGs. Guard all outbound requests against private destinations unless explicitly allowed; never include source URLs in errors/logs.
2. Add `capture_pair` using the existing pixel diff and JSON/HTML report builders without threshold, schema, or template changes. Extend the existing `orphic_compare` schema/adapter for before_url/after_url, preserving the five registered tools and the manifest. This requires the existing Python Hermes adapter `orphic_tools.py`; no UI or manifest edits.
3. Add unit/security tests and local HTTP browser integration tests; skip when no browser exists. Update the old browser class to skip on absence. Run the complete suite, plugin contract validation, and a real paired-URL example. Record evidence and limitations here.

### Status
- Inspected capture, baseline store, compare_images, build_report/write_report, Hermes handlers/schema/registration, and existing browser tests.
- Existing browser launcher: `/workspace/.orphic-eyes/run`; Python: `/workspace/.venvs/orphic-eyes/bin/python`. It maps a working official Chrome build without changing repository files and keeps temporary socket paths short. Browser sandbox remains enabled.
- `engine/templates/report.html` is owned by another agent: do not edit or stage it. Initial SHA-256: e3b41a17a0dbb5b15fa30e1675e8f8afa2a32cf216be6e07b8278b71480b41e2.
- Step 1 complete: bounded standard-library DevTools WebSocket transport plus an HTTP CONNECT guard. Every browser destination is resolved and checked; direct and upstream public connections pin a validated numeric address to prevent DNS rebinding. Inherited proxies and TLS validation remain enabled. Policy failures/errors omit URLs and browser logs.
- Final full suite: 153 passed, 0 skipped, 0 failures/errors (44.609s). Browserless simulation: unittest ran 137 test methods and reported 7 skips (four class-setup skips and three test-method skips), zero failures/errors. Both new and existing browser paths skip on absence.
- Step 2 complete: `engine.url_capture.capture(url, out_path, width=1440, height=900, full_page=False, wait_ms=250, *, timeout_ms=30000, allow_local=False, browser=None)` raises safe `CaptureError`/`CaptureTimeout`/`BrowserNotFound` errors and atomically publishes a verified PNG. `engine.capture_url` exports this API; legacy `engine.capture` stays unchanged for local-file callers.
- `engine.capture_pair(before_url, after_url, store_dir, *, name="urls", width=1440, height=900, wait_ms=250, timeout_ms=30000, allow_local=False, browser=None)` captures identical viewports, calls unchanged `compare_images`, `build_report`, `write_report`, and returns the existing schema plus output paths. Each capture has its own deadline (pair preflight DNS is also bounded). URLs/queries are never saved. A nonempty target is rejected; use a fresh name. Staging prevents partial pairs on capture failure.
- CLI: `python -B -m engine.cli capture-pair BEFORE_URL AFTER_URL --store STORE --name FRESH_NAME [--width 1440 --height 900 --wait-ms 250 --timeout-ms 30000 --allow-local]`. Exit codes retain pass=0/check=1/fail=2/error=3.
- Rendering is DPR 1, fixed light/reduced-motion media, disabled animations/transitions/carets and hidden scrollbars, fresh profiles/cache and network-idle plus wait_ms. Only browser layout metrics are used for full-page dimensions; page source, DOM contents and computed styles are never read. Full-page capture is available on the single-capture API; pairs use equal viewport-only images.
- Engine validation: 24 URL engine tests passed, including repeated identical 1440x900 PNGs, full-page capture, a real paired-URL report and CLI exit/path checks, timeout cleanup, private redirect/subresource denial, upstream numeric pinning, and output-link protection.
- Step 3 complete: extended the existing registered `orphic_compare` tool (manifest/tool count unchanged) with before_url/after_url, width/height, wait_ms/timeout_ms and allow_local. Pair mode needs both URLs and a fresh name, rejects mixing with legacy url/expect/requests, returns paths.report, optional paths.html and summary.box_count with a short changed-zone message. Source URLs are not saved to plugin state; rerun with an explicit pair/new name. Legacy baseline/compare behavior remains available.
- Updated the old `tests/test_browser.py` class to raise SkipTest when no browser is installed. Added Hermes schema/error/real-HTTP round-trip coverage and an explicit missing-browser skip regression test.
- Plugin validation available here: no `hermes` executable is installed, so `hermes plugins validate` is unavailable. The repository's manifest/registration, isolated package import, schema/adapter, local browser workflows and report freshness suites ran: 31 tests passed, zero skips/failures.
- Scope remains Python engine, minimal existing Python Hermes adapter, tests and this handoff. No UI, dependency manifest, thresholds or report schema changes. No push, merge or deployment.

### Verification and continuation

No new Python dependency: the implementation uses Python's standard library and the existing Pillow dependency. Verified here with Python 3.12.14, Pillow 13.0.0 and official Google Chrome 157.0.8103.50 on Linux. Installed Edge/Chrome/Chromium are discovered using the existing paths; the new API also accepts `browser=` or `ORPHIC_BROWSER`. Windows/Edge launch compatibility follows the existing executable discovery and standard socket/subprocess APIs but has not been run on Windows in this session.

Run the full suite from `/workspace/Orphic-Eyes`:

```sh
/workspace/.orphic-eyes/run /workspace/.venvs/orphic-eyes/bin/python -B -m unittest discover -v
```

The runtime's nested command sandbox prevents browser sandbox startup. Use approved normal launch permissions (`require_escalated`) for the launcher; browser sandboxing and TLS verification remain enabled. The retained test logs are `/workspace/.orphic-eyes/url-example/full-tests.log` and `browserless-tests.log`. Browserless simulation patched browser discovery to return None in engine.capture, engine.url_capture and engine.store before test discovery; this did not disable assertions or alter production code.

Exact registered schema can be printed from the repository:

```sh
python -B -c 'import json, orphic_tools; print(json.dumps(next(schema for name, schema, handler in orphic_tools.TOOL_DEFINITIONS if name == "orphic_compare"), indent=2))'
```

New `orphic_compare` pair-mode schema fields (the existing `name`, `url`, `requests` and `expect` fields remain):

| Field | Type | Default / requirement |
| --- | --- | --- |
| before_url | string | Required together with after_url in pair mode; public http/https |
| after_url | string | Required together with before_url in pair mode; public http/https |
| width | integer >= 1 | 1440 |
| height | integer >= 1 | 900 |
| wait_ms | integer >= 0 | 250, after network idle |
| timeout_ms | integer >= 1 | 30000 per capture; greater than wait_ms |
| allow_local | boolean | false; explicit opt-in for trusted private HTTP(S) pages/resources/redirects |

The schema retains optional legacy mode; the handler enforces the pair-field requirements and rejects mixing modes. Pair mode needs a fresh, empty target name. It never saves the source URL or implicit recapture state. To capture again, supply another pair with a fresh name. Approve/accept can still review the generated files through their existing pipeline; implicit legacy recapture needs a legacy baseline.

Example Hermes adapter call (verified against a temporary local HTTP server):

```json
{"name":"orphic_compare","arguments":{"name":"hermes-url-example","before_url":"http://127.0.0.1:8765/page_a.html","after_url":"http://127.0.0.1:8765/page_b.html","width":1440,"height":900,"allow_local":true}}
```

Response excerpt:

```json
{"success":true,"status":"check","message":"1 changed zone | Check these changes","summary":{"changed_px":2041,"changed_percent":0.157,"box_count":1,"unexpected_count":1},"paths":{"report":"/workspace/.orphic-eyes/url-example/hermes/orphic-eyes/hermes-url-example/report.json","html":"/workspace/.orphic-eyes/url-example/hermes/orphic-eyes/hermes-url-example/report.html"}}
```

Exact schema/call/response are retained outside the checkout as `tool-schema.json`, `example-call.json`, and `example-response.json` in `/workspace/.orphic-eyes/url-example/`.

Reproduce the CLI example in two terminals (choose a fresh target name if rerunning). The temporary server used for verification was stopped afterward:

```sh
# Terminal 1, from the repository root:
python -B -m http.server 8765 --bind 127.0.0.1 --directory tests/fixtures

# Terminal 2, from the repository root:
/workspace/.orphic-eyes/run /workspace/.venvs/orphic-eyes/bin/python -B -m engine.cli capture-pair http://127.0.0.1:8765/page_a.html http://127.0.0.1:8765/page_b.html --allow-local --store /workspace/.orphic-eyes/url-example --name comparison
```

Verified CLI result: exit 1 (`check`, a successful comparison requiring review), 1440x900, one changed zone, 2,041 changed pixels (0.157%). Changed box: x=48, y=232, w=186, h=49. Outputs under `/workspace/.orphic-eyes/url-example/comparison/`: `baseline.png`, `current.png`, `diff.png`, `metadata.json`, `report.json`, `report.html`. Repeated-capture tests separately verified identical pixels, disabled CSS motion, and full-page dimensions. Report HTML embeds exactly the same JSON as report.json.

### Limits and safety notes

- Strict URL capture is `engine.url_capture.capture` / `engine.capture_url`; the existing `engine.capture` remains a local-file compatibility API. The new API always rejects file/javascript/data input URLs, including with allow_local enabled. Invalid URL, blocked private destination, unavailable browser, navigation/HTTP error and timeout errors are clear and omit the source URL. No .env files are read or printed.
- Public DNS must resolve to exclusively public addresses. DNS failure is fail-closed. Public-site capture was not verified in this Cloud instance because public DNS was unavailable/restricted; the real integration tests and example use local HTTP with explicit allow_local. Required preview/live domains and their resources must also be permitted by the environment's outbound policy.
- The inherited proxy is honored. In public-only mode its CONNECT destination is a validated numeric IP to prevent DNS rebinding at the proxy; hostname-only proxy allowlists or credential routes may reject this. The proxy must support HTTP CONNECT for HTTP and HTTPS, and browser/system CA trust must be configured. No TLS/checksum verification or browser sandbox was disabled. This policy is intentionally not bypassed.
- Fresh browser profiles have no saved login/cookies. Login walls, cookie banners, sites that block headless browsers, CSP that prevents a rendering override, or dynamic video/canvas/timers can affect screenshots. Cross-browser/OS/font rendering can differ. Full-page capture is only on the single-capture API; pair reports deliberately use equal viewports.
- The capture timeout covers DNS/startup/navigation/network-idle/wait/screenshot, with bounded process cleanup. Pair preflight and each of its two captures are bounded separately. Avoid concurrent writes to the same target. Successful capture/report files stay local; the guard/profiles/browser processes are temporary and cleaned up.
- `hermes plugins validate` was unavailable (Hermes CLI not installed). Existing repository manifest/registration/schema/isolated-import and real adapter tests passed. No live Hermes host or Windows run is claimed.
- `engine/templates/report.html` and every other UI file are unchanged; template SHA-256 remains `e3b41a17a0dbb5b15fa30e1675e8f8afa2a32cf216be6e07b8278b71480b41e2`. Diff thresholds, limits, report schema and dependency manifests are unchanged. Commits are local on `feat/url-capture`; nothing was pushed, merged or deployed.

## Previous task: Settings redesign + Shortcuts (replaces Settings steps 3–4)

Branch: `feat/settings-redesign` (from `feat/mobile-fixes` at 0fbfaec). One commit per step. Only Settings changed; prefs stay in `orphic-eyes.prefs.v1` with the same keys.

### Done
1. 5fec24d Shell: 760×560 card (max 92vw/86vh, radius 12, rgba(0,0,0,.4) backdrop), 200px side list (title, tabs, "Version dev": no version constant exists), vertical tablist (Up/Down/Home/End, roving focus) + tabpanel, sticky title/subtitle, own scroll, "Changes save automatically" footer, 32px close. Re-render after a change keeps scroll + focused control.
2. 808db7c Rows/controls: group cards with optional uppercase titles; 56px rows (label 13/500, description 12 muted, 2 lines, 420px); switch 32×18 (role=switch), 28px segmented radiogroup (arrow keys), 28px select for Default view (4 options), 28px secondary buttons; red Danger zone for Reset preferences; 8 requests / 240 characters and the privacy note are blue ⓘ callouts. Descriptions via aria-describedby.
3. 2256df7 Shortcuts: one `SHORTCUTS` list ({group, action, keys, when}); groups General, Navigation, Canvas, Modes, Requests; 44px rows, mono keycaps (no "+"), ⌘ ⌥ ⇧ on Mac; search (action, group, key names; "ctrl k" → Ctrl K), marked matches, empty groups hidden, 'No shortcuts match "{q}".' + Clear search, aria-live count, Esc clears then closes; autofocus on desktop only; touch note; Ctrl K tip (palette exists). Row labels like "Open settings, Control plus comma".
4. 9a6e061 Phone (<640): full screen, level 1 = 52px section rows + close, level 2 = "‹ Settings" back + content; switches right, segments/select full width, 44px targets, keycaps 10px, safe-area padding. Dark: #1C1C1F content, #161618 side list, #ffffff14 borders, #ECECEC text, #A0A0A0 descriptions, active #2F80FF on 16% blue, danger #FF6B6B.
5. c450dcd Optional: 2px active bar, 4px backdrop blur, 1.2s "Saved" flash (role=status), matched text marked, last tab remembered for the session, 120ms control transitions (off with Reduce motion). 695b435 keeps the old panel-up open animation.
- Tabs and where settings went: General = Quick tour · Appearance = Theme, Text size · Canvas = Default view, Show grid, Grid size, Snap to grid, Rulers, Default precision · Copy prompt = 4 switches + 8/240 callout + Preview prompt · Data & privacy = privacy note + Reset preferences (moved from General) · Shortcuts · About = existing text. No tab omitted; no settings added.
- Shortcut audit: all 18 listed shortcuts have handlers (Ctrl K, Ctrl ,, ?, Ctrl Z, Ctrl Shift Z, Esc, Ctrl B, Ctrl I, 0, V, M, P, Space, Shift, 1, 2, 3, Ctrl Enter); kept, none removed, none added. Working but not listed (left as they were): Ctrl Y (redo), slider handle arrows/Home/End, sheet handle and sidebar tab arrows.
- Deviations: active tab label uses #1D63D3 (light) / #5C9BFF (dark) for 4.5:1; icon and bar stay #2F80FF. Light segmented background #F4F4F2 so unselected labels pass 4.5:1.
- Checked in Chrome at 1440 and 390/360 (touch), light/dark: acceptance 168/168, shortcuts 35/35, every listed key really works, settings persist after reload, focus returns to gear / ⋯. Main app pixel-identical to `feat/mobile-fixes` (desktop 18/18; phone 14/14 apart from a 2px focus flicker on ⋯ that also shows base-vs-base). Copy prompt text identical; mobile, load, reference, flow and motion checks unchanged.
- report.html: 441,018 → 465,787 bytes. Diff: no URLs/fetch/XHR/eval, no new storage keys. Tests unchanged: 113 passed, same 5 Edge-capture failures; `tests/test_browser.py` 7 errors (no Edge).
- Screenshots: `docs/screenshots/settings-redesign/`.

### Not done
- Optional group filter chips in Shortcuts (search already filters by group name).
- Not tested in Edge or on a real Mac (⌘ keycaps checked by code only).

### Next
- UI polish (Prompt B)

## Previous task: Mobile fixes (<640px / touch)

Branch: `feat/mobile-fixes` (from `feat/visual-fixes` at 38b9b97). One commit per step. Phone rules live in `@media (max-width:639px)` blocks; touch wording uses `matchMedia('(hover: none)')` (`body.touch`). 640–767 px keeps the old bottom sheet.

### Done
1. 584071c (+ c7a45f4 focus fix) Two-row phone header: row 1 (52 px) logo, page name with ellipsis (tap opens Pages at Half; no ▾ with one page), 44×44 Copy prompt icon (disabled reason as a toast on press), "⋯" (aria-label "More options", aria-expanded). Row 2 (40 px) Review|Move|Add (44 px tap area) + "Step n of 4". ⋯ menu: status line ("3 changes · 0 approved", + requests), Preview prompt, Undo/Redo, Theme Light/Dark/System inline, Settings, Help & shortcuts, Start tour. Esc or a tap outside closes it; focus returns to ⋯.
2. 649b893 Bottom sheet: Peek 120 px (default), Half 50vh (tab tap), Full 88vh. Handle 36×4 is a button with a 44 px hit area: tap toggles Peek/Half, drag snaps to the three positions, arrow keys step; label "Expand panel" / "Collapse panel". Sticky sheet headers, lists scroll inside (`overscroll-behavior: contain`), 24 px fade at Half that goes at the end of the list, list padding = footer + safe area + 16 px, canvas padding = current sheet height. A tap on the picture returns to Peek. Area map hidden under 640 px; each change row already names its area. The picture is fitted to the Peek layout so it does not jump when the sheet moves.
3. 6fb40e0 Requests sheet: sticky footer "{n} of 8 requests" + 44 px "Preview prompt" (hidden at Peek, where the header shows the count). Preview on phones is full screen: text "Close" top left, full-width "Copy prompt" at the bottom.
4. 3888376 Canvas: picture top-aligned, 8 px below the floating view/option bar (empty state starts at the top). All controls ≥44 px (floating bars, dock tools, slider handle; small change boxes get an invisible 44 px tap area). Touch wording: "Tap Load images, or try the sample." (+ "They stay in this tab and are never uploaded."), "Tap to add an image or GIF", "No requests yet. Mark an area and tap Add.", keyboard hints hidden from tooltips/menus, shortcuts list notes "Keyboard shortcuts work with a physical keyboard."
- Checked in Chrome device emulation (touch on) at 390×844 and 360×780, light and dark: header/menu 64/64, sheet 92/92, requests/preview 68/68, canvas + touch + 44 px audit 84/84; no console errors, no horizontal overflow.
- Desktop unchanged: pixel-identical screenshots against `feat/visual-fixes` at 1440, 1024 and 700 px, light and dark, empty + report + Move (18/18). Copy prompt text byte-identical; Load images, Add reference, Flow clarity and motion checks unchanged.
- report.html: 421,888 → 441,018 bytes. Diff: no URLs/fetch/XHR/eval/localStorage. Tests unchanged: 113 passed, same 5 Edge-capture failures; `tests/test_browser.py` 7 errors (no Edge).
- Screenshots: `docs/screenshots/mobile-fixes/` (390 px, light + dark, per step).

### Not done
- Optional: area map full-size overlay (the map is hidden on phones instead of shown as a thumbnail); "Fit width"/"Fit screen" in the zoom pill (no room at 360–390 px without dropping a zoom step). Stack view: Side by side already stacks Before over After on portrait, so nothing was added.
- Not tested on a real phone or iOS Safari (Chrome emulation only); Edge not available in the cloud runner.

### Next
- Settings step 3: tab restructure

## Previous task: Visual fixes (desktop)

Branch: `feat/visual-fixes` (from `feat/flow-clarity` at 3b4b36e). One commit per item.

### Done
1. 80d5080 Status bar file name: `afterFileName()` uses `after_name`, else a real path's base name, else `current.png`; data:/blob: contents are never printed.
2. ac79081 Header chip follows the review state: "Ready" (pass), "Check changes" (check), "Big change" (fail); same colors; tooltip has the inspector wording + changed areas (+ pending requests). Hidden when nothing is loaded.
3. 48a5904 Empty state: only the canvas 3-step card onboards; sidebar lists, Pages and inspector say "Load images to start"; capture chip and the "only sees pixels" footer are hidden until something is loaded.
4. dd196b9 Disabled Copy prompt: muted surface background, faint text, no hover change (aria-disabled + tooltip kept).
5. ec4cedc Area map: solid 3×3 lines (light and dark variants), map slightly wider, thumbnail on its own layer with a little more contrast; dark theme dims it to ~60% brightness with a dark frame.
6. 91c98e6 Inspector titles "Add request · ADD-1", "Move request · PT-4", "{Type} request · PT-1"; row labels, sub-lines and page names carry their full text as a tooltip (tooltips now wrap).
7. 43f4d62 US spelling: helper chips "Color / wrong color / match the Before color", "colored box"; no "colour" left in the file.
8. 0e9199b Tour step 3 points at the floating view bar, so the card sits below it instead of covering "Side by side".
- 849160f (found while checking 2): the longer chip pushed Copy prompt past the edge at 1440 px and the header already overflowed below 1280 px. Stepper labels from 1600 px, capture chip + brand name hidden below 1280 px, "Step n of 4" below 1100 px, status chip hidden below 900 px. Measured 768–1920 px: no overlap, Copy prompt inside the window.
- Checked in Chrome at 1440 light/dark with the embedded engine report, a data-URI preview, Try sample (fail) and two identical images (pass). Copy prompt text unchanged (engine, references). Flow clarity checks still pass.
- Diff: no URLs/fetch/XHR/eval. Tests unchanged: 113 passed, same 5 Edge-capture failures; `tests/test_browser.py` 7 errors (no Edge).
- Screenshots: `docs/screenshots/visual-fixes/` (`*-before.png` / `*-after.png` per item).

### Not done
- Edge not available in the cloud runner.

### Next
- Mobile fixes (branch from `feat/visual-fixes`)
- then Settings step 3: tab restructure

## Previous task: Flow clarity (Prompt A)

Branch: `feat/flow-clarity` (from `feat/add-reference` at a9ac1c4). One commit per item.

### Done
1. cb355a0 Guided empty state: steps "1 Load before & after", "2 Mark what changed", "3 Copy prompt"; primary "Load images" (opens the existing multi-file picker) and "Try sample" (existing loader); "Load report (.json)" kept. Disappears once images load.
2. a230d13 Header stepper Load → Review → Request → Copy, derived only from state (report loaded; a change selected, a request made, or no changes to review; ≥1 request; prompt copied this session). Current step in #2F80FF, done steps get a check. Labels hide under 1440 px; under 640 px it becomes "Step 2 of 4".
3. 6805a58 Disabled controls use aria-disabled (still hoverable/focusable) with a tooltip and aria-describedby reason: Copy prompt / Preview copy ("Add a request first"), Undo/Redo ("Nothing to undo/redo"), Swap ("Load an image first"), Add request / Save ("Mark an area first", limit), Note ("Mark an area first"), Duration/Easing ("Pick an animation first"), Approve ("Already approved"). One capture-phase guard turns a click on any aria-disabled control into a toast with the reason.
4. 0f8e543 Deleting a request shows "Request deleted" + Undo for 5 s; Undo restores it at the same index, including its reference (references stay in memory while undo history points at them). No confirm setting existed, so none was added.
5. d1b4723 Linked hover: hovering/focusing a change, request or Add row highlights its area on the stage (blue inset outline, no layout shift); hovering a change box or a saved request outline (now drawn faintly in Move/Add) highlights its row.
6. d3f114b "{n} of 8 requests" next to the Requests heading: amber at 7, red at 8 with "Limit reached. Copy this batch, then start a new one."; at 8 Add request / Save are locked with that reason.
- Checked in Chrome (1440 light/dark, 390 dark): all six acceptance items, no console errors. Copy prompt text unchanged (engine report, loaded images, references). Load images and Add reference unchanged.
- report.html: 406,529 → 419,589 bytes. Diff: no URLs/fetch/XHR/eval. Tests unchanged: 113 passed, same 5 Edge-capture failures; `tests/test_browser.py` 7 errors (no Edge).
- Screenshots: `docs/screenshots/flow-clarity/`.

### Not done
- Edge not available in the cloud runner.

### Next
- Settings step 3: tab restructure

## Previous task: Add reference

Branch: `feat/add-reference` (from `feat/load-images` at dc3b476).

### Done
- A (af8a7d0): "Reference (optional)" in the Add panel: Add reference picker, 72 px dashed drop zone ("Drop an image or GIF, or paste with Ctrl+V" / "Drop to add reference" while dragging). PNG/JPG/WebP/GIF, max 5 MB, one per request, exact error texts. Stored only in memory (`REFS`, object URLs; revoked when nothing uses them). 64×64 thumbnail (GIF animates), name `ref-{n}.{ext}` where n is the request number in the Copy prompt list, size, Replace / Remove icon buttons, toasts. Paste goes to the reference only while the Add panel (inspector) is focused and an area is marked; otherwise Load images keeps it (tested both ways). Requests list: `ref-n.ext` badge + Download reference action.
- B (1188766): "What should the AI copy from it?" Layout / Style / Animation / Interaction, single-select, tap again clears, selection blue, 28 px pills 12 px/500. A reference requires a kind ("Pick what to copy from the reference."). Guided questions per kind (Style·Copy multi-select, Direction only for Slide), 72 px muted labels, 120 ms fade (off with reduced motion). Note placeholder per kind. Existing helper chips moved to a "Quick notes" row under the questions.
- C: Copy prompt line `{n}. [Add · {Kind}] {name} — at x…` + Reference line + one answers line (speeds ~150/300/600 ms) + Note; Attachments line above the list and two extra Rules when references exist; toast "Prompt copied · Attach {k} reference files in your AI chat" with "Download references" (each file with its ref-n name); Preview prompt hint. Prompts without references are byte-identical to `feat/load-images` (checked).
- report.html: 383,754 → 406,529 bytes. Diff: no URLs/fetch/XHR/eval, no localStorage. Tests unchanged: 113 passed, same 5 Edge-capture failures; `tests/test_browser.py` 7 errors (no Edge).
- Screenshots: `docs/screenshots/add-reference/`.

### Not done
- 3D & motion kind (out of scope for this prompt). Edge not available. Browsers may ask once to allow several downloads when "Download references" saves more than one file.
- The Add panel's older Element hint / Animation fields stay; for Adds with a kind or reference they are not repeated in the prompt (the template has no line for them).

### Next
- Add reference polish: 3D & motion, 390px, a11y
- Queued now: Flow clarity (branch from `feat/add-reference`).

## Previous task: Load images in the UI

Branch: `feat/load-images` (from `feat/micro-animations` at 17038f5).

### Done
1. Empty report: Before / After drop zones (focusable buttons, "Drop image or click to choose", PNG/JPG/WebP) with a file picker; "Load report (.json)" kept as a secondary link.
2. Drag & drop: 2 files fill Before then After (names with before/baseline or after/current win); 1 file fills the zone it was dropped on, otherwise the first empty slot. Each slot shows thumbnail, file name, pixel size, file size, Replace and Remove; a Swap button between them. While reviewing loaded images the same slots sit in the Pages panel.
3. Paste: one router (`routePaste` + `claimPaste(fn, first)`); Load images is the default claimer, toast "Pasted into Before/After". Add reference can register with `first=true` to take paste when its panel is focused. Plain text paste is untouched.
4. Both slots filled: canvas diff in the browser using the engine's rules (tolerance 0, 32 px tiles, 8-way clusters, 3x3 zones, fail at 5% unexpected pixels), red-on-dimmed diff image, before/after crops (first 40 changes). All views, marking, requests and Copy prompt work. Page name = After file name without extension; viewport = image size. Different sizes: padded at the top-left (never stretched) + notice "Images have different sizes (A×B vs C×D). Aligned to top-left." Limits: over 20 MB or over 8000 px rejected with a message.
5. Try sample: a synthetic "Tidyday" mockup pair made for this task with Pillow (Montserrat text), 18 KB total, embedded as base64.
7. Errors: unsupported type, unreadable image, and dropped web addresses ("Web addresses can't be loaded. Drop an image file instead.") — non-local URLs stay blocked. A stray file drop never navigates the page away.
- `safePath` allows only blob: URLs this page created (tracked in `LOCAL_URLS`, revoked on remove/replace). Nothing goes to localStorage.
- report.html: 336,912 → 383,740 bytes (+46.8 KB, mostly the sample pair as base64 and the loader code).
- Checked in Chrome (1440 light, 390 dark): picker, drop, paste, Swap, Replace, Remove, Try sample, size notice (aspect kept 1.778), size/type/URL errors, keyboard focus on drop zones, requests + Copy prompt on loaded images, Load report (.json) and engine reports unchanged (Copy prompt text identical), no external requests, no console errors.
- Diff: no http(s) URLs, fetch, XMLHttpRequest or eval added; no localStorage writes. Tests unchanged: 113 passed, same 5 Edge-capture failures; `tests/test_browser.py` 7 errors (no Edge in the cloud runner).

### Not done
- 6 (optional, several pairs as Pages): not done.
- Edge not available in the cloud runner. Large images take a moment to compare; there is no progress indicator.

### Next
- Add reference (branch from `feat/load-images`).

## Previous task: Micro-animations

Branch: `feat/micro-animations` (from `feat/copy-prompt` at 578f076).

### Done
- Motion tokens on `:root`: `--dur-fast:120ms`, `--dur:200ms`, `--dur-slow:300ms`, `--dur-panel:160ms`, `--ease-out:cubic-bezier(.2,.8,.2,1)`. All keyframes are prefixed `oe-` and sit in one block before the reduced-motion rule.
- 1 Copy prompt: copy icon fades/scales out, a check draws with stroke-dashoffset (300 ms), holds 1.5 s, returns; label "Copied"; `#liveRegion` announces "Prompt copied". Runs only after the clipboard write succeeds.
- 2 New request row: fade + translateY(4px→0); the Requests badge pops 1→1.15→1. Only new rows animate, never ordinary re-renders.
- 3 Toasts: fade + translateY(8px→0) in, fade out, auto-dismiss after 3 s.
- 4 Selected area (Move selection, Add selection, selected change box): SVG marching ants, 1 s linear loop, blue #2F80FF (Add keeps its violet).
- 5 Delete: the row is removed at once; a copy fades + scales to .98 on top while the rows below slide up (FLIP, transform only).
- 6 Done verdict: a circle turns into a green check (stroke draw), once, the first time the Requests panel shows it.
- 7 Settings modal, palette, menus and tour slide + fade (160 ms); the inspector and the expanded sidebar slide in when opened; the mid-width drawer uses the 160 ms token. Removed the old grid-template-columns transition (layout property).
- 8 Pictures: shimmer only while an image is really loading, then a fade-in; cached pictures appear at once.
- Reduced motion: `@media (prefers-reduced-motion: reduce)` disables every animation and transition (incl. ::before/::after); keyframes animate FROM the hidden state, so the end state shows instantly (check visible, rows visible). JS skips the delete ghost and the replay classes. The app has no separate Reduce motion setting.
- Checked in Chrome with normal and reduced motion: all 8 behaviours, no console errors; Copy prompt text unchanged; no added URLs/fetch/XHR/eval. Tests: 113 passed, same 5 Edge-capture failures.

### Not done
- No in-app Reduce motion switch (none existed; the OS setting is the switch). Not tested in Edge (cloud has Chrome only).

### Next
- Load images (branch from `feat/micro-animations`).

## Previous task: Settings step 2 (one neutral Copy prompt)

Branch: `feat/copy-prompt` (from `feat/fonts` at 917cda6).

### Done
- Header: one bronze "Copy prompt" button (copy icon, tooltip "Copy all requests as one prompt for any AI assistant", Ctrl+Enter). With 0 requests it is `aria-disabled` with tooltip "Add a request first" (kept hoverable so the tooltip shows). Toast "Prompt copied · {n} requests".
- Removed: the target picker, `COPY_TARGETS`, `hermesText`, `agentText`, `messageData`, `buildMessage`. Old `prefs.copyTarget` is ignored and dropped on the next save. "Hermes" is gone from buttons, toasts, menus and the tour (About text left for a later step).
- `buildPrompt(requests, options)` builds the whole text; `promptRequests()` gives Move then Add drafts; `window.OrphicPrompt.build` is a read-only hook (tests, later references). Type labels Move / Revert / Hide / Comment / Add; per-type detail lines (Move target + precision, Add description + element/animation, Hide, Revert); "Note:" only when filled.
- "Preview prompt" link at the bottom of the Requests panel and in Ctrl+K; modal with read-only monospace text, Copy prompt + Close, Esc closes. Preview text equals the clipboard text (checked).
- Settings tab "Copy prompt" (after Canvas): Include coordinates, Add 'change nothing else' rule, Ask before guessing, Include page and viewport size (all default on, saved in prefs, survive reload) + info card with "Preview prompt".
- Verified in Chrome: all switches change the copied text immediately and after reload; all five types through `OrphicPrompt.build`; no console errors; light and dark.
- Screenshots: `docs/screenshots/copy-prompt/` (header disabled/enabled, Requests panel, Preview, Settings tab; light + dark).
- Diff: no http(s) URLs, fetch, XMLHttpRequest or eval added. Tests unchanged: 113 passed, the same 5 Edge-capture failures; `tests/test_browser.py` 7 errors (no Edge in the cloud runner).

### Not done
- Manual test in Edge: not possible in the cloud runner (Chrome only). Revert / Hide / Comment still have no UI to create them; they are covered by the builder and tested through the hook.
- The Review "Copy fix message" (single change) keeps its own short text.

### Next
- Load images (branch from `feat/copy-prompt`).

## Previous task: Embed UI fonts (Montserrat + JetBrains Mono)

Branch: `feat/fonts` (from `feat/settings-prefs` at b5fb078).

### Done
- Sources (official GitHub repos): Montserrat `JulietaUla/Montserrat` @ 555facf, `fonts/variable/Montserrat[wght].ttf`, Version 9.000. JetBrains Mono `JetBrains/JetBrainsMono` @ 1937130, `fonts/variable/JetBrainsMono[wght].ttf`, Version 2.305.
- Built locally with fonttools (not a plugin dependency): weight axis limited (Montserrat 400-700, JetBrains Mono 400-500), name table set to the plain family name so DevTools shows "Montserrat" / "JetBrains Mono", subset to U+0020-007E, U+00A0-00FF, punctuation U+2010-2027 / U+2030-203A, arrows U+2190-2199, € ™ − ↵, features kern/liga/calt/tnum/lnum/case kept, woff2, no hinting. Variable files were smaller than 4+2 statics (57.6 KB vs 90.9 KB).
- Embedded as base64 `@font-face` (font-display: swap) at the top of the `<style>`; `--font-ui` and `--font-mono` switched to the requested stacks.
- report.html: 252,296 → 329,531 bytes (+77,235 bytes, about +75 KB; target was under +250 KB). No weights dropped.
- Spacing fixes: none needed. A before/after scan of every clipped text node (1440: Review, a selected change, Move, Add, all 5 Settings tabs; 390: all 4 bottom-sheet tabs) found the same 7 clipped items at 1440 (existing intentional ellipses) and 0 at 390; no new clipping.
- Checked with external requests blocked: 0 external requests, DevTools rendered fonts = Montserrat (UI) and JetBrains Mono (mono fields).
- Licenses: `licenses/Montserrat-OFL.txt`, `licenses/JetBrainsMono-OFL.txt` (copied from upstream); README "Fonts" note under License.
- Screenshots: `docs/screenshots/fonts/` (main 1440 light/dark, 390 light/dark, Move 1440 light).
- Diff has no http(s) URLs, `<link>`, fetch, XMLHttpRequest or eval added. Tests unchanged: 113 passed, same 5 Edge-capture failures; `tests/test_browser.py` 7 errors (no Edge in the cloud runner).

### Not done
- ⌘, ✓ and ✕ are not in Montserrat; those few symbols fall back to the system font (they are not in JetBrains Mono's UI use either). Mono text at weight 600 uses the 500 face (the font is cut at 500 as asked).

### Next
- Settings step 2: Copy Prompt

## Previous task: Settings step 1 of 7 (preferences + auto-save)

Branch: `feat/settings-prefs` (from `feat/helper-chips` at d34fe0a). Only `engine/templates/report.html` and this file.

### Done
1. Precision: the toolbar Exact/Approx toggle saves `defaultPrecision` at once and is restored on load; changing "Default precision" in Settings calls the same `setPrecision`, so the toolbar updates immediately (no reload). Note: like the toolbar, it also applies to the Move request being edited.
2. Grid: one pref `showGrid` (old `grid` is migrated) drives Review, Move and Add; the Add-mode Grid button and Settings > Canvas > "Show grid" flip the same value. Review now draws the same grid over its pictures. Grid size stays in Canvas.
3. Accent row removed from Settings; an old `accent` key is ignored and dropped on the next save.
4. Every Settings control still applies and saves instantly; the modal has a footer "Changes save automatically." (no Save button).
5. Old prefs: unknown keys dropped, wrong types fall back to defaults, broken JSON or cleared storage loads defaults with no errors.
- Checked in Chrome: precision survives reload, Settings → toolbar at once, grid off/on matches in all three modes and survives reload, old prefs `{accent, grid:false, snap:'yes', textSize:'xl', ...}` load without console errors, footer visible in light and dark.
- Diff contains no added fetch / XMLHttpRequest / eval.
- Tests: 113 passed; the same 5 Edge-capture failures (test_plugin ×2, test_roundtrip ×3); `tests/test_browser.py` 7 errors because no Edge in the cloud runner (unchanged).

### Not done
- Review mode has no Grid button in its toolbar; the grid there is controlled from Settings (and from the Move/Add buttons). Copy for Hermes / targets untouched (step 2). Tabs not restructured (step 3).

### Next
- Settings step 2: Copy Prompt

## Previous task: Helper chips

Branch: `feat/helper-chips` (from `feat/add-action` at 6329be2).

### What I found
- Only Move and Add can be created in the UI (hide/revert/comment are engine-only, see the Add action notes).
- Add already has a free-text field (the required description). Move has only a short label, no note.

### Plan (report.html + this file only)
- Move gets an optional **Note** field (`#selectionNote`, max 240 chars). In the export it is one extra line `Note: …`, written ONLY when the note is not empty, so a Move without a note exports byte-for-byte as before. The note stays out of the engine JSON (the contract has no note field).
- Under the Move note and under the Add description: chip groups Colour / Size / Position / Text with the 11 static English phrases from the task.
- Tap (or Enter/Space) appends the phrase to the field: empty field → the phrase with a capital first letter; otherwise `; ` + phrase. Never replaces typed text. Focus returns to the field with the caret at the end; one undo step per chip.
- Chips are plain `<button>`s (Tab-reachable), Mockup E pill style, tokens only, so light/dark work. No network, no dependencies.

### Done
- Move: optional Note field with undo (one step per edit or chip). Export adds `Note: …` (Hermes) / `- Note: …` (other AIs) only when filled; verified a note-less Move export is byte-identical to `feat/add-action`.
- Chips (Colour, Size, Position, Text; 11 phrases) under the Move note and the Add description. Append rule: empty → capitalised phrase; else `; ` + phrase. Never erases text; caret returns to the field.
- Keyboard: Tab to a chip, Enter or Space presses it. Fixed: Space on a focused button no longer switches to the Hand tool.
- Tests: 113 passed, the same 5 Edge-capture failures as before.

### Next
- Owner check: are the 11 phrases the right ones? They are one array (`NOTE_CHIPS`) and easy to change.
- Hide / revert / comment still have no UI; when they get one, reuse `chipBlock(fieldId)` for their note.
- Merge order when approved: `ui-overhaul` → `feat/copy-targets` → `feat/add-action` → `feat/helper-chips`.

## Previous task: Add action

Branch: `feat/add-action` (from `feat/copy-targets` at 2cd2104).

### What I found
- The engine (`engine/requests.py`, `docs/report-contract.md`) only accepts `move`, `hide`, `revert`, `comment`, max 8. It rejects any other type, so an "add" can NOT be sent to `orphic_compare`.
- The UI already has an **Add mode** (ADD-n drafts: label, element hint, animation). They are copied as plain instructions under "Add instructions (not verified by the engine)" and never enter the requests JSON.
- In the UI only **Move** can be created. Hide, revert and comment exist only in the engine; there is no UI for them yet. No action has reorder.

### Plan (report.html + this file only; no engine change needed)
- Build on the existing Add mode instead of adding a second "add" path.
- New required field "What should be added here?" (`#addDescription`). Saving or copying with an empty description is blocked with an inline message and a toast; the field is marked `aria-invalid`.
- The label becomes optional ("Short name"); element hint and animation stay.
- Export (every copy target): `ADD at (x …, y …, w …, h …) on the After image: <description>. Do not change anything else.` plus element/animation and the existing "not verified" line. Add items stay out of the engine JSON.
- One limit of 8 for Move + Add together (checked when saving either).
- Own colour for Add (violet `--add`) on the placement box, tag, tool and list chip; Move keeps blue.
- Edit (select the row), delete (row ×) and undo/redo work like Move drafts. No reorder, because no action has it.
- Move/hide/revert/comment output stays byte-for-byte the same; verified against `feat/copy-targets`.

### Done
- Required "What should be added here?" field (`#addDescription`, max 240 chars). Save and the single-instruction Copy are blocked while it is empty: inline red message, `aria-invalid`, focus moves to the field, toast "Describe what should be added here."
- Optional "Short name"; element hint and animation kept. A saved Add never loses its description while editing (an emptied field is not synced).
- Export for every copy target: `ADD at (x …, y …, w …, h …) on the After image: <description>. Do not change anything else.` + element/animation + "not verified" line. Still outside the engine JSON.
- One limit for Move + Add (`requestCount()`), checked on both save paths; verified 8 → extra Add and extra Move refused.
- Violet `--add` colour (light + dark) on the placement box, tag, active tool and list chip.
- Verified: Move-only export (Hermes and ChatGPT) is byte-identical to `feat/copy-targets`. Tests: 113 passed, same 5 Edge-capture failures as before.

### Next
- Owner check on Windows: create an Add, paste the text into Hermes/ChatGPT/Claude and see if the agent does it.
- Decide whether the engine should get an `add` type later (verify only "this area changed"); that needs `engine/requests.py`, the report contract and tests, so it waits for approval.
- UI for hide / revert / comment does not exist yet (engine-only). Reorder is not implemented for any action.
- Merge order when approved: `ui-overhaul` → `feat/copy-targets` → `feat/add-action`.

## Previous task: Copy target picker

Branch: `feat/copy-targets` (from `ui-overhaul` at 5ef916f).
Scope: `engine/templates/report.html` and this file only.

### Plan
- Header: keep `#copyMain` as the main button and add a small caret button `#copyTarget` next to it (one split control). The caret opens a menu with exactly 5 targets: Hermes (default), ChatGPT, Claude, Gemini, Antigravity.
- The main button label follows the choice ("Copy for Claude"). Tooltip, aria-label, toast ("Copied for Gemini"), palette entries and tour step follow it too.
- The choice is saved as `copyTarget` in the existing prefs object (localStorage key `orphic-eyes.prefs.v1`), so it survives a reload.
- One entry point `buildMessage(target)`:
  - `hermes` → the existing `hermesText()`, untouched, so the Hermes output stays byte-for-byte the same.
  - the other four → `agentText()`, which reads the SAME data (`messageData()`): changed areas, checked request verdicts, Move drafts (via `requestObject`) and Add drafts. Only the wrapper differs: a plain-English intro (visual review of screenshots, pixels of the After image, change only what is listed, report back), then a numbered Markdown list. No Hermes-only commands (no `orphic_compare`, no raw JSON).
- Menu keyboard: Enter/Space/ArrowDown open it, arrows move, Enter/Space pick, Esc closes and returns focus to the caret. Uses the existing `.menu` style, so light/dark already work.
- No network calls, no new dependencies.

### Done
- Split Copy control: `#copyMain` + caret `#copyTarget` with a 5-item menu (Hermes, ChatGPT, Claude, Gemini, Antigravity). Keyboard: Enter/Space/ArrowDown open, arrows/Home/End move, Esc closes and returns focus.
- Label, tooltip, aria-label, toast ("Copied for Gemini"), command palette ("Copy for ..." per target) and tour step follow the chosen target.
- Choice saved as `copyTarget` in `orphic-eyes.prefs.v1`; survives reload.
- `buildMessage(target)`: Hermes = `hermesText()` unchanged (verified byte-identical against `ui-overhaul` with 2 moves + 1 add); other targets = `agentText()` built from `messageData()` in the same order (unexpected-change fix, moves, adds), then earlier verdicts as context.
- No network calls, no new dependencies. Tests: 113 passed; the same 5 browser-capture tests fail as on `ui-overhaul` (they need Edge headless, not available in the cloud runner).

### Next
- Owner review of `ui-overhaul` + `feat/copy-targets` in a real browser on Windows.
- Decide: should "Not done" requests from an earlier run be listed as context only (current) or as new work in the agent text?
- Optional: the 4 agent targets share one text; give each its own wording only if a real paste test shows a need.
- Merge order when approved: `ui-overhaul` first, then `feat/copy-targets`.
