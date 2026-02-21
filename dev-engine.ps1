$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

Write-Host "Starting Postgres(pgvector) with Docker..."
docker compose -f .\infra\docker-compose.yml up -d

if (-not (Test-Path .\engine\.venv)) {
  Write-Host "Creating Python venv..."
  python -m venv .\engine\.venv
}

Write-Host "Installing engine deps..."
cmd /c ".\\engine\\.venv\\Scripts\\python -m pip install -U pip"
cmd /c ".\\engine\\.venv\\Scripts\\pip install -r .\\engine\\requirements.txt"

Write-Host "Starting engine on 127.0.0.1:17777 ..."
Set-Location .\engine
cmd /c ".\\.venv\\Scripts\\uvicorn app.main:app --reload --host 127.0.0.1 --port 17777"
