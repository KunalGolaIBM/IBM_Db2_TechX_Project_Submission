# ==============================================================================
# FinSight AI — Start IBM Db2 Container (start-db.ps1)
# ==============================================================================
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

Write-Host ">>> Starting FinSight AI IBM Db2 Container..." -ForegroundColor Cyan

# Check if .env exists
$EnvFile = Join-Path $ProjectRoot ".env"
if (-not (Test-Path $EnvFile)) {
    Write-Error "ERROR: .env file not found at $EnvFile. Copy .env.example to .env and configure credentials first."
    exit 1
}

# Run docker-compose up -d
Push-Location $ProjectRoot
try {
    docker compose up -d
    Write-Host ">>> Container launch initiated. Checking status..." -ForegroundColor Green
    docker ps --filter "name=finsight-db2" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    Write-Host ""
    Write-Host "Note: Db2 engine initialization takes approximately 1-2 minutes on first boot." -ForegroundColor Yellow
    Write-Host "Run 'scripts/check-db.ps1' to monitor initialization progress." -ForegroundColor Cyan
} finally {
    Pop-Location
}
