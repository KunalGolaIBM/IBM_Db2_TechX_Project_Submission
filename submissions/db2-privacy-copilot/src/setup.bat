@echo off
REM Setup script for Db2 Privacy Copilot (Windows)

echo ========================================
echo Db2 Privacy Copilot - Setup Script
echo ========================================
echo.

REM Check if .env exists
if not exist .env (
    echo Creating .env file from .env.example...
    copy .env.example .env
    echo + .env created
    echo.
    echo WARNING: Edit .env and set a strong DB2_PASSWORD
    echo.
) else (
    echo + .env already exists
)

REM Create Python virtual environment
if not exist .venv (
    echo Creating Python virtual environment...
    python -m venv .venv
    echo + Virtual environment created
) else (
    echo + Virtual environment already exists
)

REM Activate virtual environment
echo Activating virtual environment...
call .venv\Scripts\activate.bat

REM Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip

REM Install dependencies
echo Installing dependencies...
pip install -e ".[dev,ui]"
echo + Dependencies installed

echo.
echo ========================================
echo Setup complete!
echo ========================================
echo.
echo Next steps:
echo   1. Edit .env and set DB2_PASSWORD and API_SECRET_KEY
echo   2. Start the local stack: docker compose --profile app up -d
echo   3. Wait until Db2 is healthy: docker compose ps
echo   4. Initialize database: docker compose exec api python -m app.bootstrap
echo   5. Seed synthetic data: docker compose exec api python -m eval.seed
echo   6. Open the UI: http://localhost:8501
echo   7. Run host tests: pytest -q
echo.
pause
