#!/usr/bin/env bash
# =============================================================================
# Kisan Mitra (किसान मित्र) - One-Command Launch Script
# IBM Db2Hack 2026
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
export PYTHONPATH="$SCRIPT_DIR:${PYTHONPATH:-}"

echo "🌾 ======================================================"
echo "🌾 Starting Kisan Mitra (किसान मित्र) - IBM Db2 AI Assistant"
echo "🌾 ======================================================"

# 1. Check or activate Python virtual environment
if [ -d ".venv" ]; then
    echo "🐍 Activating virtual environment (.venv)..."
    source .venv/bin/activate
elif [ -n "$VIRTUAL_ENV" ]; then
    echo "🐍 Using active virtual environment ($VIRTUAL_ENV)..."
else
    echo "🐍 Creating Python 3 virtual environment..."
    python3 -m venv .venv
    source .venv/bin/activate
    pip install --prefer-binary -r requirements.txt
fi

# 2. Check configuration
if [ ! -f ".env" ]; then
    echo "⚙️ Creating default .env from .env.example..."
    cp .env.example .env
fi

# 3. Verify / Ingest data if not already done
if [ ! -f "data/docs/PM_KISAN_Guidelines.pdf" ]; then
    echo "📄 Generating official scheme PDF documents in data/docs/..."
    python ingest/create_official_docs.py
fi

if [ ! -f "db/kisan_mitra_db2.sqlite" ]; then
    echo "🌾 Ingesting Mandi prices into IBM Db2 storage..."
    python ingest/fetch_mandi.py --force-csv
    echo "🧠 Generating native Db2 vector embeddings and building vector store..."
    python ingest/build_vector_store.py
fi

# 4. Launch Streamlit Dashboard
echo "🚀 Launching Kisan Mitra Streamlit Dashboard on http://localhost:8501 ..."
streamlit run app/main.py --server.port 8501 --server.headless false
