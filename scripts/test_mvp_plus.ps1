$ErrorActionPreference = "Stop"

$Base = if ($env:BASE) { $env:BASE } else { "http://127.0.0.1:17777" }
$ApiPrefix = if ($env:API_PREFIX) { $env:API_PREFIX } else { "/v1" }
$StrictDelta = if ($env:STRICT_DELTA) { [int]$env:STRICT_DELTA } else { 0 }
$Cleanup = if ($env:CLEANUP) { [int]$env:CLEANUP } else { 0 }
$BundleOnFail = if ($env:BUNDLE_ON_FAIL) { [int]$env:BUNDLE_ON_FAIL } else { 1 }
$BundleDir = if ($env:BUNDLE_DIR) { $env:BUNDLE_DIR } else { ".\mvp_diagnose" }
$RunStructureVerify = if ($env:RUN_STRUCTURE_VERIFY) { [int]$env:RUN_STRUCTURE_VERIFY } else { 1 }
$RunComboRegression = if ($env:RUN_COMBO_REGRESSION_VERIFY) { [int]$env:RUN_COMBO_REGRESSION_VERIFY } else { 1 }
$ComboRegressionChapters = if ($env:COMBO_REGRESSION_CHAPTERS) { [int]$env:COMBO_REGRESSION_CHAPTERS } else { 3 }
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..")

New-Item -ItemType Directory -Force -Path $BundleDir | Out-Null

function Get-Api($Path) { Invoke-RestMethod -Uri "$Base$ApiPrefix$Path" -Method GET }
function Post-Api($Path, $BodyObj) {
  $json = $BodyObj | ConvertTo-Json -Depth 30
  Invoke-RestMethod -Uri "$Base$ApiPrefix$Path" -Method POST -ContentType "application/json" -Body $json
}
function Save-JsonFile([string]$Name, $Obj) {
  try { $Obj | ConvertTo-Json -Depth 40 | Set-Content -Encoding UTF8 -Path (Join-Path $BundleDir "$Name.json") } catch {}
}
function Poll-Job($JobId, $MaxTries = 300) {
  for ($i = 0; $i -lt $MaxTries; $i++) {
    $j = Get-Api "/jobs/$JobId"
    $status = [string]$j.status
    $stage = [string]$j.stage
    $pct = if ($j.progress -and $j.progress.pct -ne $null) { $j.progress.pct } else { $j.progress_value }
    Write-Host "[job] $JobId status=$status stage=$stage progress=$pct"
    if ($status -in @("succeeded", "done")) { return $j }
    if ($status -in @("failed", "canceled")) { throw "Job failed: $JobId" }
    Start-Sleep -Milliseconds 300
  }
  throw "Timeout polling job: $JobId"
}

function Bundle-OnFail([string]$Reason) {
  if ($BundleOnFail -ne 1) { return }
  Write-Host "== DIAG BUNDLE: $Reason =="
  try { Save-JsonFile "health" (Get-Api "/health") } catch {}
  try { Save-JsonFile "jobs_failed_recent" (Get-Api "/jobs?status=failed&limit=30") } catch {}
  try { Save-JsonFile "jobs_running_recent" (Get-Api "/jobs?status=running&limit=30") } catch {}
  try { Save-JsonFile "jobs_done_recent" (Get-Api "/jobs?status=succeeded&limit=30") } catch {}
}

