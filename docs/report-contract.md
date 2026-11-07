# Orphic Eyes report contract (Stage 5e)

The engine remains image-only, local and offline. No target DOM, CSS selector,
source-code analysis or report UI is provided. `schema_version` remains **1**;
Stages 5c/5d add optional fields. Readers must tolerate absent optional fields and
ignore unknown fields. All rectangles use integer natural screenshot pixels,
origin top-left, `{x,y,w,h}`; right/bottom edges are exclusive. DPR is 1 for plugin
captures. Diff boxes are changed-pixel clusters, **not element bounds**.

## Inputs: requests

Optional `orphic_compare.requests` / `engine.compare(..., requests=...)` is a
list of at most 8 objects. CLI `--requests path.json` reads the same JSON list.
Explicit null, duplicate IDs, unsupported fields/types, malformed/out-of-image
rectangles, booleans as coordinates and unequal move crop sizes are rejected.
Each id matches `^PT-[1-9][0-9]{0,2}$` and is unique within the list.

```json
[
  {"id":"PT-1","type":"move","from":{"x":104,"y":180,"w":190,"h":48},"to":{"x":74,"y":180,"w":190,"h":48},"precision":"exact"},
  {"id":"PT-2","type":"hide","from":{"x":800,"y":50,"w":80,"h":32}},
  {"id":"PT-3","type":"revert","from":{"x":32,"y":300,"w":120,"h":40}},
  {"id":"PT-4","type":"comment"}
]
```

- `from` is required for move/hide/revert, always in the **baseline** image.
  It is the complete user-selected crop, including any captured background.
- `to` is required only for move, in the **after** image; its width/height must
  equal `from`. This verifies relocation, not resizing. Revert targets `from`.
  Comment has no from/to and creates no request crop. Hide has no to.
- `precision` defaults to `approximate`: 8 px per axis; `exact`: 2 px per axis.
  The top-left position is compared, using `abs(dx)<=tolerance && abs(dy)<=tolerance`.
- Searches use a 64 px pad around source and destination. Overlapping windows
  are merged; distant windows are searched separately, not across the page
  between them. Searches never expand globally to find a missing object.
- Score is `1 - mean(abs(gray_before_crop-gray_after_candidate))/255`.
  `MATCH_MIN=0.92`, `UNIQUE_GAP=0.03`; the best high-scoring match must beat
  every candidate whose top-left is at least 4 Euclidean px away by >=0.03.
  A coarse pass proposes candidates; a disjoint-block MAE lower bound screens
  all remaining positions before full-resolution scoring of plausible matches.
  Below threshold the reported match is the best observed low score, with
  absence at MATCH_MIN checked; it is not a reliable location estimate.
- Flat grayscale crops never establish uniqueness. Repeated, altered, occluded
  or off-window content can yield unknown. Grayscale matching does not verify
  colors, semantic identity, DOM removal, layout constraints or other viewports.

## Full `report.json`

Saved under `<store>/<name>/report.json`. Required pre-existing fields:

| Field | Meaning |
| --- | --- |
| `schema_version` | Integer 1. |
| `name` | Target name. |
| `status` | `pass`, `check`, `fail`; only unexpected, unapproved changes affect severity. |
| `summary` | `changed_px`, `changed_percent`, `box_count`, `unexpected_count`. |
| `size` | Actual after image `{width,height}`. |
| `images` | Relative `before`, `after`, `diff` PNG filenames; `diff` is null after accept. |
| `boxes` | Full, untruncated array of `{id,x,y,w,h,zone,percent,label,approved}`; optional `shift:{dx,dy}`. |
| `ignore_regions` | Clipped named `{name,x,y,w,h}` regions. |
| `meta` | `browser`, `os`, `viewport:{width,height,preset?}`, `created_at`, `tolerance`. |
| `note` | Optional existing notes such as `size_mismatch` or `only_expected_changes`. |

Optional Stage 5c fields:

| Field | Meaning |
| --- | --- |
| `requests` | Normalized input list, including explicit default precision. Absent when no requests were supplied. |
| `request_results` | Ordered per-ID verdicts, full details below. |
| `requests_ok` | True iff every non-skipped request is done (also true for empty/comment-only lists). |
| `request_counts` | Counts under `done`, `not_done`, `unknown`, `skipped`. |
| `crops` | `{pad:16,max_side:640,items:[{id,before,after}]}`. Each side is `{path,bbox,scale,size}` or null if it cannot intersect the image. |

Example full report (illustrative metrics):

