# Orphic Eyes

**Give Hermes eyes: compare screenshots, point at what needs changing, and turn pixels into precise requests for any AI coding agent.**

## Why

Telling an AI what looks wrong is slow and vague. Orphic Eyes gives Hermes a visual review loop: show the difference, mark the area, describe the intended change, and check the next screenshot.

Built for the Nous Research Hermes Agent Plugin Hackathon. This is a submission candidate, not an approved catalog listing.

> **Branch status:** this README includes the engine from `feat/auto-loop`. UI features marked **release UI** were inspected on `release/hackathon` at `aa8f14c2308aeaacab825ba8ec139ba4ee97bb54`; they are not all included in this branch's template. A final combined release and validation are still required.

**TODO — demo video:** add a public video link, under 90 seconds.  
**TODO — screenshots:** add captures of the final combined release; no current screenshot is presented as that release.

## Compare → point → request → verify

1. **Compare:** load Before/After images, or let the engine capture two URLs. Review changed zones.
2. **Point:** mark the area and its intended destination or placement.
3. **Request:** create Move/Add instructions, choose Exact/Approx precision, and copy a plain prompt into your coding agent.
4. **Verify:** capture the edited page again. Review request verdicts and unexpected changes, then use a follow-up prompt for the next edit.

## Features

| Feature | Availability |
| --- | --- |
| Before/After pixel diff, changed boxes and 3×3 zones | Engine and report UI |
| Move requests, Add instructions, Exact/Approx placement | Report UI; engine precision is 2/8 px per axis for supported crop requests |
| Copy Prompt for any AI coding agent | Report UI; copying does not send anything |
| Verify: next-round pass/fail/unclear checks, unexpected changes, follow-up prompt | **Release UI** |
| Content check | **TODO: implementation not found at the inspected release commit; confirm before advertising** |
| URL capture with fixed viewport, DPR 1 and bounded waits | Engine |
| `orphic_loop_step`: capture, review fixed goals, return a follow-up prompt and stop condition | Engine/Hermes adapter |
| Local read-only HTTP report server so image pixels share the report origin | Engine |
| Settings, light/dark themes and shortcuts | Report UI; shortcut **rebinding is release UI** |
| Embedded Lumen sample | **Release UI**; distinct from the engine demo below |
| Offline report with embedded fonts, CSS, JavaScript and report data | Report UI; generated reports keep PNGs/crops beside report.html |

The engine accepts move, revert, hide and comment intents. Add instructions are copied for a coding agent and are not an engine request type. UI Verify verdicts and engine `done`/`not_done`/`unknown` verdicts are separate systems. Neither establishes semantic identity or code correctness.

## Install

Requirements: Python 3.12+, Pillow (`Pillow>=10,<14`) and an installed Edge, Chrome or Chromium browser. The engine can select a browser with `ORPHIC_BROWSER`. No model API key is required by Orphic Eyes.

With Hermes installed, this command pins the **engine feature commit**, not the final hackathon submission:

```sh
hermes plugins install Ilham-Musyafa/orphic-eyes --ref ab5f9e3e836e6a49786e2920fea30ce14edfb36e
```

Installation by catalog name becomes available only after maintainer admission. Do not install from the draft's zero SHA. **TODO — final release pin:** combine the intended engine/UI release, validate it, and replace the draft pin with its full 40-character SHA.

From an existing repository checkout, install the Python dependency:

```sh
python -m pip install -r requirements.txt
```

## Quick start

From the repository root, run the included synthetic **Lumen Demo** engine scenario:

```sh
python -B demo/run_demo.py --repeat 2
python -m engine.cli serve --store demo/output --timeout 600
```

The demo regenerates tracked `demo/output/` artifacts; run it in a disposable checkout or preserve existing outputs first. It expects one done, one not_done and one unknown verdict. Its repeatability check can abort if the fixed search budget is exhausted on a busy or slow runner; do not loosen the matching rules to obtain a pass. The server prints an HTTP report URL. Open that URL for pixel-based Verify rather than opening report.html from disk; stop the server with Ctrl+C or let the timeout expire. A generated report is an offline folder bundle, not a standalone HTML file containing every PNG.

To capture the existing local fixtures, use two terminals from the repository root:

```sh
# Terminal 1: serve the test pages.
python -m http.server 8000 --bind 127.0.0.1 --directory tests/fixtures
```

```sh
# Terminal 2: capture and compare; use a fresh target name on each run.
python -m engine.cli capture-pair http://127.0.0.1:8000/page_a.html http://127.0.0.1:8000/page_b.html --store ./review-store --name first-review --allow-local
python -m engine.cli serve --store ./review-store --name first-review --timeout 600
```

`--allow-local` explicitly permits trusted private/loopback HTTP(S) destinations. Omit it for public sites. CLI visual exit codes are pass=0, check=1, fail=2 and error=3; a check result is a successful comparison that needs review. Both URLs use the same viewport. Existing targets are preserved: capture-pair requires a fresh name.

## Hermes tools

The plugin registers `orphic_baseline`, `orphic_compare`, `orphic_loop_step`, `orphic_approve`, `orphic_accept` and `orphic_ignore` in the `orphic` toolset. `/orphic doctor` checks the local runtime; `/orphic demo` exercises the adapter's offline demo. These are Hermes chat commands, not shell commands.

Capture two local pages without a prior baseline:

```json
{"name":"orphic_compare","arguments":{"name":"preview","before_url":"http://127.0.0.1:8000/page_a.html","after_url":"http://127.0.0.1:8000/page_b.html","width":1440,"height":900,"allow_local":true}}
```