try {
  Write-Host "== 0) health =="
  $health = Get-Api "/health"
  $health | ConvertTo-Json -Depth 10 | Write-Host
  Save-JsonFile "health" $health

  Write-Host "== 1) create book =="
  $book = Post-Api "/books" @{ title = "MVP Test Book"; author = "tester"; language = "zh" }
  $bookId = [string]$book.book_id
  Write-Host "BOOK_ID=$bookId"

  Write-Host "== 2) create chapter =="
  $chapter = Post-Api "/books/$bookId/chapters" @{ chapter_no = 1; title = "第一章"; arc_id = "vol-1"; arc_index = 1 }
  $chapterId = [string]$chapter.chapter_id
  Write-Host "CHAPTER_ID=$chapterId"

  Write-Host "== 3) save outline v1 =="
  $save = Post-Api "/chapters/$chapterId/outline_detail/save" @{
    note = "v1 seed"
    outline = @{
      schema_name = "OUTLINE_DETAIL"; schema_ver = 1; chapter_no = 1; chapter_title = "第一章"; template_ref = @{}
      nodes = @(
        @{ node_id = "N1"; type = "hook"; summary = "主角在雨夜收到匿名信，信中提到失踪父亲。"; beats = @(); characters = @("主角"); world_facts = @(); plot_hooks = @("父亲失踪"); conflict = @{goal_clarity=0.4;opposition_strength=0.2;stake_level=0.4;cost_level=0.0;time_pressure=0.2;info_gap=0.5;reversal_power=0.1}; constraints = @{max_words=180;must_exist=$true}; _meta=@{} }
        @{ node_id = "N2"; type = "turning_point"; summary = "主角来到废弃车站，被不明势力围堵，意识到被引入局。"; beats = @(); characters = @("主角"); world_facts = @(); plot_hooks = @("陷阱"); conflict = @{goal_clarity=0.5;opposition_strength=0.6;stake_level=0.6;cost_level=0.3;time_pressure=0.4;info_gap=0.5;reversal_power=0.6}; constraints = @{max_words=180;must_exist=$true}; _meta=@{} }
        @{ node_id = "N3"; type = "cliffhanger"; summary = "主角脱身后手机多出父亲语音：别相信任何人。"; beats = @(); characters = @("主角"); world_facts = @(); plot_hooks = @("父亲语音"); conflict = @{goal_clarity=0.5;opposition_strength=0.4;stake_level=0.6;cost_level=0.2;time_pressure=0.2;info_gap=0.7;reversal_power=0.4}; constraints = @{max_words=180;must_exist=$true;must_open_hook=$true}; _meta=@{} }
      )
      global_constraints = @{must_have_cost=$true;must_end_with_hook=$true}
    }
  }
  Write-Host ("OUTLINE_V1=" + $save.version)

  Write-Host "== 4) eval tension =="
  $eval = Post-Api "/chapters/$chapterId/tension/eval" @{ chapter_version_id = "00000000-0000-0000-0000-000000000000"; input_mode = "outline"; schema_ver = 1 }
  $evalDone = Poll-Job ([string]$eval.job_id)
  $beforeEvalRunId = [string]$evalDone.result.skill_run_id
  Save-JsonFile "job_eval" $evalDone

  Write-Host "== 5) control plan =="
  $plan = Post-Api "/chapters/$chapterId/tension/control_plan" @{
    targets = @{conflict_strength=0.78;stakes=0.74;cost=0.70;pace=0.72;reversal=0.68;hook=0.70}
    style = @{face_slap_density=0.18;upgrade_density=0.14}
    schema_ver = 1
  }
  $planDone = Poll-Job ([string]$plan.job_id)
  $planRunId = [string]$planDone.result.skill_run_id
  $planSr = Get-Api "/skill_runs/$planRunId"
  Save-JsonFile "skill_plan" $planSr
  $patches = @($planSr.output.result.patches)
  if ($patches.Count -lt 1) { throw "No patches from plan" }

  Write-Host "== 6) apply + measure =="
  $selected = @([string]$patches[0].patch_id)
  if ($patches.Count -gt 1) { $selected += [string]$patches[1].patch_id }
  $apply = Post-Api "/chapters/$chapterId/outline_detail/apply_patches" @{
    plan_skill_run_id = $planRunId
    selected_patch_ids = $selected
    auto_eval = $true
    targets = @{conflict_strength=0.78;stakes=0.74;cost=0.70;pace=0.72;reversal=0.68;hook=0.70}
  }
  $applyJobId = if ($apply.apply_job_id) { [string]$apply.apply_job_id } else { [string]$apply.job_id }
  $applyDone = Poll-Job $applyJobId
  Save-JsonFile "job_apply" $applyDone
  $delta = $applyDone.result.delta
  $delta | ConvertTo-Json -Depth 8 | Write-Host

  if ($StrictDelta -eq 1) {
    $ov = [double]($delta.overall)
    $cost = [double]($delta.cost)
    $rev = [double]($delta.reversal)
    if (-not ($ov -ge 0 -and ($cost -ge 0.05 -or $rev -ge 0.05))) {
      throw "STRICT_DELTA failed: overall=$ov cost=$cost reversal=$rev"
    }
  }

  if ($RunStructureVerify -eq 1) {
    Write-Host "== 7) structure template auto-builder verify =="
    $verifyScript = Join-Path $RepoRoot "scripts\verify_structure_templates.py"
    $engineVenvPy = Join-Path $RepoRoot "engine\.venv\Scripts\python.exe"
    if (Test-Path $engineVenvPy) {
      & $engineVenvPy $verifyScript
      if ($LASTEXITCODE -ne 0) { throw "structure verify failed (venv python): exit=$LASTEXITCODE" }
    } else {
      python $verifyScript
      if ($LASTEXITCODE -ne 0) { throw "structure verify failed (system python): exit=$LASTEXITCODE" }
    }
  }

  if ($RunComboRegression -eq 1) {
    Write-Host "== 8) combo baseline regression verify =="
    $comboVerifyScript = Join-Path $RepoRoot "scripts\verify_combo_baseline_regression.py"
    $engineVenvPy = Join-Path $RepoRoot "engine\.venv\Scripts\python.exe"
    if (Test-Path $engineVenvPy) {
      & $engineVenvPy $comboVerifyScript --base $Base --chapter-count $ComboRegressionChapters
      if ($LASTEXITCODE -ne 0) { throw "combo regression verify failed (venv python): exit=$LASTEXITCODE" }
    } else {
      python $comboVerifyScript --base $Base --chapter-count $ComboRegressionChapters
      if ($LASTEXITCODE -ne 0) { throw "combo regression verify failed (system python): exit=$LASTEXITCODE" }
    }
  }

  Write-Host "✅ MVP+ pipeline OK"
}
catch {
  Bundle-OnFail $_.Exception.Message
  throw
}
