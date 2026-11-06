"""
Convenience Launcher for SmartStock AI.
Allows starting both the FastAPI backend and Streamlit frontend.
"""

import subprocess
import sys
import time
import os
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent

def launch():
    print("=" * 60)
    print("🚀 Launching SmartStock AI Platform")
    print("=" * 60)
    
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{SRC_DIR}{os.pathsep}{existing_pythonpath}" if existing_pythonpath else str(SRC_DIR)

    print("1. Starting FastAPI Backend on http://127.0.0.1:8000...")
    backend = subprocess.Popen([
        sys.executable, "-m", "uvicorn", "backend.main:app",
        "--host", "127.0.0.1", "--port", "8000"
    ], cwd=str(SRC_DIR), env=env)

    time.sleep(2)

    print("2. Launching Streamlit Frontend on http://localhost:8501...")
    try:
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", "frontend/app.py"
        ], cwd=str(SRC_DIR), env=env)
    except KeyboardInterrupt:
        pass
    finally:
        print("\nShutting down backend...")
        backend.terminate()

if __name__ == "__main__":
    launch()
