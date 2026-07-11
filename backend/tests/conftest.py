"""
Test-scope only: makes `import shared...` resolve regardless of the CWD
pytest is invoked from. Production import resolution (how the eventual
FastAPI app finds shared/) is deferred to Steps 9-11 (DB layer / Alembic /
FastAPI skeleton), where the real entrypoint gets decided.
"""
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
