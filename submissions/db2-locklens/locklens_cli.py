"""Run the LockLens CLI without installing the package or setting PYTHONPATH.

    python locklens_cli.py test-connection --wait 900
    python locklens_cli.py init-db
    python locklens_cli.py snapshot
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from locklens.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
