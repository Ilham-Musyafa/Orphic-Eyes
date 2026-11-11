# Submission night — Ilham's checklist

These are **owner actions to do later**, not actions Codex has performed. No PR, visibility change, X post or form submission has been made. Use PowerShell. Keep the same window for the commands below; do not paste secrets or .env contents into chat or PRs.

**Deadline supplied by Ilham:** 17:00 EST on **11 November 2026** = 22:00 UTC on 11 November = **05:00 WIB (Jakarta) on Thursday, 12 November 2026**. WIB is UTC+7; EST is UTC−5. Do not confuse it with Bangkok's date or 05:00 on November 11. Aim to finish well before 04:30 WIB. The event deadline/X/form requirements below come from the owner's brief; the organizer's live announcement must be checked before relying on them.

## 0. Finish these gates BEFORE submission night

Ask Orphic Lead to confirm a final combined release is pushed to `release/hackathon`. Claude/Lead must include the intended engine and UI, final truthful README disclosures/features, and UI screenshots. Codex must not merge or change that branch in this task. Do not pin one branch and demonstrate a different one.

Complete [WINDOWS-TEST.md](WINDOWS-TEST.md), including real Windows/browser, public capture and live Hermes checks. Codex reliability work and repeated-suite evidence for the combined code are recorded in [HANDOFF.md](HANDOFF.md) on `fix/test-reliability`. Claude/Lead must integrate the fixes and reverify the final frozen release; passing a development branch is not validation of a later pin. Matcher and capture limits were not widened. Content check is present in the merged release template; verify its behavior on the submission machine. Only keep tested platform claims.

