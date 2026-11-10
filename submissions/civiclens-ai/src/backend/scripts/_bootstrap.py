"""Make the ``civiclens`` package importable when scripts are run directly."""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
SUBMISSION_DIR = BACKEND_DIR.parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
