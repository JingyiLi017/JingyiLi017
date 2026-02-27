param(
  [string]$BindHost = "127.0.0.1",
  [int]$Port = 17777,
  [switch]$Reload,
  [switch]$ForceInstall,
  [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

function Get-UsablePythonLauncher {
  $candidates = @(
    @{ Exe = "py"; Args = @("-3.13") },
    @{ Exe = "py"; Args = @() },
    @{ Exe = "python"; Args = @() }
  )
  foreach ($candidate in $candidates) {
    $exe = [string]$candidate.Exe
    $args = @($candidate.Args)
    try {
      & $exe @($args + @("--version")) | Out-Null
      if ($LASTEXITCODE -eq 0) {
        return @{ Exe = $exe; Args = $args }
      }
    } catch {
      continue
    }
  }
  throw "NO_USABLE_PYTHON_LAUNCHER"
}

function Test-VenvPython {
  param([Parameter(Mandatory = $true)][string]$PythonPath)
  if (-not (Test-Path $PythonPath)) { return $false }
  try {
    & $PythonPath --version | Out-Null
    return ($LASTEXITCODE -eq 0)
  } catch {
    return $false
  }
}

function Get-PythonVersionText {
  param([Parameter(Mandatory = $true)][string]$PythonPath)
  try {
    $v = & $PythonPath -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"
    if ($LASTEXITCODE -ne 0) { return "" }
    return [string]$v
  } catch {
    return ""
  }
}

Write-Host "Starting Postgres(pgvector) with Docker..."
docker compose -f .\infra\docker-compose.yml up -d

$launcher = Get-UsablePythonLauncher
$venvDir = Join-Path $PSScriptRoot "engine\.venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"

if ((Test-Path $venvDir) -and (-not (Test-VenvPython -PythonPath $venvPython))) {
  Write-Warning "Existing engine venv is not usable. Recreating..."
  Remove-Item -Recurse -Force $venvDir
}

if (-not (Test-VenvPython -PythonPath $venvPython)) {
  Write-Host "Creating Python venv..."
  & $launcher.Exe @($launcher.Args + @("-m", "venv", $venvDir))
  if ($LASTEXITCODE -ne 0) { throw "VENV_CREATE_FAILED" }
}

$requirementsPath = Join-Path $PSScriptRoot "engine\requirements.txt"
$depsMarkerPath = Join-Path $venvDir ".deps-cache.json"
$needsInstall = $true

if ($SkipInstall) {
  $needsInstall = $false
} elseif (-not $ForceInstall -and (Test-Path $depsMarkerPath)) {
  try {
    $cached = Get-Content $depsMarkerPath -Raw | ConvertFrom-Json
    $cachedHash = [string]($cached.requirements_sha256)
    $cachedPy = [string]($cached.python_version)
    $currentHash = [string]((Get-FileHash -Path $requirementsPath -Algorithm SHA256).Hash)
    $currentPy = Get-PythonVersionText -PythonPath $venvPython
    if ($currentHash -and $currentPy -and $cachedHash -eq $currentHash -and $cachedPy -eq $currentPy) {
      $needsInstall = $false
    }
  } catch {
    $needsInstall = $true
  }
}

if ($needsInstall) {
  Write-Host "Installing engine deps..."
  & $venvPython -m pip install -U pip
  if ($LASTEXITCODE -ne 0) { throw "PIP_UPGRADE_FAILED" }
  & $venvPython -m pip install -r ".\engine\requirements.txt"
  if ($LASTEXITCODE -ne 0) { throw "PIP_INSTALL_FAILED" }
  try {
    $cachePayload = @{
      requirements_sha256 = [string]((Get-FileHash -Path $requirementsPath -Algorithm SHA256).Hash)
      python_version = Get-PythonVersionText -PythonPath $venvPython
      updated_at = (Get-Date).ToString("o")
    }
    $cachePayload | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 -Path $depsMarkerPath
  } catch {
    Write-Warning "Failed to write deps cache marker: $($_.Exception.Message)"
  }
} else {
  Write-Host "Skipping dependency install (cache hit)."
}

Write-Host "Starting engine on $BindHost`:$Port ..."
Set-Location .\engine
$uvicornArgs = @("-m", "uvicorn", "app.main:app", "--host", $BindHost, "--port", [string]$Port)
if ($Reload) {
  $uvicornArgs += "--reload"
}
& $venvPython @uvicornArgs
