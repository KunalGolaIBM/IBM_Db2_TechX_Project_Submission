# ==============================================================================
# FinSight AI — Stop IBM Db2 Container (stop-db.ps1)
# ==============================================================================
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

Write-Host ">>> Stopping FinSight AI IBM Db2 Container..." -ForegroundColor Cyan

Push-Location $ProjectRoot
try {
    docker compose stop
    Write-Host ">>> Db2 container stopped safely. Data persists in 'finsight_db2_data' volume." -ForegroundColor Green
} finally {
    Pop-Location
}
