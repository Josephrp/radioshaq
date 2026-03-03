"""
Export FastAPI OpenAPI schema to docs/api/openapi.json for MkDocs (API reference).
Run from repo root: python radioshaq/scripts/export_openapi.py
Or from radioshaq/: python scripts/export_openapi.py (with PYTHONPATH or install).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Repo root: radioshaq/scripts/export_openapi.py -> scripts -> radioshaq -> monorepo root
_script_dir = Path(__file__).resolve().parent
_radioshaq_root = _script_dir.parent  # package root (radioshaq/ containing radioshaq/*.py)
_repo_root = _radioshaq_root.parent   # monorepo root (containing docs/, radioshaq/)
if str(_radioshaq_root) not in sys.path:
    sys.path.insert(0, str(_radioshaq_root))

def main() -> None:
    from radioshaq.api.server import app

    out_dir = _repo_root / "docs" / "api"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "openapi.json"
    spec = app.openapi()
    out_file.write_text(json.dumps(spec, indent=2), encoding="utf-8")
    print(f"Wrote {out_file}")


if __name__ == "__main__":
    main()
