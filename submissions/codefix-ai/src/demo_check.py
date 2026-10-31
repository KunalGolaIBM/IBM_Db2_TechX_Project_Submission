"""
CodeFix AI — Hackathon Readiness & System Verification Diagnostic Script

Run this script in PowerShell to verify your environment, dependencies,
local Ollama runtime, and IBM Db2 configuration before judging.
Usage:
    python demo_check.py
"""

import sys
import os
from pathlib import Path

def print_badge(label: str, status: bool, detail: str = ""):
    icon = "[PASS]" if status else "[WARN]"
    color_start = "\033[92m" if status else "\033[93m"
    color_end = "\033[0m"
    print(f" {color_start}{icon}{color_end} {label:<28} : {detail}")

def run_diagnostics():
    print("=" * 72)
    print("   CodeFix AI — Hackathon System Readiness & Verification Check   ")
    print("=" * 72)

    # 1. Python Environment Check
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    py_ok = sys.version_info >= (3, 10)
    print_badge("Python Runtime", py_ok, f"v{py_ver} (Requirement: >= 3.10)")

    # 2. Package Dependency Checks
    try:
        import importlib.metadata
        flask_ver = importlib.metadata.version("flask")
        print_badge("Flask Framework", True, f"v{flask_ver}")
    except Exception:
        print_badge("Flask Framework", False, "Missing! Run: pip install -r requirements.txt")

    try:
        import langchain
        import langchain_ollama
        print_badge("LangChain + Ollama", True, f"LangChain v{langchain.__version__}")
    except ImportError:
        print_badge("LangChain + Ollama", False, "Missing! Run: pip install -r requirements.txt")

    try:
        import ibm_db
        print_badge("IBM Db2 Driver (ibm_db)", True, f"v{ibm_db.__version__}")
    except ImportError:
        print_badge("IBM Db2 Driver (ibm_db)", False, "Missing! Run: pip install ibm_db")

    try:
        import pytest
        print_badge("Testing Framework (pytest)", True, f"v{pytest.__version__}")
    except ImportError:
        print_badge("Testing Framework (pytest)", False, "Missing! Run: pip install pytest")

    # 3. Environment & Configuration Check
    env_file = Path(__file__).resolve().parent / ".env"
    has_env = env_file.exists()
    print_badge(".env Configuration", has_env, "Configured" if has_env else "Missing .env! Copy from .env.example")

    from config import Config
    import agent_service
    import database
    import analyzer

    # 4. Ollama Local AI Check
    ollama_ok, ollama_msg, models = agent_service.check_ollama_status()
    print_badge("Ollama AI Service", ollama_ok, ollama_msg)
    if models:
        print(f"       -> Local models found: {', '.join(models)}")

    # 5. IBM Db2 Connectivity Check
    db2_configured = Config.is_db2_configured()
    if db2_configured:
        db2_conn_ok, db2_msg = database.check_db2_connection()
        print_badge("IBM Db2 Connection", db2_conn_ok, db2_msg)
    else:
        print_badge("IBM Db2 Mode", True, "Setup Mode Active (Mock interfaces ready; fill .env for live cloud)")

    # 6. AST Static Analyzer Sanity Check
    test_code = "def add(a, b):\n    return a + b\n"
    res = analyzer.analyze_code(test_code, "python")
    analyzer_ok = res.get("is_valid_syntax") is True and len(res.get("warnings", [])) == 0
    print_badge("AST Static Analyzer", analyzer_ok, "Deterministic syntax & construct validation operational")

    print("=" * 72)
    print("Verification complete.")
    print("To launch workspace: python app.py  (Opens on http://localhost:5000)")
    print("To run pytest suite: python -m pytest tests/ -v")
    print("=" * 72)

if __name__ == "__main__":
    run_diagnostics()
