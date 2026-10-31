"""Initialize CloudChange Schema in IBM Db2.

Run:
    python src/init_db2.py
"""

import sys
from pathlib import Path

src_dir = Path(__file__).resolve().parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from backend.app.db2.init_schema import main

if __name__ == "__main__":
    sys.exit(main())

