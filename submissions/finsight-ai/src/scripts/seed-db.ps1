# ==============================================================================
# FinSight AI — Database Seed Runner (seed-db.ps1)
# ==============================================================================
param()
$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
uv run --python 3.12 "$ScriptDir\seed_database.py"
