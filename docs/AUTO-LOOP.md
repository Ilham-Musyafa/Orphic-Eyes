# Local reports and the Hermes review loop

Orphic Eyes captures and compares pixels. Hermes can make code edits between
review rounds, but the engine does not read code, recognize text, identify DOM
elements, edit the website, run an AI model, or send a prompt anywhere.

## Open reports over HTTP

Opening report.html from disk can prevent the report's Verify feature from
reading image pixels. Serve the report and its adjacent PNGs from one origin:

```sh
python -m engine.cli serve
# Explicit store and target; stop with Ctrl+C or after 600 seconds:
python -m engine.cli serve --store /path/to/store --name preview --timeout 600
# Optional fixed port; otherwise an available port is selected automatically:
python -m engine.cli serve --store /path/to/store --port 8766
```

The command prints the latest report's `http://127.0.0.1:PORT/.../report.html`
URL, or the latest report inside `--name`. Without `--store`, it uses Hermes'
home resolver, then HERMES_HOME, then `~/.hermes`, with `/orphic-eyes` appended.
An empty existing store can be served before the first capture; its root URL
finds the latest report when artifacts become available.

The server binds only to 127.0.0.1. It serves report.html, report.json and PNGs,
with no directory listings or arbitrary-file access. Traversal, hidden files,
symlinks, hard links, unexpected Host headers and cross-origin browser requests
are refused. GET/HEAD are read-only; write methods are refused. Store contents
must remain locally trusted; do not replace directories with links while serving.
Stop the process to revoke access. Do not expose it through a public tunnel.

The private `.orphic-server.json` registry lets separate CLI/Hermes processes
discover the server after checking a live, instance-specific loopback endpoint.
`orphic_compare`, CLI `capture-pair`, and loop rounds return `report_url` while
that server is alive; otherwise they return `report_url: null` and `serve_hint`.
These fields are response metadata, not additions to the persisted report schema.
If HTML generation is unavailable, a served JSON report is not an interactive
Verify page. Restart the server after restoring an environment snapshot.

## Choose the completion goal

Create a named target using the existing `orphic_baseline` or paired-URL mode
of `orphic_compare`. The loop snapshots the target's original baseline and
initial current image on its first call. If there is no current image, it uses
the baseline as the initial previous image. Subsequent changes to the root
target do not replace these session anchors.

There are two modes:

- **Restore mode:** omit requests. Each initially changed box must match the
  original reference pixels again. Use this only when the intended fix is to
  restore the reference appearance. A requested redesign should not blindly be
  reverted to an old screenshot.
- **Request mode:** supply the existing Point & Tell move/hide/revert/comment
  array on the first call. Coordinates and source crops refer to the original
  baseline, with the existing 8-request limit, matching threshold, precision
  tolerances, bounded search and time budget. Later calls can omit requests to
  reuse them. Changed goals require a fresh target/session.

The round report compares the previous image with the new screenshot. Goal
verdicts remain anchored to the reference; no new changes does **not** mean a
wrong page is fixed. Unexpected zones are recalculated against the reference
outside the expected goal regions, so a side effect remains visible even when
it stops changing between rounds. Existing 32px tile clustering, 3x3 zone names
and the 5% visual-failure threshold are unchanged.

## Ask Hermes to drive the loop

Example instruction to Hermes:

> Compare the live reference with my preview as target preview. The goal is to
> restore the reference appearance in the differing areas. Start a local report
> server for the Orphic Eyes store and give me its HTTP report URL. Run at most
> three review rounds. For each round call orphic_loop_step, inspect the reference,
> current image and follow_up_prompt, make only the authorized source edits, and
> recapture. Stop immediately when should_stop is true. Ask me for clarification
> on needs_human; do not guess text, page structure or intent from pixels.

Initialize using a fresh name (public URLs are accepted when DNS/network policy
permit them; the local example needs explicit allow_local):

```json
{"name":"orphic_compare","arguments":{"name":"preview","before_url":"http://127.0.0.1:8000/reference.html","after_url":"http://127.0.0.1:8000/current.html","width":1440,"height":900,"allow_local":true}}
```

First round:

```json
{"name":"orphic_loop_step","arguments":{"name":"preview","after_url":"http://127.0.0.1:8000/current.html","allow_local":true,"max_rounds":3}}
```

Example response excerpt for a still-incorrect page:

```json
{"success":true,"round":1,"stop_condition":"continue","should_stop":false,"goal_mode":"restore","failing_count":1,"unexpected_count":0,"per_zone":[{"id":"Z1","bbox":{"x":40,"y":70,"w":48,"h":32},"status":"not_done","still_changed":true}],"follow_up_prompt":"Pixel-only visual review, round 1.\nFix only the unresolved items below...","report_url":"http://127.0.0.1:PORT/preview/loop/round-001/report.html"}
```

Hermes reads the full prompt, makes the authorized fix, then repeats the same
tool call with name and after_url. It does not pass an ever-changing goal list.
After the page matches the reference:

