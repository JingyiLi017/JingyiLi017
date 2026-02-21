param(
  [string]$Base = "http://127.0.0.1:17777",
  [string]$ApiPrefix = "/v1",
  [string]$WorkspacePath = "",
  [switch]$ForceStubLlm,
  [string]$OutFile = ".\mvp_diagnose\desktop_smart_pipeline_result.json"
)

$ErrorActionPreference = "Stop"

$AgentToken = $env:AGENT_TOKEN
if (-not $PSBoundParameters.ContainsKey("ForceStubLlm")) {
  $ForceStubLlm = $true
}
if (-not $WorkspacePath) {
  $WorkspacePath = Join-Path (Resolve-Path ".").Path "workspace_test"
}
New-Item -ItemType Directory -Force -Path $WorkspacePath | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $OutFile) | Out-Null

function Invoke-Api {
  param(
    [Parameter(Mandatory = $true)][string]$Path,
    [ValidateSet("GET", "POST")][string]$Method = "GET",
    [object]$Body = $null
  )
  $uri = "$Base$ApiPrefix$Path"
  $headers = @{}
  if ($AgentToken) {
    $headers["Authorization"] = "Bearer $AgentToken"
  }
  if ($Method -eq "GET") {
    return Invoke-RestMethod -Uri $uri -Method GET -Headers $headers
  }
  $json = if ($null -ne $Body) { $Body | ConvertTo-Json -Depth 40 } else { "{}" }
  $bytes = [System.Text.Encoding]::UTF8.GetBytes($json)
  $resp = Invoke-WebRequest -Uri $uri -Method POST -Headers $headers -ContentType "application/json; charset=utf-8" -Body $bytes -UseBasicParsing
  if (-not $resp.Content) { return @{} }
  return ($resp.Content | ConvertFrom-Json)
}

function Mark-Step {
  param(
    [Parameter(Mandatory = $true)][hashtable]$Result,
    [Parameter(Mandatory = $true)][string]$Name,
    [Parameter(Mandatory = $true)][bool]$Ok,
    [string]$Message = ""
  )
  $Result.steps[$Name] = @{
    ok = $Ok
    message = $Message
  }
}

$result = @{
  started_at = (Get-Date).ToString("o")
  base = $Base
  api_prefix = $ApiPrefix
  steps = @{}
  ids = @{}
  payloads = @{}
  ok = $false
}

