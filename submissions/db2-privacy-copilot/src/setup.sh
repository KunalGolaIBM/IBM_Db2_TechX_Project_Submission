#!/bin/bash
# Setup script for Db2 Privacy Copilot
# This script sets up the development environment on Unix-like systems

set -e

echo "========================================"
echo "Db2 Privacy Copilot - Setup Script"
echo "========================================"
echo

# Check if .env exists
if [ ! -f .env ]; then
    echo "Creating .env file from .env.example..."
    cp .env.example .env
    echo "✓ .env created"
    echo
    echo "⚠️  IMPORTANT: Edit .env and set a strong DB2_PASSWORD"
    echo
else
    echo "✓ .env already exists"
fi

# Create Python virtual environment
if [ ! -d .venv ]; then
    echo "Creating Python virtual environment..."
    python3.11 -m venv .venv || python3 -m venv .venv || python -m venv .venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate || . .venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "Installing dependencies..."
pip install -e ".[dev,ui]"
echo "✓ Dependencies installed"

echo
echo "========================================"
echo "Setup complete!"
echo "========================================"
echo
echo "Next steps:"
echo "  1. Edit .env and set DB2_PASSWORD and API_SECRET_KEY"
echo "  2. Start the local stack: docker compose --profile app up -d"
echo "  3. Wait until Db2 is healthy: docker compose ps"
echo "  4. Initialize database: docker compose exec api python -m app.bootstrap"
echo "  5. Seed synthetic data: docker compose exec api python -m eval.seed"
echo "  6. Open the UI: http://localhost:8501"
echo "  7. Run host tests: pytest -q"
echo
