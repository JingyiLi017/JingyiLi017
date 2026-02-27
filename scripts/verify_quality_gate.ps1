param(
  [string]$Base = "http://127.0.0.1:17777",
  [string]$ApiPrefix = "/v1",
  [switch]$SkipDesktopSmoke,
  [switch]$SkipApiContract,
  [bool]$AutoStartEngine = $true,
  [int]$EngineBootTimeoutSec = 120,
  [int]$EngineHealthTimeoutSec = 6,
  [int]$EngineHealthRetries = 6,
  [int]$EngineHealthRetryDelayMs = 800
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$reportDir = Join-Path $repoRoot "docs\reports"
New-Item -ItemType Directory -Force -Path $reportDir | Out-Null
$reportMd = Join-Path $reportDir "quality-gate-latest.md"
$reportJson = Join-Path $reportDir "quality-gate-latest.json"
$engineBootstrapOut = Join-Path $reportDir "quality-gate-engine-start.stdout.log"
$engineBootstrapErr = Join-Path $reportDir "quality-gate-engine-start.stderr.log"

$script:EngineBootProc = $null
$script:EngineStartedByGate = $false

$result = [ordered]@{
  started_at = (Get-Date).ToString("o")
  base = $Base
  api_prefix = $ApiPrefix
  ok = $false
  steps = [ordered]@{}
  error = $null
}

function Add-StepResult {
  param(
    [string]$Name,
    [bool]$Ok,
    [string]$Command,
    [int]$ExitCode,
    [double]$ElapsedMs,
    [string]$Message = ""
  )
  $result.steps[$Name] = [ordered]@{
    ok = $Ok
    command = $Command
    exit_code = $ExitCode
    elapsed_ms = [math]::Round($ElapsedMs, 1)
    message = $Message
    at = (Get-Date).ToString("o")
  }
}

function Run-ProcessStep {
  param(
    [Parameter(Mandatory = $true)][string]$Name,
    [Parameter(Mandatory = $true)][string]$FilePath,
    [Parameter(Mandatory = $true)][string[]]$ArgumentList,
    [Parameter(Mandatory = $true)][string]$CommandText
  )
  Write-Host "==> $Name"
  $sw = [System.Diagnostics.Stopwatch]::StartNew()
  $proc = Start-Process -FilePath $FilePath -ArgumentList $ArgumentList -WorkingDirectory $repoRoot -NoNewWindow -Wait -PassThru
  $sw.Stop()
  $exitCode = [int]$proc.ExitCode
  $ok = ($exitCode -eq 0)
  Add-StepResult -Name $Name -Ok $ok -Command $CommandText -ExitCode $exitCode -ElapsedMs $sw.Elapsed.TotalMilliseconds
  if (-not $ok) {
    throw "$Name failed with exit code $exitCode"
  }
}

function Test-EngineHealthOnce {
  param([int]$TimeoutSec = $EngineHealthTimeoutSec)
  try {
    $resp = Invoke-WebRequest -UseBasicParsing -Uri "$Base$ApiPrefix/health" -TimeoutSec $TimeoutSec
    return @{
      ok = ($resp.StatusCode -eq 200)
      status = [int]$resp.StatusCode
      message = "status=$($resp.StatusCode)"
    }
  } catch {
    return @{
      ok = $false
      status = 0
      message = [string]$_.Exception.Message
    }
  }
}

function Start-EngineForGate {
  param([int]$BootTimeoutSec = $EngineBootTimeoutSec)

  $devEngineScript = Join-Path $repoRoot "dev-engine.ps1"
  if (-not (Test-Path $devEngineScript)) {
    return @{
      ok = $false
      message = "dev-engine.ps1 not found: $devEngineScript"
    }
  }

  try {
    if (Test-Path $engineBootstrapOut) { Remove-Item -Force $engineBootstrapOut }
    if (Test-Path $engineBootstrapErr) { Remove-Item -Force $engineBootstrapErr }
  } catch {}

  $targetHost = "127.0.0.1"
  $targetPort = 17777
  try {
    $u = [uri]$Base
    if (-not [string]::IsNullOrWhiteSpace([string]$u.Host)) { $targetHost = [string]$u.Host }
    if ([int]$u.Port -gt 0) { $targetPort = [int]$u.Port }
  } catch {}

  $proc = Start-Process -FilePath "powershell.exe" `
    -ArgumentList @("-ExecutionPolicy", "Bypass", "-File", $devEngineScript, "-BindHost", $targetHost, "-Port", [string]$targetPort) `
    -WorkingDirectory $repoRoot `
    -WindowStyle Hidden `
    -PassThru `
    -RedirectStandardOutput $engineBootstrapOut `
    -RedirectStandardError $engineBootstrapErr
  $script:EngineBootProc = $proc
  $script:EngineStartedByGate = $true

  $deadline = (Get-Date).AddSeconds([math]::Max(15, $BootTimeoutSec))
  while ((Get-Date) -lt $deadline) {
    $health = Test-EngineHealthOnce -TimeoutSec $EngineHealthTimeoutSec
    if ($health.ok) {
      return @{
        ok = $true
        message = "engine auto-started, pid=$($proc.Id)"
      }
    }
    if ($proc.HasExited) {
      break
    }
    Start-Sleep -Milliseconds 1000
  }

  return @{
    ok = $false
    message = "engine auto-start timeout or process exited"
  }
}

function Check-HealthStep {
  param(
    [string]$Name = "engine_health",
    [int]$Retries = $EngineHealthRetries,
    [int]$TimeoutSec = $EngineHealthTimeoutSec
  )
  Write-Host "==> $Name"
  $sw = [System.Diagnostics.Stopwatch]::StartNew()
  $lastError = ""
  for ($i = 1; $i -le $Retries; $i++) {
    $health = Test-EngineHealthOnce -TimeoutSec $TimeoutSec
    if ($health.ok) {
      $sw.Stop()
      Add-StepResult -Name $Name -Ok $true -Command "GET $Base$ApiPrefix/health" -ExitCode 0 -ElapsedMs $sw.Elapsed.TotalMilliseconds -Message "status=200（第 $i/$Retries 次）"
      return
    }
    $lastError = [string]$health.message
    if ($i -lt $Retries) {
      Start-Sleep -Milliseconds $EngineHealthRetryDelayMs
    }
  }

  if ($AutoStartEngine) {
    Write-Host "==> engine_bootstrap (auto-start)"
    $bootSw = [System.Diagnostics.Stopwatch]::StartNew()
    $boot = Start-EngineForGate -BootTimeoutSec $EngineBootTimeoutSec
    $bootSw.Stop()
    Add-StepResult -Name "engine_bootstrap" -Ok ([bool]$boot.ok) -Command "powershell -File dev-engine.ps1" -ExitCode $(if ($boot.ok) { 0 } else { 1 }) -ElapsedMs $bootSw.Elapsed.TotalMilliseconds -Message ([string]$boot.message)
    if ($boot.ok) {
      $recheck = Test-EngineHealthOnce -TimeoutSec $TimeoutSec
      if ($recheck.ok) {
        $sw.Stop()
        Add-StepResult -Name $Name -Ok $true -Command "GET $Base$ApiPrefix/health" -ExitCode 0 -ElapsedMs $sw.Elapsed.TotalMilliseconds -Message "status=200（auto-start 后）"
        return
      }
      $lastError = [string]$recheck.message
    }
  }

  $sw.Stop()
  Add-StepResult -Name $Name -Ok $false -Command "GET $Base$ApiPrefix/health" -ExitCode 1 -ElapsedMs $sw.Elapsed.TotalMilliseconds -Message $lastError
  throw "$Name failed: $lastError"
}

function Write-Reports {
  $okCount = @($result.steps.Values | Where-Object { $_.ok }).Count
  $allCount = @($result.steps.Values).Count
  $lines = @()
  $lines += "# 质量门禁报告"
  $lines += ""
  $lines += "- 时间: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
  $lines += "- 目录: $repoRoot"
  $lines += "- 总体: " + ($(if ($result.ok) { "PASS" } else { "FAIL" }))
  $lines += "- 通过步数: $okCount/$allCount"
  $lines += ""
  $lines += "## 执行明细"
  $lines += ""
  $lines += "| Step | Result | Exit | Time(ms) | Message |"
  $lines += "| --- | --- | ---: | ---: | --- |"
  foreach ($kv in $result.steps.GetEnumerator()) {
    $name = $kv.Key
    $step = $kv.Value
    $flag = if ($step.ok) { "PASS" } else { "FAIL" }
    $msg = [string]$step.message
    $msg = $msg.Replace("|", "/")
    $lines += "| $name | $flag | $($step.exit_code) | $($step.elapsed_ms) | $msg |"
  }
  if (-not [string]::IsNullOrWhiteSpace([string]$result.error)) {
    $lines += ""
    $lines += "## 错误"
    $lines += ""
    $lines += "- $($result.error)"
  }
  $lines | Set-Content -Encoding UTF8 -Path $reportMd
  ($result | ConvertTo-Json -Depth 100) | Set-Content -Encoding UTF8 -Path $reportJson
}

try {
  Run-ProcessStep -Name "core_verify" -FilePath "cmd.exe" -ArgumentList @("/c", "npm run verify:core") -CommandText "npm run verify:core"
  Check-HealthStep -Name "engine_health"
  Run-ProcessStep -Name "splitbook_state_verify" -FilePath "cmd.exe" -ArgumentList @("/c", "npm run verify:splitbook-state") -CommandText "npm run verify:splitbook-state"
  if (-not $SkipApiContract) {
    Run-ProcessStep -Name "api_contract_verify" -FilePath "powershell.exe" -ArgumentList @(
      "-NoProfile",
      "-ExecutionPolicy", "Bypass",
      "-File", "scripts/verify_api_contract.ps1",
      "-Base", $Base,
      "-ApiPrefix", $ApiPrefix
    ) -CommandText "powershell -File scripts/verify_api_contract.ps1 -Base $Base -ApiPrefix $ApiPrefix"
  } else {
    Add-StepResult -Name "api_contract_verify" -Ok $true -Command "skipped" -ExitCode 0 -ElapsedMs 0 -Message "skip by flag"
  }
  if (-not $SkipDesktopSmoke) {
    Run-ProcessStep -Name "desktop_smart_pipeline_smoke" -FilePath "powershell.exe" -ArgumentList @(
      "-NoProfile",
      "-ExecutionPolicy", "Bypass",
      "-File", "scripts/test_desktop_smart_pipeline.ps1",
      "-Base", $Base,
      "-ApiPrefix", $ApiPrefix
    ) -CommandText "powershell -File scripts/test_desktop_smart_pipeline.ps1 -Base $Base -ApiPrefix $ApiPrefix"
  } else {
    Add-StepResult -Name "desktop_smart_pipeline_smoke" -Ok $true -Command "skipped" -ExitCode 0 -ElapsedMs 0 -Message "skip by flag"
  }
  $result.ok = $true
}
catch {
  $result.ok = $false
  $result.error = [string]$_.Exception.Message
}
finally {
  if ($script:EngineStartedByGate -and $script:EngineBootProc) {
    try {
      if (-not $script:EngineBootProc.HasExited) {
        if ($env:OS -eq "Windows_NT") {
          cmd /c "taskkill /PID $($script:EngineBootProc.Id) /T /F" | Out-Null
        } else {
          Stop-Process -Id $script:EngineBootProc.Id -Force -ErrorAction SilentlyContinue
        }
      }
    } catch {}
  }
  $result.finished_at = (Get-Date).ToString("o")
  Write-Reports
  Write-Host "report_md=$reportMd"
  Write-Host "report_json=$reportJson"
  if (-not $result.ok) {
    exit 1
  }
}