```json
{
  "schema_version":1,"name":"login","status":"pass",
  "summary":{"changed_px":2300,"changed_percent":0.25,"box_count":1,"unexpected_count":0},
  "size":{"width":1280,"height":720},
  "images":{"before":"baseline.png","after":"current.png","diff":"diff.png"},
  "boxes":[{"id":1,"x":74,"y":180,"w":220,"h":48,"zone":"top-left","percent":0.25,"label":"expected","approved":false}],
  "ignore_regions":[],
  "meta":{"browser":"/path/to/browser","os":"Windows","viewport":{"width":1280,"height":720,"preset":"desktop"},"created_at":"2026-11-06T19:00:00+07:00","tolerance":0},
  "note":"only_expected_changes",
  "requests":[{"id":"PT-1","type":"move","precision":"exact","from":{"x":104,"y":180,"w":190,"h":48},"to":{"x":74,"y":180,"w":190,"h":48}}],
  "request_results":[{"id":"PT-1","status":"done","found":{"x":74,"y":180,"w":190,"h":48},"moved":{"dx":-30,"dy":0},"off":{"dx":0,"dy":0},"match":1.0,"why":"Within target tolerance"}],
  "requests_ok":true,"request_counts":{"done":1,"not_done":0,"unknown":0,"skipped":0},
  "crops":{"pad":16,"max_side":640,"items":[
    {"id":"box-1","before":{"path":"crops/box-1-before.png","bbox":{"x":58,"y":164,"w":252,"h":80},"scale":1.0,"size":{"width":252,"height":80}},"after":{"path":"crops/box-1-after.png","bbox":{"x":58,"y":164,"w":252,"h":80},"scale":1.0,"size":{"width":252,"height":80}}},
    {"id":"req-PT-1","before":{"path":"crops/req-PT-1-before.png","bbox":{"x":88,"y":164,"w":222,"h":80},"scale":1.0,"size":{"width":222,"height":80}},"after":{"path":"crops/req-PT-1-after.png","bbox":{"x":58,"y":164,"w":222,"h":80},"scale":1.0,"size":{"width":222,"height":80}}}
  ]}
}
```

### Request verdicts are independent of visual status

- Move/revert: unique high-scoring match within tolerance -> done; unique match
  outside tolerance -> not_done; low score/ambiguity -> unknown.
- Hide: score below MATCH_MIN -> done (bounded visual absence); otherwise not_done,
  even if the location is ambiguous. A size mismatch makes non-comment requests
  unknown rather than treating a cropped-away object as hidden.
- Comment -> skipped. `why` is <=80 characters. `found` is a source-sized
  rectangle only for a unique high-scoring location; otherwise null.
- `moved` is found minus source; `off` is found minus target (source for hide/revert).
  Both have `{dx:null,dy:null}` when no trustworthy location exists.
- The 64px-padded source/destination regions are added to expected regions for
  move/hide/revert. This **does not** turn an unknown/not_done verdict into done.
  Side effects outside expected areas still affect the existing visual status.
- Approve preserves request verdicts, crop metadata and existing shift hints;
  approving a visual box never marks a failed request done. Accept retains preset
  metadata and rewrites the report as schema version 1, status `pass`, all-zero
  summary, `boxes: []`, and `note: "baseline_accepted"`. Request fields are absent.
  Both `images.before` and `images.after` are `baseline.png`; `images.diff` is null.
  Accept clears diff.png, crop contents and approvals, and refreshes `meta.created_at`
  while preserving the viewport/preset. Compare can then regenerate normal diffs.

### Crops and shifts

First 8 diff boxes: `crops/box-<id>-before.png`, `box-<id>-after.png`.
Every non-comment request: `crops/req-PT-<n>-before.png`, `req-PT-<n>-after.png`.
Before uses the baseline area; request-after uses found, otherwise to, otherwise
from (hide/revert). Each area is padded 16 px then clipped to its own image.
Longest saved side <=640; `scale=min(1,640/max(padded_w,padded_h))`; `size` records
the exact rounded output dimensions. Paths are relative to the case directory.
All stale crop files are cleared on every successful compare. Unsafe links, hard links,
redirected directories and nested directories are refused rather than traversed.

Up to 8 unapproved unexpected boxes <=400x200 can receive `shift:{dx,dy}` after a
unique match in a +/-128px neighborhood. Offset (0,0), flat/repeated templates,
low scores and size mismatches produce no hint. A shift describes movement of
the baseline **box crop**, not a detected DOM element; it is not a request verdict.

The Hermes adapter enables crops and shifts on every compare. Standalone legacy
`compare` calls omit new optional fields; `requests` enables request crops, while
`focus=True` and `shift_hints=True` opt into the respective extras independently.
CLI `--requests` enables all extras. Existing CLI codes remain 0/1/2/3 based on
visual pass/check/fail/error, regardless of request verdicts.

Matching has cooperative per-compare deadlines: 1.2s for the complete request
batch, 0.5s for optional shift hints, leaving headroom toward the 2s extra-work
budget. Unfinished request searches return unknown (including hide; a timeout
never proves absence), and unfinished shifts are omitted. This is a wall-clock
guard checked between bounded work chunks, not a hard real-time guarantee on
arbitrary hardware. Positive verdicts still require completed pixel checks.

## Compact tool results

`success: true` means the tool ran without error; it does not mean visual pass
or completed requests. Without requests, existing messages stay unchanged.
With nonempty requests and `requests_ok: true`, append ` | Requests: ` and
nonzero `N done, N not_done, N unknown, N skipped` counts in that order.
With `requests_ok: false`, use `Requests incomplete (N not_done, N unknown) | `
before the visual text, omitting zero counts. Existing hints remain independent.
The same rules apply to a report's optional `message` when present.

