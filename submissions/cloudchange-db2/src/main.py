"""CloudChange Application Server Entrypoint.

Starts the FastAPI server with Uvicorn.
"""

import sys
from pathlib import Path
import uvicorn

# Ensure src/ is on sys.path
src_dir = Path(__file__).resolve().parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from backend.app.main import app

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

