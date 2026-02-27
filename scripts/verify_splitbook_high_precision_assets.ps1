$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$pythonExe = Join-Path $repoRoot "engine\.venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
  $pythonExe = "python"
}

& $pythonExe "engine/scripts/verify_splitbook_high_precision_assets.py"
if ($LASTEXITCODE -ne 0) {
  throw "verify_splitbook_high_precision_assets failed"
}
