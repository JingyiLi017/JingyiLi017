param(
  [string]$Base = "http://127.0.0.1:17777",
  [string]$ApiPrefix = "/v1"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$pythonExe = Join-Path $repoRoot "engine\.venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
  $pythonExe = "python"
}

Write-Host "==> ensure pytest installed =="
try {
  & $pythonExe -m pytest --version | Out-Host
  if ($LASTEXITCODE -ne 0) { throw "pytest not available" }
} catch {
  Write-Host "pytest not found, installing dev dependencies..."
  & $pythonExe -m pip install -r engine/requirements-dev.txt | Out-Host
  if ($LASTEXITCODE -ne 0) {
    throw "failed to install engine/requirements-dev.txt"
  }
}

$env:API_BASE = $Base
$env:API_PREFIX = $ApiPrefix

Write-Host "==> run api contract regression tests =="
& $pythonExe -m pytest engine/tests/api_contract -q
if ($LASTEXITCODE -ne 0) {
  throw "api contract regression failed: exit=$LASTEXITCODE"
}

Write-Host "✅ api contract regression passed"