The response includes `paths.report`, optional `paths.html`, `summary.box_count`, and `report_url` when a report server is running; otherwise `serve_hint` gives its startup command.

After the coding agent edits the page, review one round:

```json
{"name":"orphic_loop_step","arguments":{"name":"preview","after_url":"http://127.0.0.1:8000/page_b.html","allow_local":true,"max_rounds":3}}
```

The engine returns per-zone verdicts, unexpected zones, `follow_up_prompt`, `should_stop` and `stop_condition`: continue, done, max_rounds or needs_human. Hermes performs any authorized code edits; the engine never executes the prompt. With requests omitted, the goal is restoration of the original reference appearance. Supply baseline-relative Point & Tell requests on the first call for supported explicit changes. Goals stay fixed throughout the session. Do not use restoration mode to undo an intentional redesign accidentally.

See [AUTO-LOOP.md](docs/AUTO-LOOP.md) for request-mode examples, the full argument table, stored evidence and stop semantics. See [the report contract](docs/report-contract.md) for pixel/report details.

## Limits

- Pixels only: no OCR, page-source reading, DOM-content inspection or text understanding. The browser applies rendering overrides, such as disabling motion; comparison uses screenshots.
- Crop matching is grayscale, local and bounded. Flat/repeated content, changed appearance or exhausted search time can produce unknown/needs_human. Hide means a crop was not found in the searched area, not proof of DOM removal.
- Add requests, animations, video/canvas content and semantic correctness are not fully verifiable from still pixels. Login walls, cookie banners, headless blocking, fonts and dynamic content can alter captures.
- Linux Chrome has automated coverage. Windows/Edge, macOS and a live Hermes host have not been verified by this project's automated tests. Recreate baselines across browsers or operating systems.
- Public DNS and outbound access must work. Private destinations are blocked by default, including redirects/resources; public-IP pinning can conflict with hostname-only proxy policies.
- **TODO — admission validation:** `hermes plugins validate . --install-deps` must pass on the final pinned release. The Hermes executable was unavailable in this development environment; repository tests are not a substitute for that gate.

## Privacy and runtime disclosures

The report UI performs its review locally and has no automatic network-service client or upload path. Fonts/sample assets are embedded; images selected by the user or served next to a report are read locally. Copy Prompt writes to the clipboard only when requested. Opening the HTTP report naturally requests its HTML and PNGs from the local server.

URL capture navigates to the URLs the user supplies; those pages may load subresources, follow redirects or make their own network requests. It is not an arbitrary crawler, and there is no Orphic-hosted screenshot service. The guarded capture path accepts HTTP/HTTPS only, blocks private addresses unless `allow_local` is explicit, and never permits file/javascript/data input URLs. The legacy local baseline API separately supports local file pages; it is not the guarded public-URL API.

- **Reads/writes:** screenshots, reports, requests, approvals and loop history are stored locally. Hermes storage is under its resolved home's `orphic-eyes/`; standalone callers choose a store. Explicit input images/pages, Python packages, browser executables and system fonts can be read outside that store. Doctor probes storage write access.
- **Processes:** captures launch an installed headless browser with argument lists, not a shell. URL capture uses a temporary loopback guard proxy and browser profiles. The optional report server is a long-running loopback process until Ctrl+C/timeout; it serves only report HTML/JSON and PNGs. Temporary profiles are cleaned up, but captured content may itself contain sensitive information.
- **Credentials:** no credential store or .env files are read, no model credentials are required, and no source URL is saved by the new capture/loop path. Legacy baseline state can save URLs. Avoid credential-bearing URLs. Pages can create temporary cookies; existing proxy/CA configuration is inherited.
- **Telemetry:** no plugin telemetry or usage reporting is implemented. Browser behavior and resources loaded by captured pages remain outside this claim.

These runtime disclosures must also accompany the future catalog PR. **TODO — PR disclosures:** copy and review them against the final pinned code before submission; no PR has been created by this documentation task.

## Authorship, assets and affiliation

Built by **Ilham Musyafa** with AI coding assistants: **Claude Code, OpenAI Codex and Cursor**.

- Project code: [Apache License 2.0](LICENSE).
- Montserrat: The Montserrat Project Authors, [SIL Open Font License 1.1](licenses/Montserrat-OFL.txt).
- JetBrains Mono: The JetBrains Mono Project Authors, [SIL Open Font License 1.1](licenses/JetBrainsMono-OFL.txt).
- Lumen and other sample/mockup images were created for this project; they are synthetic examples, not customer screenshots. No third-party stock-photo attribution is claimed.

Orphic Eyes is an independent community project and is **not affiliated with or endorsed by Nous Research**.

## Submission draft and development

[Draft catalog entry](docs/catalog/orphic-eyes.yaml) — the zero SHA is deliberately unusable until the final release is selected. The draft follows the [upstream catalog schema](https://github.com/NousResearch/hermes-agent/blob/main/plugin-catalog/README.md), using these real examples: [Accent Picker](https://github.com/NousResearch/hermes-agent/blob/main/plugin-catalog/accent-picker.yaml) and [Accessible Session List](https://github.com/NousResearch/hermes-agent/blob/main/plugin-catalog/accessible-session-list.yaml).

Run the existing tests from the repository root:

```sh
python -B -m unittest discover -v
```

Browser tests skip when no browser is installed; launch failures with an installed browser are errors to investigate. In restricted CI environments, use supported browser launch permissions rather than disabling browser sandboxing or TLS verification. [HANDOFF.md](docs/HANDOFF.md) records this branch's command verification and test evidence.
