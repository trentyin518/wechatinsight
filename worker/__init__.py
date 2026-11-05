"""Background collection worker (reuses backend packages).

Run from the repo root:  python -m worker.main --once
or as a long-running scheduler:  python -m worker.main
"""

import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))
