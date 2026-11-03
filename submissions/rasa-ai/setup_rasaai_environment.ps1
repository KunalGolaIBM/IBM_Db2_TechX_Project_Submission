$ErrorActionPreference = "Stop"

Write-Host "RasaAI environment setup" -ForegroundColor Cyan
Write-Host "This script expects app.py and requirements.txt in the current project folder."
Write-Host ""

if (-not (Test-Path ".\app.py")) {
    throw "app.py was not found in the current folder. Open PowerShell in the RasaAI project folder first."
}
if (-not (Test-Path ".\requirements.txt")) {
    throw "requirements.txt was not found in the current folder."
}

Write-Host "Checking Python 3.12..."
py -3.12 --version
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Python 3.12 was not found through the Windows Python launcher." -ForegroundColor Yellow
    Write-Host "Install 64-bit Python 3.12, reopen PowerShell, and run this script again."
    Write-Host "Official downloads: https://www.python.org/downloads/"
    exit 1
}

$venvPath = ".\.venv312"
$pythonPath = Join-Path $venvPath "Scripts\python.exe"

if (Test-Path $venvPath) {
    Write-Host "Using existing .venv312 environment."
} else {
    Write-Host "Creating .venv312..."
    py -3.12 -m venv $venvPath
    if ($LASTEXITCODE -ne 0) { throw "Virtual environment creation failed." }
}

Write-Host "Upgrading pip..."
& $pythonPath -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed. See the error above." }

Write-Host "Installing project dependencies..."
& $pythonPath -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed. See the error above." }

Write-Host "Checking package imports..."
& $pythonPath -c "import numpy, cv2, mediapipe, streamlit, pypdf; print('NumPy', numpy.__version__); print('OpenCV', cv2.__version__); print('MediaPipe', mediapipe.__version__); print('Streamlit', streamlit.__version__); print('pypdf', pypdf.__version__)"
if ($LASTEXITCODE -ne 0) {
    throw "One or more package imports failed. Copy the full error output before changing package versions."
}

Write-Host ""
Write-Host "Setup checks passed." -ForegroundColor Green
Write-Host "To launch RasaAI, run:"
Write-Host '& ".\.venv312\Scripts\python.exe" -m streamlit run app.py' -ForegroundColor Cyan
