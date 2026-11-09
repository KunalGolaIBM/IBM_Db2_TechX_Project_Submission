# ==============================================================================
# FinSight AI — Check IBM Db2 Container & Health (check-db.ps1)
# ==============================================================================
[CmdletBinding()]
param()

$ErrorActionPreference = "Continue"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "         FinSight AI - IBM Db2 Health Check" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Container status
Write-Host ""
Write-Host "[1] Checking Docker Container Status:" -ForegroundColor Yellow
$container = docker ps -a --filter "name=finsight-db2" --format "{{.ID}} | Status: {{.Status}} | Ports: {{.Ports}}"
if ($container) {
    Write-Host "   $container" -ForegroundColor Green
} else {
    Write-Host "   [!] Container 'finsight-db2' does not exist." -ForegroundColor Red
    exit 1
}

# 2. Check Port 50000 listening on localhost
Write-Host ""
Write-Host "[2] Checking Local Port 50000 Binding:" -ForegroundColor Yellow
$portCheck = Get-NetTCPConnection -LocalPort 50000 -ErrorAction SilentlyContinue
if ($portCheck) {
    Write-Host "   Port 50000 is LISTENING on $($portCheck.LocalAddress)" -ForegroundColor Green
} else {
    Write-Host "   [!] Port 50000 is not currently active on host." -ForegroundColor Yellow
}

# 3. Check Db2 Instance Inside Container
Write-Host ""
Write-Host "[3] Checking Db2 Engine and FINDB Database Status:" -ForegroundColor Yellow
$checkSql = "connect to FINDB;`nSELECT CURRENT SERVER FROM SYSIBM.SYSDUMMY1;`nSELECT count(*) AS total_transactions FROM FINSIGHT.TRANSACTIONS;`nconnect reset;"

$output = $checkSql | docker exec -i finsight-db2 su - db2inst1 -c "db2 -t"

if ($LASTEXITCODE -eq 0) {
    Write-Host "   Db2 engine is ONLINE and connected to FINDB successfully!" -ForegroundColor Green
    Write-Host ($output -join "`n")
} else {
    Write-Host "   [!] Db2 is still initializing or unavailable." -ForegroundColor Yellow
    Write-Host ($output -join "`n")
}

Write-Host "==========================================================" -ForegroundColor Cyan
