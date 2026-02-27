param(
  [string]$Base = "http://127.0.0.1:17777",
  [string]$ApiPrefix = "/v1",
  [string]$OutFile = ".\\docs\\reports\\splitbook-state-consistency-latest.json",
  [int]$JobTimeoutSec = 900,
  [int]$HealthTimeoutSec = 6,
  [int]$HealthRetries = 6,
  [int]$HealthRetryDelayMs = 800,
  [bool]$AutoCleanupStaleJobs = $true,
  [int]$StaleSeconds = 120,
  [switch]$KeepArtifacts
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$reportDir = Split-Path -Parent $OutFile
if ([string]::IsNullOrWhiteSpace($reportDir)) {
  $reportDir = "."
}
New-Item -ItemType Directory -Force -Path $reportDir | Out-Null

function Try-Health {
  param(
    [Parameter(Mandatory = $true)][string]$CandidateBase,
    [int]$TimeoutSec = $HealthTimeoutSec
  )
  try {
    $resp = Invoke-WebRequest -UseBasicParsing -Method GET -Uri "$CandidateBase$ApiPrefix/health" -TimeoutSec $TimeoutSec
    if (-not $resp.Content) { return $null }
    return ($resp.Content | ConvertFrom-Json)
  } catch {
    return $null
  }
}

function Ensure-EngineOnline {
  param(
    [int]$Retries = $HealthRetries,
    [int]$SleepMs = $HealthRetryDelayMs
  )

  $candidates = @($Base)
  if ($Base -match "127\\.0\\.0\\.1:17777") {
    $candidates += "http://127.0.0.1:17779"
  } elseif ($Base -match "127\\.0\\.0\\.1:17779") {
    $candidates += "http://127.0.0.1:17777"
  }

  foreach ($candidate in $candidates) {
    for ($i = 0; $i -lt $Retries; $i++) {
      $health = Try-Health -CandidateBase $candidate
      if ($health -ne $null) {
        $script:Base = $candidate
        return $health
      }
      Start-Sleep -Milliseconds $SleepMs
    }
  }

  $ports = @(17777, 17779)
  $listening = @()
  try {
    $listening = Get-NetTCPConnection -State Listen | Where-Object { $_.LocalPort -in $ports } | Select-Object -ExpandProperty LocalPort -Unique
  } catch {
    $listening = @()
  }
  $listenText = if ($listening.Count -gt 0) { ($listening -join ",") } else { "无" }
  throw "无法连接引擎健康接口（$Base$ApiPrefix/health）。请先启动引擎（建议执行：.\\dev-engine.ps1 或启动桌面端并确认 Sidecar 在线）。当前监听端口：$listenText。"
}

function Invoke-Api {
  param(
    [Parameter(Mandatory = $true)][string]$Path,
    [ValidateSet("GET", "POST", "DELETE")][string]$Method = "GET",
    [object]$Body = $null
  )
  $uri = "$Base$ApiPrefix$Path"
  if ($Method -eq "GET") {
    $resp = Invoke-WebRequest -UseBasicParsing -Method GET -Uri $uri
  } elseif ($Method -eq "DELETE") {
    $resp = Invoke-WebRequest -UseBasicParsing -Method DELETE -Uri $uri
  } else {
    $json = if ($null -ne $Body) { $Body | ConvertTo-Json -Depth 80 } else { "{}" }
    $resp = Invoke-WebRequest -UseBasicParsing -Method POST -Uri $uri -ContentType "application/json; charset=utf-8" -Body $json
  }
  if (-not $resp.Content) { return @{} }
  return ($resp.Content | ConvertFrom-Json)
}

function Invoke-ApiAllowError {
  param(
    [Parameter(Mandatory = $true)][string]$Path,
    [ValidateSet("GET", "POST", "DELETE")][string]$Method = "GET",
    [object]$Body = $null
  )
  $uri = "$Base$ApiPrefix$Path"
  try {
    $payload = Invoke-Api -Path $Path -Method $Method -Body $Body
    return @{
      ok = $true
      status = 200
      body = $payload
      raw = ""
    }
  } catch {
    $resp = $_.Exception.Response
    $status = 0
    $raw = ""
    if (-not [string]::IsNullOrWhiteSpace([string]$_.ErrorDetails.Message)) {
      $raw = [string]$_.ErrorDetails.Message
    }
    if ($resp) {
      try { $status = [int]$resp.StatusCode } catch { $status = 0 }
      if ([string]::IsNullOrWhiteSpace($raw)) {
        try {
          $stream = $resp.GetResponseStream()
          if ($stream) {
            $sr = New-Object System.IO.StreamReader($stream)
            $raw = $sr.ReadToEnd()
            $sr.Dispose()
          }
        } catch {
          $raw = ""
        }
      }
    }
    $body = $null
    if (-not [string]::IsNullOrWhiteSpace($raw)) {
      try { $body = $raw | ConvertFrom-Json } catch { $body = $null }
    }
    return @{
      ok = $false
      status = $status
      body = $body
      raw = $raw
    }
  }
}

function Mark-Step {
  param(
    [Parameter(Mandatory = $true)][hashtable]$Result,
    [Parameter(Mandatory = $true)][string]$Name,
    [Parameter(Mandatory = $true)][bool]$Ok,
    [string]$Message = "",
    [bool]$Skipped = $false,
    [object]$Data = $null
  )
  $Result.steps[$Name] = @{
    ok = $Ok
    skipped = $Skipped
    message = $Message
    data = $Data
    at = (Get-Date).ToString("o")
  }
}

function Get-Job {
  param([Parameter(Mandatory = $true)][string]$JobId)
  return Invoke-Api -Path "/jobs/$JobId" -Method "GET"
}

function Get-JobListByStatus {
  param(
    [Parameter(Mandatory = $true)][string]$Status,
    [int]$Limit = 200
  )
  $out = Invoke-Api -Path "/jobs?status=$Status&limit=$Limit" -Method "GET"
  return @($out.items)
}

function Get-JobAgeSeconds {
  param([Parameter(Mandatory = $true)][object]$Job)
  $updatedAt = [string]$Job.updated_at
  $createdAt = [string]$Job.created_at
  $tsText = if (-not [string]::IsNullOrWhiteSpace($updatedAt)) { $updatedAt } else { $createdAt }
  if ([string]::IsNullOrWhiteSpace($tsText)) { return 0 }
  try {
    $ts = [datetime]::Parse($tsText).ToUniversalTime()
    return [int](((Get-Date).ToUniversalTime() - $ts).TotalSeconds)
  } catch {
    return 0
  }
}

function Cleanup-StaleSplitbookJobs {
  param([int]$ThresholdSeconds = 120)

  $running = Get-JobListByStatus -Status "running" -Limit 200
  $queued = Get-JobListByStatus -Status "queued" -Limit 200
  $active = @($running + $queued)
  $splitbookActive = @(
    $active | Where-Object {
      $cap = [string]$_.capability_id
      $typ = [string]$_.job_type
      ($cap -like "splitbook.*") -or ($typ.ToUpper().Contains("SPLITBOOK"))
    }
  )

  $stale = @(
    $splitbookActive | Where-Object {
      (Get-JobAgeSeconds -Job $_) -ge $ThresholdSeconds
    }
  )

  $resumed = @()
  $canceled = @()
  $resumeFailed = @()
  $cancelFailed = @()

  foreach ($j in $stale) {
    $jid = [string]$j.job_id
    if ([string]::IsNullOrWhiteSpace($jid)) { continue }
    try {
      $r = Invoke-Api -Path "/jobs/$jid/resume?force=true" -Method "POST"
      $resumed += @{
        job_id = $jid
        status = [string]$r.status
      }
    } catch {
      $resumeFailed += @{
        job_id = $jid
        error = [string]$_.Exception.Message
      }
    }
    Start-Sleep -Milliseconds 150
    try {
      $latest = Get-Job -JobId $jid
      $st = [string]$latest.status
      $age = Get-JobAgeSeconds -Job $latest
      if (($st -eq "running" -or $st -eq "queued") -and $age -ge $ThresholdSeconds) {
        try {
          $c = Invoke-Api -Path "/jobs/$jid/cancel" -Method "POST"
          $canceled += @{
            job_id = $jid
            status = [string]$c.status
          }
        } catch {
          $cancelFailed += @{
            job_id = $jid
            error = [string]$_.Exception.Message
          }
        }
      }
    } catch {
      $cancelFailed += @{
        job_id = $jid
        error = [string]$_.Exception.Message
      }
    }
  }

  return @{
    total_active = @($splitbookActive).Count
    stale_count = @($stale).Count
    resumed = $resumed
    canceled = $canceled
    resume_failed = $resumeFailed
    cancel_failed = $cancelFailed
  }
}

function Wait-JobTerminal {
  param(
    [Parameter(Mandatory = $true)][string]$JobId,
    [int]$TimeoutSec = 900
  )
  $start = Get-Date
  $lastUpdatedAt = ""
  $lastStatus = ""
  $lastTick = Get-Date
  $resumeCount = 0
  while (((Get-Date) - $start).TotalSeconds -lt $TimeoutSec) {
    $job = Get-Job -JobId $JobId
    $st = [string]$job.status
    $updatedAt = [string]$job.updated_at
    if (@("succeeded", "failed", "canceled") -contains $st) {
      return $job
    }
    $now = Get-Date
    if ((($now - $lastTick).TotalSeconds -ge 10)) {
      $pct = 0
      try { $pct = [int][math]::Round(([double]$job.progress_value) * 100) } catch { $pct = 0 }
      Write-Host ("   - waiting job={0} status={1} progress={2}% updated_at={3}" -f $JobId, $st, $pct, $updatedAt)
      $lastTick = $now
    }

    $isPotentiallyStalled = $false
    if (-not [string]::IsNullOrWhiteSpace($updatedAt)) {
      try {
        $ts = [datetime]::Parse($updatedAt).ToUniversalTime()
        $staleSec = ((Get-Date).ToUniversalTime() - $ts).TotalSeconds
        if (($st -eq "queued" -and $staleSec -ge 15) -or ($st -eq "running" -and $staleSec -ge 60)) {
          $isPotentiallyStalled = $true
        }
      } catch {}
    } elseif ($st -eq $lastStatus -and $st -in @("queued", "running") -and ((Get-Date) - $start).TotalSeconds -ge 12) {
      $isPotentiallyStalled = $true
    }

    if ($isPotentiallyStalled -and $resumeCount -lt 8) {
      try {
        $resumeResp = Invoke-Api -Path "/jobs/$JobId/resume?force=true" -Method "POST"
        $resumeCount += 1
        Write-Host ("   - auto resume triggered ({0}/8), status={1}" -f $resumeCount, [string]$resumeResp.status)
      } catch {
        Write-Host ("   - auto resume failed: {0}" -f [string]$_.Exception.Message)
      }
    }

    $lastStatus = $st
    $lastUpdatedAt = $updatedAt
    Start-Sleep -Milliseconds 800
  }
  throw ("JOB_TIMEOUT:{0}:last_status={1}:last_updated_at={2}" -f $JobId, $lastStatus, $lastUpdatedAt)
}

function Get-Splitbooks {
  param([bool]$Sync = $true)
  $syncText = if ($Sync) { "true" } else { "false" }
  $out = Invoke-Api -Path "/splitbooks?limit=200&sync=$syncText" -Method "GET"
  return @($out.items)
}

function Find-Splitbook {
  param(
    [Parameter(Mandatory = $true)][array]$Items,
    [Parameter(Mandatory = $true)][string]$SplitbookId
  )
  return ($Items | Where-Object { [string]$_.splitbook_id -eq $SplitbookId } | Select-Object -First 1)
}

$result = @{
  ok = $false
  started_at = (Get-Date).ToString("o")
  base = $Base
  api_prefix = $ApiPrefix
  steps = @{}
  artifacts = @{}
}

$createdSplitbookId = ""
$createdSplitbookName = ""
$tempFilePath = ""
$activeJobId = ""

try {
  Write-Host "== 1) 健康检查 =="
  $health = Ensure-EngineOnline
  Mark-Step -Result $result -Name "health" -Ok $true -Message ("health ok @ " + $Base) -Data $health

  if ($AutoCleanupStaleJobs) {
    Write-Host "== 1.5) 预清理疑似卡住任务 =="
    $cleanup = Cleanup-StaleSplitbookJobs -ThresholdSeconds $StaleSeconds
    $cleanupOk = (@($cleanup.resume_failed).Count -eq 0 -and @($cleanup.cancel_failed).Count -eq 0)
    Mark-Step -Result $result -Name "cleanup_stale_splitbook_jobs" -Ok $cleanupOk -Message ("active=" + [string]$cleanup.total_active + ", stale=" + [string]$cleanup.stale_count + ", resumed=" + [string](@($cleanup.resumed).Count) + ", canceled=" + [string](@($cleanup.canceled).Count)) -Data $cleanup
  } else {
    Mark-Step -Result $result -Name "cleanup_stale_splitbook_jobs" -Ok $true -Skipped $true -Message "已关闭自动预清理"
  }

  Write-Host "== 2) 创建测试文本与拆书 =="
  $tmpDir = Join-Path $repoRoot "workspace_test\\splitbook_state_verify"
  New-Item -ItemType Directory -Force -Path $tmpDir | Out-Null
  $ts = Get-Date -Format "yyyyMMdd_HHmmss"
  $tempFilePath = Join-Path $tmpDir "verify_splitbook_$ts.txt"
  $chunk = "这是拆书状态一致性测试文本。用于验证中止、继续、对账、删除等关键能力。`r`n"
  $builder = New-Object System.Text.StringBuilder
  for ($i = 0; $i -lt 2400; $i++) {
    [void]$builder.Append($chunk)
  }
  [System.IO.File]::WriteAllText($tempFilePath, $builder.ToString(), [System.Text.Encoding]::UTF8)

  $createdSplitbookName = "状态一致性回归-$ts"
  $created = Invoke-Api -Path "/splitbooks" -Method "POST" -Body @{
    name = $createdSplitbookName
    author = "qa"
    source_path = $tempFilePath
    note = "auto verify"
  }
  $createdSplitbookId = [string]$created.splitbook_id
  if ([string]::IsNullOrWhiteSpace($createdSplitbookId)) {
    throw "SPLITBOOK_CREATE_NO_ID"
  }
  $result.artifacts.created_splitbook_id = $createdSplitbookId
  $result.artifacts.temp_file = $tempFilePath
  Mark-Step -Result $result -Name "create_splitbook" -Ok $true -Message $createdSplitbookId

  Write-Host "== 3) 导入任务完成 =="
  $ingest = Invoke-Api -Path "/splitbooks/$createdSplitbookId/ingest" -Method "POST" -Body @{
    path = $tempFilePath
    encoding = "utf-8"
    auto_optimize = $true
  }
  $ingestJobId = [string]$ingest.job_id
  if ([string]::IsNullOrWhiteSpace($ingestJobId)) {
    throw "INGEST_JOB_ID_EMPTY"
  }
  $ingestTerminal = Wait-JobTerminal -JobId $ingestJobId -TimeoutSec $JobTimeoutSec
  $ingestOk = ([string]$ingestTerminal.status -eq "succeeded")
  Mark-Step -Result $result -Name "ingest_terminal" -Ok $ingestOk -Message ("status=" + [string]$ingestTerminal.status) -Data $ingestTerminal
  if (-not $ingestOk) {
    throw ("INGEST_NOT_SUCCEEDED:" + [string]$ingestTerminal.status)
  }

  Write-Host "== 4) 队列任务列表可见性 =="
  $queuedList = Invoke-Api -Path "/jobs?status=queued&limit=30" -Method "GET"
  Mark-Step -Result $result -Name "jobs_queued_list_available" -Ok $true -Message ("queued_count=" + [string](@($queuedList.items).Count))

  Write-Host "== 5) 向量化中止后状态回落 =="
  $embed = Invoke-Api -Path "/splitbooks/$createdSplitbookId/embed" -Method "POST" -Body @{
    auto_optimize = $true
    batch = 32
  }
  $embedJobId = [string]$embed.job_id
  if ([string]::IsNullOrWhiteSpace($embedJobId)) {
    throw "EMBED_JOB_ID_EMPTY"
  }
  $activeJobId = $embedJobId
  Start-Sleep -Milliseconds 350
  $cancelOut = Invoke-Api -Path "/jobs/$embedJobId/cancel" -Method "POST"
  $canceled = Wait-JobTerminal -JobId $embedJobId -TimeoutSec 180
  $booksAfterCancel = Get-Splitbooks -Sync $true
  $bookAfterCancel = Find-Splitbook -Items $booksAfterCancel -SplitbookId $createdSplitbookId
  $embedStatusAfterCancel = [string]$bookAfterCancel.embed_status
  $cancelOk = ([string]$canceled.status -eq "canceled") -and (@("canceled", "pending", "failed", "done") -contains $embedStatusAfterCancel)
  Mark-Step -Result $result -Name "embed_cancel_consistent" -Ok $cancelOk -Message ("job=" + [string]$canceled.status + ", splitbook=" + $embedStatusAfterCancel) -Data @{
    cancel_response = $cancelOut
    job = $canceled
    splitbook = $bookAfterCancel
  }
  $activeJobId = ""

  Write-Host "== 6) 继续向量化条件可判定 =="
  $booksForResume = Get-Splitbooks -Sync $true
  $bookForResume = Find-Splitbook -Items $booksForResume -SplitbookId $createdSplitbookId
  $ingestStatus = [string]$bookForResume.ingest_status
  $embedStatus = [string]$bookForResume.embed_status
  $activeEmbedStatus = [string]$bookForResume.stats.active_embed_job_status
  $resumeEligible =
    ($ingestStatus -eq "done") -and
    (@("pending", "failed", "canceled") -contains $embedStatus) -and
    (-not (@("queued", "running") -contains $activeEmbedStatus))
  Mark-Step -Result $result -Name "embed_resume_condition" -Ok $resumeEligible -Message ("ingest=" + $ingestStatus + ", embed=" + $embedStatus + ", active_embed=" + $activeEmbedStatus)

  Write-Host "== 7) 已完成向量化重复触发保护 =="
  $allBooks = Get-Splitbooks -Sync $true
  $doneBook = $allBooks | Where-Object { [string]$_.embed_status -eq "done" } | Select-Object -First 1
  if ($null -eq $doneBook) {
    Mark-Step -Result $result -Name "embed_duplicate_guard" -Ok $true -Skipped $true -Message "未找到 embed_status=done 的拆书，跳过此项"
  } else {
    $dup = Invoke-ApiAllowError -Path "/splitbooks/$([string]$doneBook.splitbook_id)/embed" -Method "POST" -Body @{}
    $detailCode = ""
    if ($dup.body -and $dup.body.detail_code) {
      $detailCode = [string]$dup.body.detail_code
    } elseif ($dup.body -and $dup.body.detail) {
      $detailCode = [string]$dup.body.detail
    } else {
      $detailCode = [string]$dup.raw
    }
    $dupConflict = (-not $dup.ok) -and ($dup.status -eq 409)
    $dupKnownCode = $dupConflict -and ($detailCode -match "SPLITBOOK_EMBED_ALREADY_DONE")
    $dupFallback = $dupConflict -and ([string]$doneBook.embed_status -eq "done") -and [string]::IsNullOrWhiteSpace($detailCode)
    $dupOk = $dupKnownCode -or $dupFallback
    Mark-Step -Result $result -Name "embed_duplicate_guard" -Ok $dupOk -Message ("status=" + [string]$dup.status + ", detail=" + $detailCode) -Data $dup
  }

  Write-Host "== 8) 删除拆书生效 =="
  $deleteOut = Invoke-Api -Path "/splitbooks/$createdSplitbookId" -Method "DELETE"
  $remaining = Get-Splitbooks -Sync $true
  $deletedRow = Find-Splitbook -Items $remaining -SplitbookId $createdSplitbookId
  $deleteOk = ($deleteOut.ok -eq $true) -and ($null -eq $deletedRow)
  Mark-Step -Result $result -Name "splitbook_delete_effective" -Ok $deleteOk -Message ("deleted=" + [string]$deleteOut.ok)
  $createdSplitbookId = ""

  $required = @(
    "health",
    "cleanup_stale_splitbook_jobs",
    "create_splitbook",
    "ingest_terminal",
    "jobs_queued_list_available",
    "embed_cancel_consistent",
    "embed_resume_condition",
    "embed_duplicate_guard",
    "splitbook_delete_effective"
  )
  $allOk = $true
  foreach ($k in $required) {
    $item = $result.steps[$k]
    if ($null -eq $item) { $allOk = $false; continue }
    if (-not [bool]$item.ok) { $allOk = $false; continue }
  }
  $result.ok = $allOk
  $result.finished_at = (Get-Date).ToString("o")
  $result | ConvertTo-Json -Depth 100 | Set-Content -Encoding UTF8 -Path $OutFile
  if ($result.ok) {
    Write-Host "✅ 拆书状态一致性验证通过"
  } else {
    Write-Host "❌ 拆书状态一致性验证未全部通过，请查看报告"
    exit 2
  }
}
catch {
  $result.ok = $false
  $result.finished_at = (Get-Date).ToString("o")
  $result.error = [string]$_.Exception.Message
  $result | ConvertTo-Json -Depth 100 | Set-Content -Encoding UTF8 -Path $OutFile
  Write-Error ("验证失败: " + [string]$_.Exception.Message)
  exit 1
}
finally {
  if (-not $KeepArtifacts) {
    if (-not [string]::IsNullOrWhiteSpace($activeJobId)) {
      try { Invoke-Api -Path "/jobs/$activeJobId/cancel" -Method "POST" | Out-Null } catch {}
    }
    if (-not [string]::IsNullOrWhiteSpace($createdSplitbookId)) {
      try { Invoke-Api -Path "/splitbooks/$createdSplitbookId" -Method "DELETE" | Out-Null } catch {}
    }
    if (-not [string]::IsNullOrWhiteSpace($tempFilePath) -and (Test-Path $tempFilePath)) {
      try { Remove-Item -Force -Path $tempFilePath } catch {}
    }
  }
  Write-Host ("report_file=" + $OutFile)
}