```json
{"success":true,"round":2,"stop_condition":"done","should_stop":true,"failing_count":0,"unexpected_count":0,"per_zone":[{"id":"Z1","status":"done","still_changed":false}],"follow_up_prompt":"Pixel review is complete for the listed goals. No further changes are requested."}
```

Request-mode example (a move, rather than restoring all initial differences):

```json
{"name":"orphic_loop_step","arguments":{"name":"preview","after_url":"https://preview.example.com/","requests":[{"id":"PT-1","type":"move","from":{"x":40,"y":70,"w":48,"h":32},"to":{"x":100,"y":70,"w":48,"h":32},"precision":"exact"}]}}
```

Use a fresh initialized target if switching modes or changing requests.

## Schema and command-line equivalents

`orphic_loop_step` has object arguments, `additionalProperties: false`:

| Argument | Type | Meaning |
| --- | --- | --- |
| name | string, required | Existing target; same name every round |
| after_url | string, required | HTTP/HTTPS page to capture this round |
| requests | array, optional | Existing Point & Tell schema, at most 8; fixed at first call |
| max_rounds | positive integer, default 3 | Fixed at first call; omit later to reuse |
| allow_local | boolean, default false | Explicit permission for trusted private/loopback destinations |
| wait_ms | nonnegative integer, default 250 | Additional wait after network idle |
| timeout_ms | positive integer, default 30000 | Capture deadline; greater than wait_ms |

The `orphic_compare` input schema is unchanged from URL capture. Its response
now includes report_url/serve_hint. Print the exact registered schemas:

```sh
python -c 'import json, orphic_tools; print(json.dumps([schema for name, schema, handler in orphic_tools.TOOL_DEFINITIONS if name in ("orphic_compare", "orphic_loop_step")], indent=2))'
```

Python API: `engine.loop_step(name, after_url, store_dir=None, requests=None,
max_rounds=None, allow_local=False, wait_ms=250, timeout_ms=30000, browser=None)`.
The omitted round limit becomes 3 on first use and is reused thereafter.

```sh
python -m engine.cli capture-pair BEFORE_URL AFTER_URL --store STORE --name preview
python -m engine.cli serve --store STORE --name preview --timeout 600
python -m engine.cli loop-step preview AFTER_URL --store STORE --max-rounds 3
python -m engine.cli loop-step preview AFTER_URL --store STORE
# Trusted local test pages additionally need --allow-local.
# Optional initial --requests points to a JSON request list, never an .env file.
```

The loop CLI returns exit 0 for a completed review operation, including a stop
requiring human review; inspect stop_condition. Errors return exit 3. Existing
capture-pair visual exit codes remain pass=0, check=1, fail=2, error=3.

## Stop conditions and stored evidence

- `continue`: failing goals or unexpected zones remain; Hermes may make another
  authorized edit and call the next step.
- `done`: no failing/unclear items and no unexpected zones remain. This is a
  pixel result, not semantic correctness or proof of implementation.
- `max_rounds`: the configured number of rounds has been reached while failures
  remain. Stop and review with a person.
- `needs_human`: ambiguous/low match, exhausted search budget, viewport mismatch
  or a comment without a pixel test. Stop and clarify; never relax assertions.

Terminal sessions return the last round with `already_stopped: true` without
another capture. A stopped session is not silently reset. Requests and the round
limit are fixed; create a fresh initialized target to start over.

Files live under `STORE/name/loop/`: session.json, reference.png, initial.png and
round-001/, round-002/, etc. Each round contains the previous image as baseline.png,
current.png, diff.png, goal-diff.png, metadata.json, report.json, optional report.html,
round.json and prompt.txt. Paths identify all evidence. Failed captures do not
publish a partial round. The per-target .loop-lock prevents concurrent steps;
after a crash, remove a stale lock only after confirming its process stopped.

Full per-zone results and prompts are in round.json/prompt.txt. Hermes responses
respect the existing 4KB budget and explicitly count omitted entries or mark a
truncated prompt; read the complete prompt before editing. Prompt text is plain
and can be used with any coding assistant; the engine never executes it.

## Limits and safety

Only HTTP/HTTPS capture inputs are allowed. Private addresses, including
redirects and subresources, are blocked unless allow_local is explicitly true;
file/javascript/data inputs remain forbidden. DNS and proxy restrictions are
fail-closed. The URL-capture proxy pins public addresses, so hostname-only
CONNECT allowlists or credential routes may refuse them. No TLS or browser
sandbox verification is disabled. No .env files are read, source URLs are not
persisted, and browser/report-server request logs are suppressed.

Pixels do not establish text meaning, DOM removal or code identity. Matching
uses grayscale crops and bounded regions; repeated/flat content, changed crop
appearance, expected-region padding and tile-box merging limit what can be
proven. Comments require a human. Animations, video/canvas, fonts, login state,
cookie banners and sites blocking headless browsers can affect captures.
Restoring pixels can undo intentional design changes unless the goal was chosen
correctly. No network/model service or new dependency is added.

Linux Chrome is covered by local HTTP integration tests, including same-origin
canvas pixel reads and a two-round fix. Windows/Edge and a live Hermes host are
not tested in this session. See HANDOFF.md for exact validation counts, verified
commands, artifacts and pushed refs.
