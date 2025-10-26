"""Ensure the project root is importable when running commands from backend/."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def _ensure_project_root() -> None:
    backend_dir = Path(__file__).resolve().parent
    project_root = backend_dir.parent

    # Prepend so local modules win over globally installed packages with same name.
    project_root_str = str(project_root)
    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)


_ensure_project_root()
