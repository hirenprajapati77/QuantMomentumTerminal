"""
Root conftest.py — ensures both ``app.X`` and ``backend.app.X`` import paths
work in the same pytest session regardless of which PYTHONPATH was set.

The unit tests use bare ``app.X`` imports (no backend prefix).
The integration tests use ``backend.app.X`` imports (canonical project path).

Both work when both the project root AND the backend/ subdirectory are on sys.path.
"""
import sys
from pathlib import Path

# Project root  → enables ``import backend.app.X``
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# backend/ dir  → enables ``import app.X``
backend_dir = project_root / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))
