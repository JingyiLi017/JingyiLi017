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

if (-not $SkipBuild) {
  cmd /c npm run build:sidecar
  if ($LASTEXITCODE -ne 0) { throw "build:sidecar failed" }
  cmd /c npm run build
  if ($LASTEXITCODE -ne 0) { throw "build failed" }
}

if ($Dir) {
  cmd /c npx electron-builder --dir
} else {
  cmd /c npx electron-builder
}
if ($LASTEXITCODE -ne 0) { throw "electron-builder failed" }

