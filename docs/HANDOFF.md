# HANDOFF

## Current task: Micro-animations

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