Have Git, Hermes, your GitHub account, an X account, and a synthetic-data demo video **shorter than 90 seconds** ready. Use the [official Hermes installation instructions](https://hermes-agent.nousresearch.com/docs/getting-started/installation) if Hermes is missing. Check the actual form early; access from this environment returned HTTP 403, so its exact current field labels, sign-in requirements and confirmation screen are unverified.

**Success:** Lead says the combined release, README, assets and tests are ready; Hermes runs on the submission machine. **If not:** stop the affected gate and ask its owner in the TODO table. This checklist cannot replace missing code integration, a passing admission gate or a video.

## 1. Get the final SHA from the pushed release

Use fresh folders so you do not overwrite Claude's checkout or your test files. The prep clone supplies the draft; the separate release clone supplies the code being pinned.

```powershell
$Night = Join-Path $HOME ('orphic-submit-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $Night | Out-Null
$Prep = Join-Path $Night 'submission-docs'
$Release = Join-Path $Night 'release-check'
$Artifacts = Join-Path $Night 'artifacts'
New-Item -ItemType Directory -Path $Artifacts | Out-Null
git clone --branch docs/submit-prep --single-branch https://github.com/Ilham-Musyafa/orphic-eyes.git $Prep
if ($LASTEXITCODE -ne 0) { throw 'Prep clone failed.' }
git clone --branch release/hackathon --single-branch https://github.com/Ilham-Musyafa/orphic-eyes.git $Release
if ($LASTEXITCODE -ne 0) { throw 'Release clone failed.' }
git -C $Release fetch origin release/hackathon
if ($LASTEXITCODE -ne 0) { throw 'Release fetch failed.' }
$FinalSha = (git -C $Release rev-parse FETCH_HEAD).Trim()
if ($FinalSha -notmatch '^[0-9a-fA-F]{40}$' -or $FinalSha -eq ('0' * 40)) { throw 'Invalid release SHA.' }
if ((git -C $Release rev-parse HEAD).Trim() -ne $FinalSha) { throw 'Release moved during cloning. Ask Lead to freeze it, then start a fresh verification clone.' }
git -C $Release status --short
git -C $Release log -1 --oneline
Write-Host "FINAL SHA: $FinalSha"
git -C $Release checkout --detach $FinalSha
$Catalog = Join-Path $Artifacts 'orphic-eyes.yaml'
Copy-Item (Join-Path $Prep 'docs\catalog\orphic-eyes.yaml') $Catalog
$YamlText = [System.IO.File]::ReadAllText($Catalog)
if ($YamlText -notmatch '(?m)^sha: "0{40}"\s*$') { throw 'Draft pin differs from expected placeholder; inspect before editing.' }
$YamlText = $YamlText -replace '(?m)^sha: "0{40}"\s*$', ('sha: "' + $FinalSha + '"')
[System.IO.File]::WriteAllText($Catalog, $YamlText, [System.Text.UTF8Encoding]::new($false))
notepad $Catalog
```

In Notepad, check the full SHA, `repo`, version and six declared tools against the final release's plugin.yaml. Replace/remove only resolved draft TODO comments and the resolved “Draft pin is a placeholder” known-issue line. Keep honest unresolved limitations. After native validation passes, remove its pending-validation wording too. Keep `tier: community`. `requires_hermes` is optional and omitted because no tested minimum is established; never guess a version floor. Screenshots/gallery URLs must be public GitHub-hosted URLs, ideally pinned to the same SHA.

Keep `platforms: [linux]`. Change to `[linux, windows]` **only** after Ilham's Windows guide passes on this exact final commit; a commented TODO is not a support claim. If required Windows checks fail, retain Linux only and disclose the result.

**Success:** a clean detached release checkout, full real SHA and separately edited catalog file. **If it fails:** save the command/error and ask Lead; do not reset an existing checkout, merge, force-push or select an arbitrary commit. If the final code/README changes afterward, restart pin verification and validation. The catalog file is outside the pinned checkout; editing that proposal does not change the plugin SHA.

## 2. Make the plugin repository public — Ilham only

On GitHub open `Ilham-Musyafa/orphic-eyes` → **Settings → General → Danger Zone → Change repository visibility → Public**, then follow GitHub's confirmation prompts. Before confirming, have the owner review the repository and history for material that must not be public; never paste credentials into a PR to discuss them. [GitHub visibility instructions](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/setting-repository-visibility).

Open a private/incognito browser window **logged out of GitHub**. Open both:

- `https://github.com/Ilham-Musyafa/orphic-eyes`
- The commit page formed below.

```powershell
$CommitUrl = 'https://github.com/Ilham-Musyafa/orphic-eyes/commit/' + $FinalSha
Write-Host $CommitUrl
git ls-remote https://github.com/Ilham-Musyafa/orphic-eyes.git refs/heads/release/hackathon
```

**Success:** logged-out browser can read the repo and exact commit; ls-remote shows the frozen release SHA. **If it fails:** check visibility/URL and whether the commit was pushed. An authenticated git ls-remote succeeding alone does **not** prove public access; credential helpers/proxies can authenticate silently. Do not open the catalog PR while anonymous access fails.

## 3. Validate the EXACT pinned checkout, not the YAML file

Official command and gate: [catalog submission guide](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/developer-guide/plugins/catalog-submission.md#before-you-submit). `hermes plugins validate` takes a **plugin directory**; it does not take a catalog YAML as the plugin. The YAML's pin/capabilities are checked separately and by upstream catalog CI. There is no catalog install-deps field: dependencies belong in plugin.yaml; --install-deps is a validation CLI flag.

```powershell
$PinMatch = Select-String -Path $Catalog -Pattern '^sha: "([0-9a-fA-F]{40})"$'
if (-not $PinMatch) { throw 'Catalog sha line is missing or malformed.' }
$CatalogSha = $PinMatch.Matches[0].Groups[1].Value
if ($CatalogSha -ne $FinalSha -or $CatalogSha -eq ('0' * 40)) { throw 'Catalog does not pin the verified final commit.' }
if ((git -C $Release rev-parse HEAD).Trim() -ne $FinalSha) { throw 'Wrong checkout.' }
$ValidationLog = Join-Path $Artifacts 'hermes-validation.log'
hermes plugins validate $Release --install-deps 2>&1 | Tee-Object -FilePath $ValidationLog
$ValidationExit = $LASTEXITCODE
Write-Host "Validation exit: $ValidationExit"
if ($ValidationExit -ne 0) { throw 'Admission validation failed. Do not call this a pass or open the PR yet.' }
git -C $Release status --short
```

**Success:** exit 0, successful dependency installation, plugin load/capability/security checks. Read all warnings and report them in the PR; an existing project test pass is not a substitute. Review catalog capabilities field by field against the pinned plugin, not against another branch. See [the schema](https://github.com/NousResearch/hermes-agent/blob/main/plugin-catalog/README.md#entry-schema) and [Accessible Session List example](https://github.com/NousResearch/hermes-agent/blob/main/plugin-catalog/accessible-session-list.yaml).

**If it fails:** send Orphic Lead the failed check and redacted log tail, not secrets. Missing Hermes: use official installation docs. Dependency conflicts/scanner failures/capability mismatches require investigation; do not bypass checks or change the SHA to a commit that was not validated. Any fix to the plugin needs a new pushed final SHA and repeat validation. No native Hermes validation was possible in Codex's environment; there is no pre-existing passing log to reuse.

## 4. Fork Hermes, copy ONE catalog file, and open the PR — Ilham only

1. While logged in, open [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) and click **Fork**. Select your account. If you already have a fork, use **Sync fork** to bring its default branch current; resolve problems before continuing.
2. In the same PowerShell window:

```powershell
$GitHubUser = Read-Host 'Your GitHub username (not a password or token)'
$Fork = Join-Path $Night 'hermes-agent-fork'
git clone --branch main --single-branch "https://github.com/$GitHubUser/hermes-agent.git" $Fork
if ($LASTEXITCODE -ne 0) { throw 'Fork clone failed.' }
$ProposalBranch = 'catalog/orphic-eyes-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
git -C $Fork switch -c $ProposalBranch
$Destination = Join-Path $Fork 'plugin-catalog\orphic-eyes.yaml'
if (Test-Path $Destination) { throw 'An entry already exists. Ask Lead whether this should be an update instead of overwriting it.' }
Copy-Item $Catalog $Destination
git -C $Fork diff --check
git -C $Fork add -- plugin-catalog/orphic-eyes.yaml
git -C $Fork diff --cached --stat
git -C $Fork diff --cached -- plugin-catalog/orphic-eyes.yaml
```

3. Confirm the staged change is exactly one catalog entry, with a nonzero 40-character pin, honest platforms and metadata. Then:

```powershell
git -C $Fork commit -m 'catalog: add Orphic Eyes'
if ($LASTEXITCODE -ne 0) { throw 'Commit failed.' }
git -C $Fork push -u origin $ProposalBranch
if ($LASTEXITCODE -ne 0) { throw 'Fork branch push failed.' }
```

4. On GitHub click **Compare & pull request**, or upstream **Pull requests → New pull request → compare across forks**. Choose **base repository NousResearch/hermes-agent**, **base main**, **head your fork**, and the proposal branch printed by Git. Confirm the diff still contains only `plugin-catalog/orphic-eyes.yaml`.
5. Title: **catalog: add Orphic Eyes**. Paste the PR draft below after filling every evidence placeholder. Attach synthetic-data UI screenshots and the native validation log/summary. Click **Create pull request** yourself. Save its URL in PowerShell:

```powershell
$PrUrl = Read-Host 'Paste the created NousResearch/hermes-agent PR URL'
if ($PrUrl -notmatch '^https://github\.com/NousResearch/hermes-agent/pull/[0-9]+/?$') { throw 'Use the actual upstream PR URL, not a compare/fork/commit URL.' }
```

**Success:** the open PR is under NousResearch/hermes-agent, pins the validated public commit, and contains disclosures. Watch catalog CI; it must turn green. A PR being open is not admission or maintainer approval. **If it fails:** read the CI logs and ask Lead. A plugin-code fix means a new pin and fresh native validation; a catalog-only correction can update this fork branch. Do not merge the upstream PR yourself or force-push protected branches. Follow the organizer's rule for an open PR by the deadline; do not claim an unmerged PR is accepted.

### Ready-to-paste PR description

Replace the TODO evidence fields and remove any unverified feature claims before posting. Do not assert success without the real log. This draft matches the current README; recheck it against the final pinned release.

```markdown
## Orphic Eyes

Orphic Eyes is an independent, pixel-only visual review plugin by Ilham Musyafa. It compares Before/After screenshots, identifies changed zones, prepares precise coding-agent requests, and supports bounded follow-up review rounds. The engine returns prompts; Hermes or the user performs authorized edits. It does not read page source, DOM contents or text with OCR. Browser rendering controls are used for screenshots.

Hermes surfaces: six tools in toolset `orphic`: `orphic_baseline`, `orphic_compare`, `orphic_loop_step`, `orphic_approve`, `orphic_accept`, `orphic_ignore`; `/orphic help`, `/orphic doctor`, `/orphic demo`. No hooks or middleware, no Desktop SDK extension, and no custom top-level Hermes CLI command are registered. The standalone engine provides its own capture/serve/loop CLI.

### Pin and evidence
- Public repository: https://github.com/Ilham-Musyafa/orphic-eyes
- Exact catalog SHA: TODO paste the final validated 40-character SHA.
- Version/capabilities: TODO confirm against plugin.yaml at that SHA.
- Native admission validation: TODO paste the successful `hermes plugins validate PATH --install-deps` exit/result and warnings; attach the log.
- Tested platforms/browser versions and current test results: TODO supply actual evidence; do not claim three green runs, Windows, a live Hermes host or public capture unless verified.
- UI screenshots from this exact release: TODO attach synthetic-data screenshots; confirm which Verify/Content check features actually ship.
- Demo: TODO add the X post URL after posting; no video claim yet.

### Runtime and privacy disclosures
- Review/report processing and artifacts are local: screenshots, reports, requests, approvals and loop history are stored in the resolved Hermes home's `orphic-eyes/` directory or the caller's chosen store. Captured content can be sensitive. Explicit input images/pages, runtime packages, browser executables and system fonts may be read outside that store; doctor probes storage write access.
- The report UI has no automatic external service/upload/telemetry client. Its CSS, JavaScript and fonts are embedded. HTTP-served reports request their HTML/PNGs from the local server; selected images are read locally. Copy Prompt writes to the clipboard only on request and sends nothing automatically. Generated reports keep PNGs/crops adjacent to HTML.
- User-requested URL capture launches a locally installed headless Edge/Chrome/Chromium. Supplied pages can follow redirects, load third-party resources or make their own network requests. There is no Orphic-hosted screenshot/model service. This is not a promise of zero browser network traffic. The guarded HTTP/HTTPS path blocks private destinations unless explicitly allowed; file/javascript/data input URLs remain forbidden there. Legacy local baselines separately allow local file pages.
- Browser processes use argument lists without a shell. Profiles use short system-temp paths outside the report store; URL capture also uses a temporary loopback guard proxy. Cleanup stops the owned browser tree with bounded waits before removing profiles; persistent cleanup errors remain capture failures and may leave artifacts. An optional read-only 127.0.0.1 report server remains running until Ctrl+C or timeout. Disclose the actual final-pin results and any failures; do not substitute earlier branch evidence.
- No credential-store or .env files are read and no model key is required. Existing proxy/CA settings are inherited. New URL capture/loop metadata does not persist source URLs; legacy baseline state may store URLs. Pages may create temporary cookies. Avoid credential-bearing URLs.
- No plugin telemetry or usage reporting is implemented. Browser/page behavior and network resources loaded by captured pages are outside that claim. There is no self-updater or bundled browser binary, and prompts are returned rather than executed.

### Authorship, assets and limits
Built by Ilham Musyafa with Claude Code, OpenAI Codex and Cursor. Code is Apache-2.0. Embedded Montserrat and JetBrains Mono fonts use SIL OFL 1.1 (licenses included). Lumen/sample mockup images were created for this project; they are synthetic, not customer screenshots. Orphic Eyes is not affiliated with or endorsed by Nous Research.

Pixels do not prove semantic identity, text meaning, DOM removal or code correctness. Matching is grayscale/local/bounded; repeated content, expected-region padding, animations, login walls, cookie banners, fonts and dynamic content can produce uncertain results. Add instructions are not an engine request type. Omitted loop requests mean restoration to the original reference; explicit supported requests are fixed for the session. Stop on done/max_rounds/needs_human. README contains the corresponding disclosures and limitations.
```

## 5. Post the short video on X — Ilham only

Upload the prepared **under-90-second** video as a public post. Show the same release/pin as the PR. Use only synthetic pages; keep keys, private URLs, usernames and sensitive screenshots out of the recording. Check the uploaded video actually plays for a logged-out viewer.

Ready-to-paste post text (replace the TODO before posting):

> Orphic Eyes gives Hermes a pixel-only visual review loop: compare screenshots, point at an area, copy a precise request, then review the next round. Built for the Hermes Agent Plugin Hackathon. @NousResearch
> Catalog PR: TODO paste the actual PR URL. Demo attached (under 90 seconds).

After clicking Post, use **Share → Copy link** on the post:

```powershell
$XUrl = Read-Host 'Paste the public X post URL containing the video'
if ($XUrl -notmatch '^https://(www\.)?(x\.com|twitter\.com)/[^/]+/status/[0-9]+') { throw 'Use the public post URL, not a video file or profile URL.' }
```

Edit the GitHub PR description to add this X link under Demo. This does not change the pinned code. Do not change the release merely to add a README video link after freezing the SHA; a later README change would require a new reviewed pin/validation if included in the submission snapshot.

**Success:** public playable post, duration below 90 seconds, `@NousResearch` mention, copied post URL. **If it fails:** fix upload/privacy/duration before submitting the form; an unposted local video file is not the required X link.

## 6. Submit BOTH links through Typeform — Ilham only

Open [the supplied submission form](https://form.typeform.com/to/FwJLvOln). This task could not inspect live labels (HTTP 403); exact current field names/order are **TODO to confirm manually**. Use the field's purpose, not a guessed question number:

| Form field purpose | Paste | Do not paste |
| --- | --- | --- |
| GitHub/catalog pull request | `$PrUrl`: `https://github.com/NousResearch/hermes-agent/pull/NUMBER` | Plugin repo, fork, branch, commit or compare URL |
| Demo video / X post | `$XUrl`: the public X status URL containing the under-90s video and tag | Profile URL, local video path or PR URL |

If there is one combined link field, enter both on separate labeled lines. If the form asks for another kind of URL, answer that field separately. If wording is ambiguous, pause and ask Orphic Lead/the organizer; do not silently swap the links. Fill required identity/contact fields yourself; never send passwords/tokens. Review all answers and click the final Submit button.

```powershell
Write-Host "Catalog PR: $PrUrl"
Write-Host "Demo X post: $XUrl"
```

**Success:** form shows its actual submission confirmation. Save a screenshot/receipt and submission time privately. **If it fails:** retain both URLs, retry within the deadline, and contact the organizer if blocked. A filled but unsubmitted form is not a submission. No specific confirmation wording or resubmission behavior is claimed here because it was not accessible.

## 7. Final check BEFORE 05:00 WIB, Thursday 12 November 2026

- [ ] Official organizer deadline/time zone checked; all actions complete before **05:00 WIB**, preferably before 04:30.
- [ ] Repo and pinned commit visible while logged out.
- [ ] YAML pins that exact nonzero 40-character SHA; platform/version/capability claims are truthful.
- [ ] Native validation passed on that exact checkout; warnings reviewed and logged.
- [ ] Upstream catalog PR URL saved; PR disclosures/README agree; UI screenshots attached; CI checked.
- [ ] Public X post plays the under-90s video and tags @NousResearch.
- [ ] PR URL and X post URL placed in their corresponding form fields; final confirmation saved.
- [ ] No code or README changed after the SHA was frozen without repinning and revalidating.

Keep this folder's evidence and send Orphic Lead only the two public links, final SHA, validation summary and submission confirmation—not credentials.

## Sources and field audit

Current official [catalog schema](https://github.com/NousResearch/hermes-agent/blob/main/plugin-catalog/README.md#entry-schema), [admission rules](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/developer-guide/plugins/catalog-submission.md), [Accessible Session List entry](https://github.com/NousResearch/hermes-agent/blob/main/plugin-catalog/accessible-session-list.yaml), and [CLI parser](https://github.com/NousResearch/hermes-agent/blob/main/hermes_cli/subcommands/plugins.py).

| Draft field | Official format / comparison with example |
| --- | --- |
| name, repo, sha | Required catalog identity, HTTPS repo and full 40-hex pin; same keys as example. Draft zero string intentionally remains unusable. |
| description, maintainer | Same keys; folded description includes behavior disclosures like the example. |
| tier, category | Supported enums; community/tools for this plugin, not the example's desktop category. |
| title, version, docs_url, readme | Supported optional metadata; quoted version matches current manifest, recheck final release. |
| platforms | Supported list; Linux only. Windows is a commented conditional TODO, never silently enabled. Empty would advertise all platforms. |
| known_issues | Supported string list; preserve actual limits and remove only resolved draft-state lines. |
| capabilities | Same four lists: provides_tools, provides_hooks, provides_middleware, requires_env; current six tools match plugin.yaml. Recheck final pin. |
| requires_hermes | Optional; example declares its own floor, ours omits it because no minimum has been verified. If needed, establish it and match plugin.yaml. |
| subdir, image, screenshots, onboarding | Optional and omitted; plugin is at repo root. Gallery screenshots can be added later with verified public GitHub-hosted URLs. |

The README's cleanup statement was minimally qualified to reflect its error paths; the remaining disclosures already agree with the inspected engine. “Local processing” is not rewritten as “no network whatsoever”: browser resources/redirects, loopback HTTP traffic and inherited proxy settings are explicitly disclosed. Final-release README/UI contents, native validation, repo visibility, event deadline and live Typeform/X submission must still be verified by their owners.

## Every remaining TODO / gate

This inventory includes README placeholders, YAML comments/known-issue conditions and this checklist's external/manual gates. “Blocking” means required before a truthful submission; optional polish is marked no. No TODO is satisfied merely by this document being written.

| Item | Owner | Blocking |
| --- | --- | --- |
| Confirm organizer's Nov 11 17:00 EST deadline, X tagging and form requirements | Ilham | Yes |
| Final approved engine/UI integration on release/hackathon; final branch pushed and frozen | Claude | Yes |
| Confirm Content check exists in final code or remove its advertised claim | Claude | Yes |
| Final README branch-status/feature accuracy and disclosure review before freezing | Claude | Yes |
| Resolve/investigate existing matcher, browser timeout/cleanup issues; achieve truthful release test evidence | Codex | Done on fix/test-reliability: three full runs each 189 passed, zero failures/errors/skips; native-unusable check 167 passed/22 clearly skipped. Full evidence in HANDOFF.md. Claude/Ilham must integrate and retest the frozen release. Historical trace limitations are explicit, not claimed solved by widening limits. |
| Complete WINDOWS-TEST.md: Windows/browser/public-site/live Hermes results | Ilham | Yes for those claims; keep Windows out of platforms until passed |
| Final version and six-tool capability audit at the selected pin | Codex | Done for the combined tested branch: orphic-eyes 0.3.0, six schema/handler/README/catalog tool sets agree (HANDOFF.md). Final submission SHA is still unselected; recheck that exact frozen pin after integration. |
| Establish minimum Hermes version if required; otherwise leave optional requires_hermes absent | Codex | No, unless final API usage needs a floor |
| Select real final SHA and replace YAML's 40 zeros; remove resolved draft-state notes | Ilham | Yes |
| Make repo public and verify exact commit anonymously | Ilham | Yes |
| Run native hermes plugins validate PATH --install-deps successfully; retain log/warnings | Ilham | Yes |
| Windows platforms comment: enable only with passing exact-pin Windows evidence | Ilham | No if Linux-only; yes before advertising Windows |
| Capture final-release synthetic UI screenshots for reviewer; no stale release screenshots | Claude | Yes for upstream UI review request |
| Optional catalog screenshots/gallery URLs, pinned to final SHA | Ilham | No; review screenshots can be PR attachments |
| README screenshots TODO replaced with truthful final screenshots | Claude | No separate hard gate if PR review images supplied; recommended before freeze |
| Record/export demo under 90s, then public X post with @NousResearch | Ilham | Yes |
| README demo-link TODO (may remain pending in frozen README until X post exists) | Ilham | No; public X link itself is mandatory |
| Fill PR draft SHA/version/results/screenshots placeholders; copy all disclosures and open upstream PR | Ilham | Yes |
| Remove pending validation wording only after a real pass; do not conceal remaining limitations | Ilham | Yes |
| Fill X-post PR URL placeholder; add actual X URL to PR Demo field | Ilham | Yes |
| Confirm live Typeform labels and insert the PR and X URLs correctly | Ilham | Yes |
| Submit Typeform, save its actual confirmation/time before deadline | Ilham | Yes |
