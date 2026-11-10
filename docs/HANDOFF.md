# HANDOFF

## Current task: Copy target picker

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
