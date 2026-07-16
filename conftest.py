"""
Ensures the project root is on sys.path so `from app.xxx import yyy` works
in tests regardless of how pytest is invoked or whether the project is
installed in editable mode. Without this, a fresh environment (like a
clean CI checkout) can fail with `ModuleNotFoundError: No module named 'app'`
even though the exact same tests pass locally.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.resolve()

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))