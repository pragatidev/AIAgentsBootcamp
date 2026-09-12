"""Start the thin DataFlow chat page. Port from DATAFLOW_UI_PORT (default 8000)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    import uvicorn

    host = os.environ.get("DATAFLOW_UI_HOST", "127.0.0.1")
    port = int(os.environ.get("DATAFLOW_UI_PORT", "8000"))
    uvicorn.run("dataflow.serve.app:app", host=host, port=port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