try {
  Write-Host "== 0) health =="
  $health = Invoke-Api -Path "/health" -Method "GET"
  Mark-Step -Result $result -Name "health" -Ok $true -Message ("ok=" + [string]$health.ok)
  $result.payloads.health = $health

  Write-Host "== 1) create book =="
  $book = Invoke-Api -Path "/books" -Method "POST" -Body @{
    title = "Desktop Smart Pipeline Smoke " + (Get-Date -Format "yyyyMMdd_HHmmss")
    author = "smoke"
    language = "zh"
  }
  $bookId = [string]$book.book_id
  if (-not $bookId) { throw "BOOK_ID_EMPTY" }
  $result.ids.book_id = $bookId
  Mark-Step -Result $result -Name "create_book" -Ok $true -Message $bookId

  Write-Host "== 2) create chapter =="
  $chapter = Invoke-Api -Path "/books/$bookId/chapters" -Method "POST" -Body @{
    chapter_no = 1
    title = "烟测章节"
    arc_id = "smoke-vol-1"
    arc_index = 1
  }
  $chapterId = [string]$chapter.chapter_id
  if (-not $chapterId) { throw "CHAPTER_ID_EMPTY" }
  $result.ids.chapter_id = $chapterId
  Mark-Step -Result $result -Name "create_chapter" -Ok $true -Message $chapterId

  Write-Host "== 3) auto create volume =="
  $volAuto = Invoke-Api -Path "/books/$bookId/volumes/auto_create" -Method "POST" -Body @{
    chapters_per_volume = 10
  }
  $volumeId = ""
  if ($volAuto.items -and $volAuto.items.Count -gt 0) {
    $volumeId = [string]$volAuto.items[0].volume_id
  } else {
    $volList = Invoke-Api -Path "/books/$bookId/volumes" -Method "GET"
    if ($volList.items -and $volList.items.Count -gt 0) {
      $volumeId = [string]$volList.items[0].volume_id
    }
  }
  if (-not $volumeId) { throw "VOLUME_ID_EMPTY" }
  $result.ids.volume_id = $volumeId
  Mark-Step -Result $result -Name "create_volume" -Ok $true -Message $volumeId

  Write-Host "== 4) set workspace =="
  $ws = Invoke-Api -Path "/books/$bookId/workspace" -Method "POST" -Body @{
    workspace_path = $WorkspacePath
    book_slug = "smoke-" + $bookId.Substring(0, 8)
  }
  Mark-Step -Result $result -Name "set_workspace" -Ok $true -Message (ConvertTo-Json $ws -Depth 8 -Compress)

  Write-Host "== 5) draft run =="
  $draftRun = Invoke-Api -Path "/draft/run" -Method "POST" -Body @{
    book_id = $bookId
    chapter_id = $chapterId
    intent_confirmed = "smoke smart pipeline"
    force_stub_llm = [bool]$ForceStubLlm
    dry_run = $false
    reuse_if_exists = $false
    idempotency_key = "smoke-smart-" + [Guid]::NewGuid().ToString("N")
  }
  $result.payloads.draft_run = $draftRun
  if (-not $draftRun.ok) { throw "DRAFT_RUN_NOT_OK" }
  Mark-Step -Result $result -Name "draft_run" -Ok $true -Message ("run_id=" + [string]$draftRun.run_id)

  Write-Host "== 6) list versions =="
  $versions = Invoke-Api -Path "/draft/list_versions" -Method "POST" -Body @{
    chapter_id = $chapterId
  }
  $items = @($versions.items)
  if ($items.Count -lt 1) { throw "NO_DRAFT_VERSIONS" }
  $latestDraftId = [string]$items[0].draft_id
  $result.ids.draft_id = $latestDraftId
  $result.payloads.versions = $versions
  Mark-Step -Result $result -Name "list_versions" -Ok $true -Message ("count=" + [string]$items.Count)

  Write-Host "== 7) select latest =="
  $select = Invoke-Api -Path "/draft/select" -Method "POST" -Body @{
    book_id = $bookId
    chapter_id = $chapterId
    draft_id = $latestDraftId
    selected_by = "smoke"
    reason = "smart pipeline smoke test"
  }
  $result.payloads.select = $select
  Mark-Step -Result $result -Name "select_latest" -Ok $true -Message ("selected=" + [string]$latestDraftId)

  Write-Host "== 8) publish pack =="
  $pack = Invoke-Api -Path "/export/publish_pack" -Method "POST" -Body @{
    book_id = $bookId
    volume_id = $volumeId
    pack_name = "smoke_pack_" + (Get-Date -Format "yyyyMMdd_HHmmss")
  }
  $result.payloads.publish_pack = $pack
  if (-not $pack.ok) { throw "PUBLISH_PACK_NOT_OK" }
  Mark-Step -Result $result -Name "publish_pack" -Ok $true -Message ([string]$pack.output_dir)

  Write-Host "== 9) preflight run =="
  $preflight = Invoke-Api -Path "/preflight/run" -Method "POST" -Body @{
    book_id = $bookId
    volume_id = $volumeId
    write_report = $false
  }
  $result.payloads.preflight = $preflight
  Mark-Step -Result $result -Name "preflight_run" -Ok $true -Message ("overall=" + [string]($preflight.report.summary.overall))

  Write-Host "== 10) fixwizard plan =="
  $fwPlan = Invoke-Api -Path "/fixwizard/plan" -Method "POST" -Body @{
    book_id = $bookId
    volume_id = $volumeId
  }
  $result.payloads.fixwizard_plan = $fwPlan
  $fixes = @($fwPlan.fixes)
  Mark-Step -Result $result -Name "fixwizard_plan" -Ok $true -Message ("fixes=" + [string]$fixes.Count)

  if ($fixes.Count -gt 0) {
    Write-Host "== 11) fixwizard execute (first low/first available) =="
    $pick = $fixes | Where-Object { [string]$_.risk -eq "low" } | Select-Object -First 1
    if (-not $pick) { $pick = $fixes | Select-Object -First 1 }
    $fwExec = Invoke-Api -Path "/fixwizard/execute" -Method "POST" -Body @{
      book_id = $bookId
      volume_id = $volumeId
      chapter_id = $chapterId
      selected_fixes = @(@{ fix_id = [string]$pick.fix_id })
      preflight = $preflight.report
      preflight_summary = $fwPlan.summary
      auto_recheck = $true
    }
    $result.payloads.fixwizard_execute = $fwExec
    $chainId = [string]$fwExec.chain_id
    if (-not $chainId) { throw "FIXWIZARD_CHAIN_ID_EMPTY" }
    $result.ids.chain_id = $chainId
    Mark-Step -Result $result -Name "fixwizard_execute" -Ok $true -Message ("chain_id=" + $chainId)

    Write-Host "== 12) fixwizard rollback_last =="
    $fwRollback = Invoke-Api -Path "/fixwizard/rollback_last" -Method "POST" -Body @{
      book_id = $bookId
      volume_id = $volumeId
    }
    $result.payloads.fixwizard_rollback_last = $fwRollback
    Mark-Step -Result $result -Name "fixwizard_rollback_last" -Ok $true -Message ("chain_id=" + [string]$fwRollback.chain_id)
  } else {
    Mark-Step -Result $result -Name "fixwizard_execute" -Ok $true -Message "skipped: no fixes"
    Mark-Step -Result $result -Name "fixwizard_rollback_last" -Ok $true -Message "skipped: no chain"
  }

  $result.ok = $true
  $result.finished_at = (Get-Date).ToString("o")
  $result | ConvertTo-Json -Depth 50 | Set-Content -Encoding UTF8 -Path $OutFile
  Write-Host "✅ desktop smart pipeline smoke test passed"
  Write-Host "result_file=$OutFile"
}
catch {
  $result.ok = $false
  $result.finished_at = (Get-Date).ToString("o")
  $result.error = $_.Exception.Message
  $result | ConvertTo-Json -Depth 50 | Set-Content -Encoding UTF8 -Path $OutFile
  Write-Host "❌ desktop smart pipeline smoke test failed"
  Write-Host $_.Exception.Message
  Write-Host "result_file=$OutFile"
  exit 1
}
