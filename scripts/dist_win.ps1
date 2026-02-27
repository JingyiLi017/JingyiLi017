param(
  [switch]$SkipBuild,
  [switch]$Dir,
  [switch]$NoPackage
)

$ErrorActionPreference = "Stop"

# Mirror defaults (can be overridden by existing env vars)
if (-not $env:ELECTRON_MIRROR) {
  $env:ELECTRON_MIRROR = "https://npmmirror.com/mirrors/electron/"
}
if (-not $env:ELECTRON_BUILDER_BINARIES_MIRROR) {
  $env:ELECTRON_BUILDER_BINARIES_MIRROR = "https://npmmirror.com/mirrors/electron-builder-binaries/"
}

Write-Host "[dist] ELECTRON_MIRROR=$($env:ELECTRON_MIRROR)"
Write-Host "[dist] ELECTRON_BUILDER_BINARIES_MIRROR=$($env:ELECTRON_BUILDER_BINARIES_MIRROR)"

if ($NoPackage) {
  Write-Host "[dist] NoPackage mode: skip build and electron-builder execution."
  exit 0
}

function Stop-ProcessTreeById([int]$TargetProcessId) {
  try {
    Stop-Process -Id $TargetProcessId -Force -ErrorAction Stop
  } catch {
    try { cmd /c "taskkill /PID $TargetProcessId /F" | Out-Null } catch {}
  }
}

function Stop-LockingProcesses([string]$RootPath) {
  $targets = @()
  $processById = @{}
  try {
    Get-CimInstance Win32_Process | ForEach-Object { $processById[[int]$_.ProcessId] = $_ }
  } catch {}

  try {
    $targets += Get-Process | Where-Object {
      try {
        $_.Path -and $_.Path.StartsWith($RootPath, [System.StringComparison]::OrdinalIgnoreCase)
      } catch {
        $false
      }
    }
  } catch {}

  $lockedWin32 = @()
  try {
    $lockedWin32 = Get-CimInstance Win32_Process | Where-Object {
      $p = $_.ExecutablePath
      if (-not $p) { return $false }
      if ($p.StartsWith($RootPath, [System.StringComparison]::OrdinalIgnoreCase)) { return $true }
      if ($_.Name -ieq "sidecar.exe" -and $p.IndexOf("\release\win-unpacked\", [System.StringComparison]::OrdinalIgnoreCase) -ge 0) { return $true }
      return $false
    }

    $targets += $lockedWin32 | ForEach-Object {
      [PSCustomObject]@{
        Id = [int]$_.ProcessId
        ProcessName = $_.Name
        Path = $_.ExecutablePath
      }
    }
  } catch {}

  foreach ($p in $lockedWin32) {
    $parentId = [int]$p.ParentProcessId
    while ($parentId -gt 0 -and $parentId -ne 4 -and $processById.ContainsKey($parentId)) {
      $parent = $processById[$parentId]
      $parentName = [string]$parent.Name
      if ($parentName -ieq "WriterBook Desktop.exe" -or $parentName -ieq "electron.exe") {
        $targets += [PSCustomObject]@{
          Id = [int]$parent.ProcessId
          ProcessName = $parentName
          Path = $parent.ExecutablePath
        }
        $parentId = [int]$parent.ParentProcessId
        continue
      }
      break
    }
  }

  $targets = $targets | Group-Object Id | ForEach-Object { $_.Group[0] }
  if (-not $targets -or $targets.Count -eq 0) { return }

  Write-Host "[dist] Found potential locking processes, stopping..."
  $targets | ForEach-Object {
    Write-Host ("[dist] stop pid={0} name={1}" -f $_.Id, $_.ProcessName)
    Stop-ProcessTreeById -TargetProcessId ([int]$_.Id)
  }
  Start-Sleep -Milliseconds 900
}

function Remove-DirWithRetry([string]$Path, [int]$RetryCount = 4) {
  for ($i = 0; $i -lt $RetryCount; $i++) {
    if (-not (Test-Path $Path)) { return $true }
    try {
      Remove-Item $Path -Recurse -Force -ErrorAction Stop
      return $true
    } catch {
      if ($i -ge ($RetryCount - 1)) {
        return $false
      }
      Start-Sleep -Milliseconds (500 * ($i + 1))
    }
  }
  return $false
}

if (-not $SkipBuild) {
  cmd /c npm run build:sidecar
  if ($LASTEXITCODE -ne 0) { throw "build:sidecar failed" }
  cmd /c npm run build
  if ($LASTEXITCODE -ne 0) { throw "build failed" }
}

$unpackedRoot = Join-Path (Get-Location) "release\\win-unpacked"
Stop-LockingProcesses -RootPath $unpackedRoot

if (Test-Path $unpackedRoot) {
  if (Remove-DirWithRetry -Path $unpackedRoot) {
    Write-Host "[dist] Cleaned old output: $unpackedRoot"
  } else {
    Write-Warning "[dist] Failed to clean old output, will try fallback output dir on failure."
  }
}

$builderArgs = @()
if ($Dir) { $builderArgs += "--dir" }

function Invoke-Builder([string[]]$Args) {
  $argLine = ($Args | ForEach-Object { $_ }) -join " "
  if ([string]::IsNullOrWhiteSpace($argLine)) {
    cmd /c "npx electron-builder"
  } else {
    cmd /c "npx electron-builder $argLine"
  }
}

Invoke-Builder $builderArgs
$builderExit = $LASTEXITCODE
if ($builderExit -ne 0) {
  Stop-LockingProcesses -RootPath $unpackedRoot
  if (Test-Path $unpackedRoot) {
    [void](Remove-DirWithRetry -Path $unpackedRoot)
  }
  Write-Warning "[dist] Retrying electron-builder once after lock cleanup..."
  Invoke-Builder $builderArgs
  $builderExit = $LASTEXITCODE
}
if ($builderExit -ne 0) {
  $isCi = [string]::Equals($env:CI, "true", [System.StringComparison]::OrdinalIgnoreCase)
  if (-not $isCi) {
    $fallbackOutput = "release-local-" + (Get-Date -Format "yyyyMMdd-HHmmss")
    $fallbackArgs = @("--config.directories.output=$fallbackOutput") + $builderArgs
    Write-Warning "[dist] electron-builder failed with default output, retrying with fallback output: $fallbackOutput"
    Invoke-Builder $fallbackArgs
    $builderExit = $LASTEXITCODE
    if ($builderExit -eq 0) {
      $fallbackAbs = Join-Path (Get-Location) $fallbackOutput
      Write-Host "[dist] Fallback build succeeded: $fallbackAbs"
      exit 0
    }
  }
  throw "electron-builder failed"
}
