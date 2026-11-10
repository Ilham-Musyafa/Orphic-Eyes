# HANDOFF

## Current task: Add action

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
