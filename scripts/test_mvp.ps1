$ErrorActionPreference = "Stop"

$Base = if ($env:BASE) { $env:BASE } else { "http://127.0.0.1:17777" }
$ApiPrefix = if ($env:API_PREFIX) { $env:API_PREFIX } else { "/v1" }

function Get-Api($Path) {
  Invoke-RestMethod -Uri "$Base$ApiPrefix$Path" -Method GET
}

function Post-Api($Path, $BodyObj) {
  $json = $BodyObj | ConvertTo-Json -Depth 20
  Invoke-RestMethod -Uri "$Base$ApiPrefix$Path" -Method POST -ContentType "application/json" -Body $json
}

function Poll-Job($JobId, $MaxTries = 300) {
  for ($i = 0; $i -lt $MaxTries; $i++) {
    $j = Get-Api "/jobs/$JobId"
    $status = [string]$j.status
    $stage = [string]$j.stage
    $pct = if ($j.progress -and $j.progress.pct -ne $null) { $j.progress.pct } else { $j.progress_value }
    Write-Host "[job] $JobId status=$status stage=$stage progress=$pct"
    if ($status -in @("succeeded", "done")) { return $j }
    if ($status -in @("failed", "canceled")) {
      if ($j.error) { $j.error | ConvertTo-Json -Depth 8 | Write-Host }
      throw "Job failed: $JobId"
    }
    Start-Sleep -Milliseconds 400
  }
  throw "Timeout polling job: $JobId"
}

Write-Host "== 0) health =="
Get-Api "/health" | ConvertTo-Json -Depth 8 | Write-Host

Write-Host "== 1) create book =="
$book = Post-Api "/books" @{
  title = "MVP Test Book"
  author = "tester"
  language = "zh"
}
$bookId = [string]$book.book_id
Write-Host "BOOK_ID=$bookId"

Write-Host "== 2) create chapter =="
$chapter = Post-Api "/books/$bookId/chapters" @{
  chapter_no = 1
  title = "第一章"
  arc_id = "vol-1"
  arc_index = 1
}
$chapterId = [string]$chapter.chapter_id
Write-Host "CHAPTER_ID=$chapterId"

Write-Host "== 3) save outline v1 =="
$save = Post-Api "/chapters/$chapterId/outline_detail/save" @{
  note = "v1 seed"
  outline = @{
    schema_name = "OUTLINE_DETAIL"
    schema_ver = 1
    chapter_no = 1
    chapter_title = "第一章"
    template_ref = @{}
    nodes = @(
      @{
        node_id = "N1"; type = "hook"; summary = "主角在雨夜收到匿名信，信中提到失踪父亲。"
        beats = @(); characters = @("主角"); world_facts = @(); plot_hooks = @("父亲失踪")
        conflict = @{goal_clarity=0.4;opposition_strength=0.2;stake_level=0.4;cost_level=0.0;time_pressure=0.2;info_gap=0.5;reversal_power=0.1}
        constraints = @{max_words=180;must_exist=$true}; _meta = @{}
      },
      @{
        node_id = "N2"; type = "turning_point"; summary = "主角来到废弃车站，被不明势力围堵，意识到被引入局。"
        beats = @(); characters = @("主角"); world_facts = @(); plot_hooks = @("陷阱")
        conflict = @{goal_clarity=0.5;opposition_strength=0.6;stake_level=0.6;cost_level=0.3;time_pressure=0.4;info_gap=0.5;reversal_power=0.6}
        constraints = @{max_words=180;must_exist=$true}; _meta = @{}
      },
      @{
        node_id = "N3"; type = "cliffhanger"; summary = "主角脱身后手机多出父亲语音：别相信任何人。"
        beats = @(); characters = @("主角"); world_facts = @(); plot_hooks = @("父亲语音")
        conflict = @{goal_clarity=0.5;opposition_strength=0.4;stake_level=0.6;cost_level=0.2;time_pressure=0.2;info_gap=0.7;reversal_power=0.4}
        constraints = @{max_words=180;must_exist=$true;must_open_hook=$true}; _meta = @{}
      }
    )
    global_constraints = @{must_have_cost=$true;must_end_with_hook=$true}
  }
}
Write-Host ("OUTLINE_V1=" + $save.version)

Write-Host "== 4) eval tension (outline mode) =="
$evalJob = Post-Api "/chapters/$chapterId/tension/eval" @{
  chapter_version_id = "00000000-0000-0000-0000-000000000000"
  input_mode = "outline"
  schema_ver = 1
}
$evalJobId = [string]$evalJob.job_id
$evalDone = Poll-Job $evalJobId
$beforeEvalRunId = [string]$evalDone.result.skill_run_id
Write-Host "BEFORE_EVAL_RUN_ID=$beforeEvalRunId"

Write-Host "== 5) control plan =="
$planJob = Post-Api "/chapters/$chapterId/tension/control_plan" @{
  targets = @{conflict_strength=0.78;stakes=0.74;cost=0.70;pace=0.72;reversal=0.68;hook=0.70}
  style = @{face_slap_density=0.18;upgrade_density=0.14}
  schema_ver = 1
}
$planJobId = [string]$planJob.job_id
$planDone = Poll-Job $planJobId
$planRunId = [string]$planDone.result.skill_run_id
Write-Host "PLAN_RUN_ID=$planRunId"

$planSr = Get-Api "/skill_runs/$planRunId"
$patches = @($planSr.output.result.patches)
if ($patches.Count -lt 1) { throw "No patches produced by PLAN job." }
$selected = @([string]$patches[0].patch_id)
if ($patches.Count -gt 1) { $selected += [string]$patches[1].patch_id }

Write-Host "== 6) apply + measure =="
$applySubmit = Post-Api "/chapters/$chapterId/outline_detail/apply_patches" @{
  plan_skill_run_id = $planRunId
  selected_patch_ids = $selected
  auto_eval = $true
  targets = @{conflict_strength=0.78;stakes=0.74;cost=0.70;pace=0.72;reversal=0.68;hook=0.70}
}
$applyJobId = if ($applySubmit.apply_job_id) { [string]$applySubmit.apply_job_id } else { [string]$applySubmit.job_id }
$applyDone = Poll-Job $applyJobId

$newOutlineVersion = $applyDone.result.new_outline_version
$afterEvalRunId = [string]$applyDone.result.after_eval_run_id
$beforeEval2 = [string]$applyDone.result.before_eval_run_id

Write-Host "== 7) summary =="
Write-Host "BOOK_ID=$bookId"
Write-Host "CHAPTER_ID=$chapterId"
Write-Host "PLAN_RUN_ID=$planRunId"
Write-Host "NEW_OUTLINE_VERSION=$newOutlineVersion"
Write-Host "BEFORE_EVAL_RUN_ID=$beforeEvalRunId"
Write-Host "BEFORE_EVAL_2=$beforeEval2"
Write-Host "AFTER_EVAL_RUN_ID=$afterEvalRunId"
Write-Host "DELTA="
$applyDone.result.delta | ConvertTo-Json -Depth 8 | Write-Host

if ($beforeEval2 -and $afterEvalRunId) {
  Write-Host "== 8) eval compare =="
  Get-Api "/chapters/$chapterId/eval/compare?before_run_id=$beforeEval2&after_run_id=$afterEvalRunId" | ConvertTo-Json -Depth 10 | Write-Host
}

Write-Host "✅ MVP pipeline OK"

