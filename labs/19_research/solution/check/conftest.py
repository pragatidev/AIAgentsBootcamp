from __future__ import annotations

import sys
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]
COURSE = None
for parent in [Path.cwd(), *Path(__file__).resolve().parents]:
    if (parent / "config.py").is_file() and (parent / "research_agent").is_dir():
        COURSE = parent
        break
if COURSE is not None:
    sys.path.insert(0, str(COURSE))
sys.path.insert(0, str(PKG))
