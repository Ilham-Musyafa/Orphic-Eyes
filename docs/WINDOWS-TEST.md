# Windows 11 test guide — Orphic Eyes

For Ilham: use **PowerShell**, not Command Prompt, Git Bash or a Python prompt. Paste one block at a time. No Administrator window is needed for these project tests. Keep the same PowerShell window through steps 1–7 so its variables remain available. Never paste passwords, tokens, cookies, .env contents or your whole environment into a report.

This tests `docs/windows-test`, based on `docs/readme` and `feat/auto-loop`. It does **not** contain all UI changes from `release/hackathon`. Windows, Edge, Chrome, public-site capture and a live Hermes host are tests to perform here, not previously proven compatibility claims. Do not switch to or modify release/hackathon. Request an approved final combined commit from Orphic Lead before the final UI/submission gate.

## 1. Get a fresh checkout and virtual environment

```powershell
git --version
py -3 --version
$Repo = Join-Path $HOME 'Orphic-Eyes-Windows'
if (Test-Path $Repo) { throw 'This folder already exists. Preserve it and choose a different fresh folder name in $Repo.' }
git clone --branch docs/windows-test --single-branch https://github.com/Ilham-Musyafa/Orphic-Eyes.git $Repo
if ($LASTEXITCODE -ne 0) { throw 'Clone failed; stop here.' }
Set-Location $Repo
git branch --show-current
git rev-parse HEAD
py -3 -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed.' }
$Python = Join-Path $Repo '.venv\Scripts\python.exe'
& $Python --version
$Work = Join-Path $HOME ('orphic-test-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
$Store = Join-Path $Work 'store'
$Site = Join-Path $Work 'pages'
New-Item -ItemType Directory -Path $Store, $Site | Out-Null
Write-Host "Repository: $Repo"
Write-Host "Test files and logs: $Work"
```

**What you should see:** Git works, Python is **3.12 or newer**, branch is docs/windows-test, a full commit SHA and a fresh test folder. Explicitly invoking `$Python` avoids PowerShell activation/execution-policy problems.