Success retains existing engine field names and adds:
`success`, `target`, `message`, `changed_percent`, boxes' `bbox`/`kind`,
`boxes_omitted`, `paths:{baseline,after,diff,report}`,
`viewport:{width,height,dpr:1,preset?}`, `hint`, optional `request_results`,
`requests_ok`, `request_counts`, and **one** `crops_dir` absolute path. Full input
`requests` and the detailed `crops` object are not echoed in tool output.
`paths.report` is the absolute report.json path when the file exists; otherwise
null, including immediately after a fresh baseline. Compare, approve and accept
return that path. `paths.html` is optional and appears only when HTML was written.

```json
{
  "success":true,"status":"pass","name":"login","target":"login",
  "message":"Requests incomplete (1 not_done) | No unexpected changes","changed_percent":0,
  "summary":{"changed_px":0,"changed_percent":0,"box_count":0,"unexpected_count":0},
  "schema_version":1,"size":{"width":390,"height":844},
  "images":{"before":"baseline.png","after":"current.png","diff":"diff.png"},
  "boxes":[],"boxes_omitted":0,"ignore_regions":[],
  "meta":{"browser":"/path/to/browser","os":"Windows","viewport":{"width":390,"height":844,"preset":"mobile"},"created_at":"2026-11-06T19:00:00+07:00","tolerance":0},
  "paths":{"baseline":"/home/.hermes/orphic-eyes/login/baseline.png","after":"/home/.hermes/orphic-eyes/login/current.png","diff":"/home/.hermes/orphic-eyes/login/diff.png","report":"/home/.hermes/orphic-eyes/login/report.json"},
  "viewport":{"width":390,"height":844,"dpr":1,"preset":"mobile"},
  "crops_dir":"/home/.hermes/orphic-eyes/login/crops",
  "request_results":[{"id":"PT-1","status":"not_done","found":{"x":104,"y":180,"w":190,"h":48},"moved":{"dx":0,"dy":0},"off":{"dx":30,"dy":0},"match":1.0,"why":"Found outside target tolerance"}],
  "requests_ok":false,"request_counts":{"done":0,"not_done":1,"unknown":0,"skipped":0},
  "hint":"Check PT-1; fix or clarify these intents, then call orphic_compare again."
}
```

Serialized ASCII JSON is strictly **<4000 UTF-8 bytes**, never Base64 or image
contents. Initially include <=20 boxes. If over budget: clear `why` to empty
strings, omit `found` keys, then drop boxes from the end and increment
`boxes_omitted`; existing ignore-region omission is the last fallback. Every
request id/status remains. Full report data is never shortened. An unusually
long storage path can exceed the metadata budget and returns an actionable error
instead of silently discarding request identities.

All failures: `{"success":false,"error":"...","fix":"..."}` (no raising/printing).
Engine/CLI internal errors retain their existing `status:"error"` contract.

## Optional HTML embedding foundation

`engine.report_html.write_report_html(case_dir, template_path=None)` writes
`report.html` beside report.json and returns its absolute Path. A template must
contain exactly one `<!--ORPHIC_REPORT_JSON-->`; it becomes
`<script type="application/json" id="orphic-report">...</script>` containing
the report data. Image and crop paths remain relative to the case directory,
allowing a future file:// page to read embedded data without fetching JSON.

Embedding escapes `</` as `<\/`, U+2028/U+2029 as JSON Unicode escapes,
and `<!--` as `\u003c!--`. The requested spelling `<\!--` uses an invalid JSON
escape (`\!`); encoding the less-than character gives safe, valid JSON with
identical parsed strings. Names and why fields round-trip without data changes.
Only static template content surrounds the data; no UI is generated here.

Without an explicit template, only `engine/templates/report.html` is considered.
If absent, return None without writing anything. No default template is shipped.
Every report.json write refreshes the optional page, including compare, approve,
accept, and direct `write_report` calls. Ignore add/remove refresh the page from
the existing report, if present; they retain the existing requirement to compare
again to recalculate metrics and boxes. Operations return `paths.html` only when
a page was written. The HTML's embedded JSON equals report.json exactly; HTML
paths are returned separately and never added to the persisted report schema.
Replacing a baseline or deleting its report also removes report.html. Accept
removes the previous page when it replaces the baseline, then generates a new
page from the accepted report if a template exists.

## Viewport state

Explicit baseline preset: desktop=1280x720, mobile=390x844, tablet=768x1024.
Passing preset with width or height is an error. `plugin-state.json` stores
`url`, optional `latest_url` and `viewport_preset`; preset is mirrored into
metadata `viewport.preset`, retained through compare/approve/accept and returned
in tool `viewport.preset`. Legacy calls without preset retain their original
field shape, even when their default size equals desktop. There is no automatic
inference of a preset for custom sizes. After capture, the plugin checks actual
PNG dimensions; it never rescales a screenshot to pretend a viewport worked.
