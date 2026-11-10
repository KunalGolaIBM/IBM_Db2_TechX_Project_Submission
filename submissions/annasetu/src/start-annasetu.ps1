param(
    [switch]$SkipBrowserOpen
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
$logs = Join-Path $root 'logs'
New-Item -ItemType Directory -Force -Path $logs | Out-Null

function Get-ListenerPid([int]$Port) {
    $listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($listener) { return [int]$listener.OwningProcess }
    return $null
}

function Wait-For([scriptblock]$Check, [int]$Attempts, [string]$Description) {
    for ($i = 0; $i -lt $Attempts; $i++) {
        try { if (& $Check) { return } } catch {}
        Start-Sleep -Seconds 2
    }
    throw "$Description did not become ready. See the logs directory."
}

$docker = Get-Command docker -ErrorAction Stop
$containerState = & $docker.Source inspect --format '{{.State.Status}}' annasetu-db2 2>$null
if ($LASTEXITCODE -ne 0) {
    throw 'The existing annasetu-db2 container was not found. The launcher will not create or reset a database.'
}
if ($containerState.Trim() -ne 'running') {
    & $docker.Source start annasetu-db2 | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Could not start the existing annasetu-db2 container.' }
}
Wait-For {
    $state = & $docker.Source inspect --format '{{.State.Health.Status}}' annasetu-db2 2>$null
    $LASTEXITCODE -eq 0 -and $state.Trim() -eq 'healthy'
} 90 'IBM Db2'

$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Project Python environment is missing at .venv\Scripts\python.exe.' }
$target = & $python -c 'from api.app.config import settings; print(settings.db2_name.upper())'
if ($LASTEXITCODE -ne 0 -or $target.Trim() -ne 'ANNASETU') {
    throw 'The local .env must target ANNASETU before starting the operational API.'
}
$cors = & $python -c 'from api.app.config import settings; print(str("http://127.0.0.1:5175" in settings.allowed_origins and "http://localhost:5175" in settings.allowed_origins))'
if ($LASTEXITCODE -ne 0 -or $cors.Trim() -ne 'True') {
    throw 'The local .env must allow the 5175 frontend origin.'
}

$apiPid = Get-ListenerPid 8010
if ($apiPid) {
    try {
        $api = Invoke-RestMethod -TimeoutSec 4 'http://127.0.0.1:8010/api/health'
        if ($api.status -ne 'ok' -or $api.database -ne 'IBM Db2' -or $api.database_name -ne 'ANNASETU') {
            throw "Port 8010 is occupied by a service that is not the configured AnnaSetu ANNASETU API (PID $apiPid)."
        }
    } catch {
        throw "Port 8010 is occupied by an unverified service (PID $apiPid); no process was stopped. $($_.Exception.Message)"
    }
    Write-Output "FastAPI already healthy on ANNASETU at 127.0.0.1:8010 (PID $apiPid)."
} else {
    $env:DB2_NAME = 'ANNASETU'
    $env:CORS_ORIGINS = 'http://localhost:5173,http://127.0.0.1:5173,http://localhost:5175,http://127.0.0.1:5175'
    Remove-Item Env:DEMO_PASSWORD -ErrorAction SilentlyContinue
    $apiOut = Join-Path $logs 'api.stdout.log'
    $apiErr = Join-Path $logs 'api.stderr.log'
    Start-Process -FilePath $python `
        -ArgumentList @('-m', 'uvicorn', 'api.app.main:app', '--host', '127.0.0.1', '--port', '8010', '--log-level', 'info') `
        -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardOutput $apiOut -RedirectStandardError $apiErr | Out-Null
    Wait-For {
        $api = Invoke-RestMethod -TimeoutSec 3 'http://127.0.0.1:8010/api/health'
        $api.status -eq 'ok' -and $api.database -eq 'IBM Db2' -and $api.database_name -eq 'ANNASETU'
    } 60 'FastAPI on ANNASETU'
    Write-Output 'FastAPI started on ANNASETU at 127.0.0.1:8010; logs are in .\logs.'
}

$frontendPid = Get-ListenerPid 5175
if ($frontendPid) {
    try {
        $page = Invoke-WebRequest -UseBasicParsing -TimeoutSec 4 'http://127.0.0.1:5175/'
        if ($page.StatusCode -ne 200) { throw 'Unexpected HTTP response.' }
        $apiSource = Invoke-WebRequest -UseBasicParsing -TimeoutSec 4 'http://127.0.0.1:5175/src/api.js'
        if ($apiSource.Content -notmatch '127\.0\.0\.1:8010/api') {
            throw "Port 5175 is occupied by an outdated frontend (PID $frontendPid)."
        }
    } catch {
        throw "Port 5175 is occupied by an unverified service (PID $frontendPid); no process was stopped. $($_.Exception.Message)"
    }
    Write-Output "React/Vite already responding at 127.0.0.1:5175 (PID $frontendPid)."
} else {
    $vite = Join-Path $root 'frontend\node_modules\vite\bin\vite.js'
    if (-not (Test-Path -LiteralPath $vite)) { throw 'Frontend dependencies are missing; run npm install in frontend.' }
    $env:VITE_API_BASE = 'http://127.0.0.1:8010/api'
    $node = (Get-Command node -ErrorAction Stop).Source
    $webOut = Join-Path $logs 'vite.stdout.log'
    $webErr = Join-Path $logs 'vite.stderr.log'
    Start-Process -FilePath $node `
        -ArgumentList @($vite, '--host', '127.0.0.1', '--port', '5175', '--strictPort') `
        -WorkingDirectory (Join-Path $root 'frontend') -WindowStyle Hidden `
        -RedirectStandardOutput $webOut -RedirectStandardError $webErr | Out-Null
    Wait-For {
        $page = Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 'http://127.0.0.1:5175/'
        $page.StatusCode -eq 200
    } 30 'React/Vite on port 5175'
    Write-Output 'React/Vite started at 127.0.0.1:5175; logs are in .\logs.'
}

if (-not $SkipBrowserOpen) {
    Start-Process 'http://127.0.0.1:5175' | Out-Null
}
Write-Output 'AnnaSetu URL: http://127.0.0.1:5175'
