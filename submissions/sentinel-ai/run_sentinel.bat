@echo off
title SENTINEL AI - Defence Cybersecurity Intelligence System
color 0B
echo ===============================================================================
echo            SENTINEL AI: MIL-SPEC AGENTIC CYBERSECURITY PLATFORM
echo              Detect Early. Analyse Smartly. Defend Strongly.
echo ===============================================================================
echo.
echo [1/2] Checking Python environment...
set PYTHON_EXE=C:\Users\Pranav\AppData\Local\Programs\Python\Python314\python.exe
if not exist "%PYTHON_EXE%" (
    set PYTHON_EXE=python
)

echo [2/2] Starting SENTINEL AI on http://127.0.0.1:8000 ...
cd /d "%~dp0backend"
start http://127.0.0.1:8000
"%PYTHON_EXE%" main.py
pause
