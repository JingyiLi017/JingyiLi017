param(
  [switch]$NoInstall
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$engineDir = Join-Path $root "engine"
$venvPython = Join-Path $engineDir ".venv\\Scripts\\python.exe"
$python = if (Test-Path $venvPython) { $venvPython } else { "python" }

Write-Host "[sidecar-build] python=$python"
Write-Host "[sidecar-build] engineDir=$engineDir"

if (-not $NoInstall) {
  & $python -m pip install --upgrade pip | Out-Null
  & $python -m pip install -r (Join-Path $engineDir "requirements.txt")
  & $python -m pip install pyinstaller
}

$distDir = Join-Path $engineDir "dist\\sidecar"
if (Test-Path $distDir) { Remove-Item -Recurse -Force $distDir }
New-Item -ItemType Directory -Force -Path $distDir | Out-Null

Push-Location $engineDir
try {
  & $python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --name sidecar `
    --distpath $distDir `
    --paths $engineDir `
    sidecar_entry.py
} finally {
  Pop-Location
}

$exe = Join-Path $distDir "sidecar.exe"
if (-not (Test-Path $exe)) {
  throw "sidecar.exe not produced: $exe"
}
Write-Host "[sidecar-build] ok -> $exe"