**If it fails, paste this output:** the failed command/error, `git --version`, `py -3 --version`. If Git is missing use [Git for Windows](https://git-scm.com/download/win); if Python is missing/too old use [official Python Windows downloads](https://www.python.org/downloads/windows/). If only the `py` launcher is missing but `python --version` shows 3.12+, use `python -m venv .venv` instead of the `py` venv command. Stop if the interpreter is older. Do not delete an existing checkout or change execution policy to fix this guide.

## 2. Install the declared dependencies

```powershell
& $Python -m pip install -r requirements.txt 2>&1 | Tee-Object -FilePath (Join-Path $Work 'install.log')
$InstallExit = $LASTEXITCODE
& $Python -m pip check
Write-Host "Install exit: $InstallExit"
```

**What you should see:** Pillow installs or is already satisfied, install exit 0, and `No broken requirements found`. No new project dependency is needed.

**If it fails, paste this output:**

```powershell
& $Python --version
Get-Content (Join-Path $Work 'install.log') -Tail 60
```

Do not disable certificate verification. Remove any credential-bearing proxy/index URL from logs before sharing.

## 3. Run all tests three times

Close CPU-heavy work first. Do not run captures/demos alongside the suite. Keep browsers installed; intentionally making them unavailable would skip the checks you need.

```powershell
Set-Location $Repo
$TestResults = @()
foreach ($Run in 1..3) {
    $Log = Join-Path $Work "tests-$Run.log"
    & $Python -B -m unittest discover -v 2>&1 | Tee-Object -FilePath $Log
    $Code = $LASTEXITCODE
    $TestResults += "Run $Run exit $Code"
}
$TestResults
$TestResults | Set-Content -Path (Join-Path $Work 'test-exits.txt')
```

**What you should see:** all three exits 0 and each run ends `OK` (the current source has 182 tests when all browser tests execute). A skipped class can change the displayed count. Browser-dependent classes in test_browser, test_plugin, test_roundtrip, test_url_capture, test_url_plugin, test_loop_plugin and test_serve_cli skip when no browser is detected. Directory-link checks may also skip if Windows denies symlink creation. Record skips; a skipped browser check is **not** a Windows/browser pass. A browser that is found but cannot launch should produce a failure/error to investigate.

**If it fails, paste this output:**

```powershell
$TestResults
Get-Content (Join-Path $Work 'tests-1.log') -Tail 70
Get-Content (Join-Path $Work 'tests-2.log') -Tail 70
Get-Content (Join-Path $Work 'tests-3.log') -Tail 70
```

Keep all failures and timeouts. Do not edit assertions, search budgets or timeout values. For comparison, rerun a previously intermittent check alone:

```powershell
& $Python -B -m unittest tests.test_serve.ReportServerTests.test_registry_discovery_across_processes_and_stale_cleanup -v
& $Python -B -m unittest tests.test_url_capture.URLBrowserTests.test_default_viewport_repeated_pixels_and_motion_disabled -v
```

A focused pass after a full-run timeout is useful evidence, but does not make the failed full run green.

## 4. Doctor and browser selection

The repository command below works without Hermes; `/orphic doctor` is a Hermes chat command, not a PowerShell command.

```powershell
& $Python -B -c "import commands; print(commands.doctor())" 2>&1 | Tee-Object -FilePath (Join-Path $Work 'doctor.log')
```

**What you should see:** checks for Python, Pillow, writable data storage, engine imports and detected browser path/version. The existing auto-detection checks common Windows Edge paths before Chrome. Record the actual path; do not assume both browsers were tested.

**If it fails, paste this output:** doctor.log and the Python version. Install/update Chrome or Edge through its official installer if missing. For the **new URL capture/loop API only**, you may select an existing executable explicitly:

```powershell
$Candidates = @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
    "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe"
)
$Candidates | ForEach-Object { if (Test-Path $_) { Write-Host $_ } }
```

Set `$env:ORPHIC_BROWSER` to one of the real printed paths before step 5 if needed. Example, **only if that path exists**:

```powershell
$env:ORPHIC_BROWSER = "$env:ProgramFiles\Google\Chrome\Application\chrome.exe"
```

This does not override every legacy browser test or the legacy doctor detector. Record the selected URL-capture browser separately. Never add `--no-sandbox` or ignore TLS errors to obtain a pass.

## 5. Capture two PUBLIC URLs

These example domains are stable public test pages; they may look identical. Zero changed zones is a valid result, not a failure of the comparison.

```powershell
$PublicName = 'public-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
$PublicOutput = & $Python -B -m engine.cli capture-pair https://example.com https://example.org --store $Store --name $PublicName 2> (Join-Path $Work 'public-error.log')
$PublicExit = $LASTEXITCODE
$PublicOutput | Set-Content -Path (Join-Path $Work 'public-result.json')
Write-Host "Public capture exit: $PublicExit"
$PublicOutput
if ($PublicExit -notin @(0, 1, 2)) { throw 'Public capture failed. Save the error below before continuing.' }
$Public = $PublicOutput | ConvertFrom-Json
$Public.paths
```

**What you should see:** PNG/report paths and pass/check/fail status. Exit 0/1/2 means the comparison ran; exit 3 is an error. Do not use `--allow-local` for these public sites. Two URLs can redirect or load resources; DNS/proxy restrictions, banners and headless blocking can affect capture. Record actual results rather than claiming public compatibility from a local test.

**If it fails, paste this output:**

```powershell
Write-Host "Exit: $PublicExit"
Get-Content (Join-Path $Work 'public-error.log') -Tail 60
& $Python -B -c "from engine.url_capture import validate_url; print(validate_url('https://example.com')); print(validate_url('https://example.org'))"
```

Do not loosen private-network or TLS rules. If this fails, mark public capture failed and continue with the trusted local tests, using a fresh target name.

## 6. Serve and open the HTTP report

If public capture succeeded, start its server in the background for 15 minutes. Keep the test window open. This is the actual CLI; the output URL is written to a log, not guessed from a port number.

```powershell
$ServeOut = Join-Path $Work 'report-server.stdout.log'
$ServeErr = Join-Path $Work 'report-server.stderr.log'
$ServeArgs = "-B -m engine.cli serve --store `"$Store`" --timeout 900"
$ReportServer = Start-Process -FilePath $Python -ArgumentList $ServeArgs -PassThru -RedirectStandardOutput $ServeOut -RedirectStandardError $ServeErr
for ($Try = 0; $Try -lt 30; $Try++) {
    if ((Test-Path $ServeOut) -and ((Get-Item $ServeOut).Length -gt 0)) { break }
    Start-Sleep -Milliseconds 500
}
$ReportUrl = (Get-Content $ServeOut -First 1).Trim()
Write-Host $ReportUrl
Start-Process $ReportUrl
```

**What you should see:** `http://127.0.0.1:PORT/.../report.html`, a readable report and its Before/After PNGs. It must be HTTP, not file://. If no report exists yet (public capture failed), create the local pair in step 7 first, then run this block. The existing server can serve future rounds; do not start a second server for the same store while it is alive.

For a simple foreground alternative, run this command, open the printed URL manually, and press Ctrl+C before returning to PowerShell:

```powershell
& $Python -B -m engine.cli serve --store $Store --timeout 900
```

Use **one** server method, not both. After background timeout, rerun the server block for a fresh URL. Do not kill unrelated Python/browser processes.

**UI checks:** this branch does not include all release UI. If Verify exists, create a supported Move request, apply the corresponding page change, upload the next screenshot and check that per-area results/crops appear without a pixel-read/security error. Test Content check only if an approved combined release actually provides it. If either control is absent, record **BLOCKED — UI not present at tested SHA**, not pass. Content check was not found at the previously inspected release commit. Ask Orphic Lead for the final combined release; do not modify report.html or switch release/hackathon to make the check pass.

**If it fails, paste this output:**

```powershell
Get-Content $ServeOut -Tail 10
Get-Content $ServeErr -Tail 60
Get-ChildItem $Store -Recurse -Filter report.html | Select-Object FullName
```

Also paste the visible browser error and tested Git SHA. Do not paste captured private content.

## 7. Local two-round loop with exact test pages

The generated files below live outside the repository. The intended fix is to make the blue rectangle red, matching the reference. No text recognition or semantic inference is needed.

```powershell
$ReferenceHtml = @'
<!doctype html><meta charset="utf-8"><title>Orphic reference</title>
<style>body{margin:0;background:white}.box{position:absolute;left:40px;top:70px;width:48px;height:32px;background:red}</style><div class="box"></div>
'@
$CurrentHtml = $ReferenceHtml.Replace('background:red','background:blue')
Set-Content -Path (Join-Path $Site 'reference.html') -Value $ReferenceHtml -Encoding UTF8
Set-Content -Path (Join-Path $Site 'current.html') -Value $CurrentHtml -Encoding UTF8
$SiteOut = Join-Path $Work 'site.stdout.log'
$SiteErr = Join-Path $Work 'site.stderr.log'
$SiteArgs = "-m http.server 8765 --bind 127.0.0.1 --directory `"$Site`""
$SiteServer = Start-Process -FilePath $Python -ArgumentList $SiteArgs -PassThru -RedirectStandardOutput $SiteOut -RedirectStandardError $SiteErr
Start-Sleep -Seconds 1
(Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8765/current.html).StatusCode
$LoopName = 'loop-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
& $Python -B -m engine.cli capture-pair http://127.0.0.1:8765/reference.html http://127.0.0.1:8765/current.html --store $Store --name $LoopName --width 400 --height 300 --allow-local
$PairExit = $LASTEXITCODE
Write-Host "Initial pair exit: $PairExit"
if ($PairExit -notin @(0, 1, 2)) { throw 'Local pair failed. Stop and save its error.' }
$Round1Text = & $Python -B -m engine.cli loop-step $LoopName http://127.0.0.1:8765/current.html --store $Store --allow-local --max-rounds 3
$Round1Text | Set-Content -Path (Join-Path $Work 'round1.json')
$Round1 = $Round1Text | ConvertFrom-Json
$Round1 | Select-Object success, round, stop_condition, failing_count, unexpected_count, report_url
$Round1.follow_up_prompt
```

**What you should see:** HTTP 200, initial pair normally check/exit 1, round 1 `success:true`, `continue`, one failing area and a nonempty follow-up prompt. Visual status may be pass because the wrong page did not change; the authoritative loop result is stop_condition. Missing report_url means the report server is not running; use serve_hint/step 6.

Now fix the generated page and recapture at the **same URL/name**:

```powershell
Set-Content -Path (Join-Path $Site 'current.html') -Value $ReferenceHtml -Encoding UTF8
$Round2Text = & $Python -B -m engine.cli loop-step $LoopName http://127.0.0.1:8765/current.html --store $Store --allow-local
$Round2Text | Set-Content -Path (Join-Path $Work 'round2.json')
$Round2 = $Round2Text | ConvertFrom-Json
$Round2 | Select-Object success, round, stop_condition, should_stop, failing_count, unexpected_count, report_url
if ($Round2.report_url) { Start-Process $Round2.report_url }
```

**What you should see:** round 2, done, should_stop true, zero failing and unexpected zones. Both rounds' files remain under `$Store\$LoopName\loop`. Without requests this mode means restoration to the original reference, not an arbitrary redesign. Stop on done/max_rounds/needs_human or an error. Use a fresh name to start another session.

**If it fails, paste this output:**

```powershell
Get-Content (Join-Path $Work 'round1.json')
Get-Content (Join-Path $Work 'round2.json')
Get-Content $SiteErr -Tail 40
& $Python -B -c "import commands; print(commands.doctor())"
```

If port 8765 is already occupied, do not stop the unknown process. Choose another unused port and change every 8765 in this step consistently. For cleanup, stop only the page-server process you started; the report server expires cleanly after its timeout:

```powershell
if ($SiteServer -and -not $SiteServer.HasExited) { Stop-Process -Id $SiteServer.Id }
```

## 8. Install Hermes and validate the LOCAL plugin

Engine testing above needs no Hermes. For the host test, use the official [installation guide](https://hermes-agent.nousresearch.com/docs/getting-started/installation) and [upstream README Windows instructions](https://github.com/NousResearch/hermes-agent#quick-install). The current upstream README explicitly offers this native PowerShell command; review the linked source before running it:

```powershell
iex (irm https://hermes-agent.nousresearch.com/install.ps1)
```

**What you should see:** the official installer completes. Follow its prompts. Reopen PowerShell afterward if `hermes` is not found; no shell activation or antivirus bypass is prescribed here. Do not paste account keys or authentication output. Upstream native Windows support is not proof that Orphic Eyes works with it.

In the new PowerShell window, initialize the repository variable again. If you chose a different folder in step 1, use that folder:

```powershell
$Repo = Join-Path $HOME 'Orphic-Eyes-Windows'
Set-Location $Repo
Get-Command hermes | Select-Object Name, Source
hermes plugins --help
$Commit = (git rev-parse HEAD).Trim()
$LocalGitUrl = ([System.Uri]::new((Resolve-Path $Repo).Path + [System.IO.Path]::DirectorySeparatorChar)).AbsoluteUri
hermes plugins install $LocalGitUrl --ref $Commit
$PluginInstallExit = $LASTEXITCODE
hermes plugins validate $Repo --install-deps
$ValidateExit = $LASTEXITCODE
Write-Host "Plugin install exit: $PluginInstallExit ; validate exit: $ValidateExit"
```

This installs the **committed local Git folder**, not uncommitted edits or the draft catalog's zero SHA. It may show a local-file-source warning and dependency/enable prompts; review them and only consent to this known checkout. Do not use force, allow-removed or scanner bypasses. Existing plugin conflicts should be reported rather than overwritten. Syntax is verified in upstream [plugin commands](https://github.com/NousResearch/hermes-agent/blob/main/hermes_cli/subcommands/plugins.py) and [local Git URL resolver](https://github.com/NousResearch/hermes-agent/blob/main/hermes_cli/plugins_cmd.py). `validate` requires a path: `hermes plugins validate --install-deps` alone is incomplete.

**What you should see:** installation and capability/security validation succeed (exit 0), with the six declared tools including orphic_loop_step. Read warnings; do not treat scanner warnings or incomplete dependency installation as an automatic admission pass. Hermes installs dependencies in its own runtime, which can differ from the project venv.

After official setup, use `/orphic doctor` in Hermes chat. Ask Hermes to list its Orphic tools and perform a new local pair/loop using the same URLs but a fresh target name. Hermes uses its own store; a server for `$Store` does not automatically serve that separate store. Follow its returned serve_hint. Do not type JSON tool calls into PowerShell as commands.

**If it fails, paste this output:** failed command, exit codes, validation summary/traceback, Git SHA and `hermes plugins --help`. Redact private paths if desired and all credentials. If no host is available, mark this step NOT RUN; it remains a submission blocker.

## 9. Paste results to Orphic Lead

Copy this checklist, fill the blanks, and include the relevant log tails. Never send .env, cookies, account tokens or private screenshots.

- [ ] Windows 11 version, Python version, Git SHA/branch recorded: ___
- [ ] Dependencies installed; pip check clean: ___
- [ ] Full suite run 1 / run 2 / run 3: exit/counts/skips/errors ___
- [ ] Three consecutive full runs green with no timeouts (otherwise list exact tests): ___
- [ ] Doctor path/version recorded; actual Edge/Chrome tested: ___
- [ ] Public example.com/example.org capture result and report paths: ___
- [ ] HTTP report opens with adjacent PNGs: ___
- [ ] Verify reads pixels on the approved combined UI commit: PASS / FAIL / BLOCKED ___
- [ ] Content check exists and reads pixels on that commit: PASS / FAIL / BLOCKED ___
- [ ] Local loop round 1 continue + prompt; round 2 done: ___
- [ ] Hermes installed and local-folder plugin install passed: ___
- [ ] `hermes plugins validate PATH --install-deps` passed: ___
- [ ] Live Hermes tool discovery and a fresh tool-driven loop passed: ___
- [ ] Remaining failures/unclear/skipped/NOT RUN checks: ___

### What the existing timeouts mean

Previous Linux runs timed out in `URLBrowserTests.test_default_viewport_repeated_pixels_and_motion_disabled` (capture's real 30-second deadline) and `ReportServerTests.test_registry_discovery_across_processes_and_stale_cleanup` (5-second test-only child-process limit). They passed individually afterward; quiet full runs failed in different places. This suggests load/startup sensitivity but does not establish a root cause. The demo also hit a real matcher deadline. A successful isolated retry does not prove three consecutive suites are reliable.

Do not increase production navigation/matching budgets to turn failures into passes. A larger test-only child-process startup timeout could be appropriate **only after** proving the child is healthy but simply slow. A navigation wait can instead indicate a browser/network lifecycle problem requiring a separate engine fix. This documentation task makes neither change without that evidence. Final Linux three-run results and investigation notes are in [HANDOFF.md](HANDOFF.md); they are not Windows validation.
