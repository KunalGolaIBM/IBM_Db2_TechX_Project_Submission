"""AsOf entry point: the REST API and the web UI.

    python src/main.py                    # http://127.0.0.1:8000 (UI), /docs (API)
    python src/main.py --port 8080        # any option of `python -m asof.api`

Equivalent to `python -m asof.api`. Run `python -m asof.setup` once before the first start.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Works from a plain checkout too, before `pip install -e .`.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from asof.api import main  # noqa: E402

if __name__ == "__main__":
    main()
