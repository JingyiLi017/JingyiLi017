$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$reportDir = Join-Path $repoRoot "docs\reports"
New-Item -ItemType Directory -Force -Path $reportDir | Out-Null

$ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$reportPath = Join-Path $reportDir "core-verify-latest.md"
$lines = @()
$lines += "# 核心能力验证报告"
$lines += ""
$lines += "- 时间: $ts"
$lines += "- 目录: $repoRoot"
$lines += ""

$script:StaticChecksOk = $true
$script:HealthOk = $false

function Run-Step {
  param(
    [string]$Name,
    [string]$Command
  )
  Write-Host "==> $Name"
  try {
    cmd /c $Command | Out-Host
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
      throw "命令退出码非零: $exitCode"
    }
    $script:lines += "- [x] $Name"
  } catch {
    $script:StaticChecksOk = $false
    $script:lines += "- [ ] $Name"
    $script:lines += "  - 错误: $($_.Exception.Message)"
    $script:lines | Set-Content -Path $reportPath -Encoding UTF8
    throw
  }
}

function Check-Health {
  param(
    [int]$MaxRetries = 3,
    [int]$TimeoutSec = 5
  )
  for ($i = 1; $i -le $MaxRetries; $i++) {
    try {
      $health = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:17777/v1/health" -TimeoutSec $TimeoutSec
      if ($health.StatusCode -eq 200) {
        return @{ ok = $true; message = "status=200（第 $i/$MaxRetries 次）" }
      }
      Start-Sleep -Milliseconds 400
    } catch {
      if ($i -lt $MaxRetries) {
        Start-Sleep -Milliseconds 400
      }
    }
  }
  return @{ ok = $false; message = "连接超时或引擎未启动（重试 $MaxRetries 次）" }
}

Run-Step -Name "Python 语法编译检查" -Command "python -m compileall -q engine/app"
Run-Step -Name "TypeScript 类型检查" -Command "npm run typecheck"
Run-Step -Name "前后端构建检查" -Command "npm run build"
Run-Step -Name "能力矩阵生成" -Command "python scripts/export_capabilities.py"

$healthCheck = Check-Health -MaxRetries 3 -TimeoutSec 5
if ($healthCheck.ok) {
  $script:HealthOk = $true
  $lines += "- [x] 引擎在线接口检查（/v1/health，$($healthCheck.message)）"
} else {
  $lines += "- [ ] 引擎在线接口检查（$($healthCheck.message)）"
}

$lines += ""
$lines += "## 产物"
$lines += ""
$lines += "- docs/PROJECT_CAPABILITY_MATRIX.md"
$lines += "- docs/reports/core-verify-latest.md"
$lines += ""
$lines += "## 结论"
$lines += ""
if ($StaticChecksOk -and $HealthOk) {
  $lines += "- 静态与在线检查均通过，可进入联调/回归阶段。"
} elseif ($StaticChecksOk) {
  $lines += "- 静态检查通过，但在线接口未确认；请先启动 sidecar/engine 后复验。"
} else {
  $lines += "- 核心能力验证未通过，请修复失败项后重试。"
}

$lines | Set-Content -Path $reportPath -Encoding UTF8
Write-Host ""
Write-Host "[ok] report generated: $reportPath"
