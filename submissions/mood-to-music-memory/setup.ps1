# setup.ps1
# One-command setup for Mood-to-Music Memory on Windows.
# Run from the project root: .\setup.ps1

param(
    [switch]$SkipVenv,
    [switch]$SkipFrontend,
    [switch]$SkipSeed
)

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Mood-to-Music Memory — Setup Script" -ForegroundColor Cyan
Write-Host "  IBM Db2 TechX Summit 2026" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# ── 1. Check .env ────────────────────────────────────────────────────
if (-not (Test-Path "$ProjectRoot\.env")) {
    Write-Host "[1/6] Creating .env from .env.example..." -ForegroundColor Yellow
    Copy-Item "$ProjectRoot\.env.example" "$ProjectRoot\.env"
    Write-Host "  ⚠  Edit .env with your Db2 credentials before continuing!" -ForegroundColor Red
    Write-Host "  Then re-run: .\setup.ps1" -ForegroundColor Red
    exit 1
} else {
    Write-Host "[1/6] .env found ✅" -ForegroundColor Green
}

# ── 2. Python virtual environment ────────────────────────────────────
if (-not $SkipVenv) {
    Write-Host "[2/6] Setting up Python virtual environment..." -ForegroundColor Yellow
    if (-not (Test-Path "$ProjectRoot\.venv")) {
        python -m venv "$ProjectRoot\.venv"
    }
    & "$ProjectRoot\.venv\Scripts\pip" install -r "$ProjectRoot\requirements.txt" --quiet
    Write-Host "  Python dependencies installed ✅" -ForegroundColor Green
} else {
    Write-Host "[2/6] Skipping venv setup" -ForegroundColor Gray
}

# ── 3. Test Db2 connection ───────────────────────────────────────────
Write-Host "[3/6] Testing IBM Db2 connection..." -ForegroundColor Yellow
try {
    & "$ProjectRoot\.venv\Scripts\python.exe" "$ProjectRoot\db\check_db2.py"
    Write-Host "  Db2 connection OK ✅" -ForegroundColor Green
} catch {
    Write-Host "  ✗ Cannot connect to Db2. Is DB2 running? Check .env settings." -ForegroundColor Red
    exit 1
}

# ── 4. Run schema + seed ────────────────────────────────────────────
if (-not $SkipSeed) {
    Write-Host "[4/6] Setting up Db2 schema and seed data..." -ForegroundColor Yellow
    & "$ProjectRoot\.venv\Scripts\python.exe" "$ProjectRoot\db\setup_db2.py"
    & "$ProjectRoot\.venv\Scripts\python.exe" "$ProjectRoot\db\seed_db.py"
    Write-Host "  Schema and seed data ready ✅" -ForegroundColor Green
} else {
    Write-Host "[4/6] Skipping seed (use -SkipSeed to skip next time)" -ForegroundColor Gray
}

# ── 5. Frontend ──────────────────────────────────────────────────────
if (-not $SkipFrontend) {
    Write-Host "[5/6] Installing frontend dependencies..." -ForegroundColor Yellow
    Set-Location "$ProjectRoot\frontend"
    pnpm install --silent
    Set-Location $ProjectRoot
    Write-Host "  Frontend dependencies installed ✅" -ForegroundColor Green
} else {
    Write-Host "[5/6] Skipping frontend install" -ForegroundColor Gray
}

# ── 6. Check Ollama ─────────────────────────────────────────────────
Write-Host "[6/6] Checking Ollama AI..." -ForegroundColor Yellow
$ollamaRunning = $false
try {
    $resp = Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -TimeoutSec 3 -ErrorAction Stop
    $ollamaRunning = $true
    Write-Host "  Ollama running ✅" -ForegroundColor Green
} catch {
    Write-Host "  ⚠  Ollama not running. Start it with: ollama serve" -ForegroundColor Yellow
    Write-Host "     Then pull models: ollama pull llama3.2:3b && ollama pull nomic-embed-text" -ForegroundColor Yellow
}

# ── Done ─────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Setup complete! Start the app with:" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Backend:  .\.venv\Scripts\uvicorn backend.main:app --port 8000 --reload" -ForegroundColor White
Write-Host "  Frontend: cd frontend && pnpm dev" -ForegroundColor White
Write-Host ""
Write-Host "  App URL:  http://localhost:5173" -ForegroundColor Green
Write-Host "  API URL:  http://localhost:8000/docs" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

