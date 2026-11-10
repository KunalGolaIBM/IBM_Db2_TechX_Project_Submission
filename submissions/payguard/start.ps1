# PayGuard one-click launcher for Windows.
# Run by double-clicking start.bat (or: powershell -ExecutionPolicy Bypass -File start.ps1)
Set-Location $PSScriptRoot

function Fail($msg) { Write-Host "`nERROR: $msg" -ForegroundColor Red; Read-Host "Press Enter to close"; exit 1 }

# 1. .env
if (!(Test-Path .env)) {
    Copy-Item .env.example .env
    Write-Host "Created .env. Paste your Gemini key after GEMINI_API_KEY= , save, close Notepad." -ForegroundColor Yellow
    Start-Process notepad .env -Wait
}

# 2. Python environment
if (!(Get-Command python -ErrorAction SilentlyContinue)) { Fail "Python is not installed or not on PATH." }
if (!(Test-Path .venv)) { Write-Host "Creating Python environment..."; python -m venv .venv }
$py = ".\.venv\Scripts\python.exe"
Write-Host "Installing Python packages (first time takes a few minutes)..."
& $py -m pip install -q --disable-pip-version-check -r requirements.txt
if ($LASTEXITCODE -ne 0) { Fail "pip install failed. Scroll up for the reason." }

# 3. Db2 in Docker
cmd /c "docker info >nul 2>&1"
if ($LASTEXITCODE -ne 0) { Fail "Docker is not running. Open Docker Desktop, wait until it says 'Engine running', then start again." }
Write-Host "Starting Db2 (first time downloads a large image)..."
cmd /c "docker compose up -d"
if ($LASTEXITCODE -ne 0) { Fail "docker compose failed. Scroll up for the reason." }

Write-Host "Waiting for Db2 to finish setting up (5-10 minutes the first time)" -NoNewline
$deadline = (Get-Date).AddMinutes(25)
while ($true) {
    $logs = cmd /c "docker logs payguard-db2 2>&1"
    if ($logs -match "Setup has completed") { break }
    if ((Get-Date) -gt $deadline) { Fail "Db2 did not finish in 25 minutes. Run: docker logs payguard-db2" }
    Write-Host "." -NoNewline
    Start-Sleep 15
}
Write-Host " ready." -ForegroundColor Green

# 4. Tables + knowledge base (only loads if empty)
& $py src\seed.py
if ($LASTEXITCODE -ne 0) { Fail "Seeding Db2 failed. Scroll up for the reason." }

# 5. App
Write-Host "`nPayGuard is starting at http://localhost:8000  (Ctrl+C to stop)" -ForegroundColor Green
Start-Process "http://localhost:8000"
& $py -m uvicorn main:app --app-dir src --port 8000
