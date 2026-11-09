# ==============================================================================
# FinSight AI — Database Migration Runner (run-migrations.ps1)
# ==============================================================================
param()
$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
uv run --python 3.12 "$ScriptDir\run_migrations.py"
