"""Write the API's OpenAPI schema for the web app's generated types (task #83).

    python -m api.export_openapi        # → web/src/api/openapi.json (then `npm run gen:types` in web/)
"""
from __future__ import annotations

import json
from pathlib import Path

from api.main import app

OUT = Path(__file__).resolve().parents[1] / "web" / "src" / "api" / "openapi.json"


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(app.openapi(), indent=1, ensure_ascii=False) + "\n")
    print(f"openapi → {OUT} ({len(app.openapi()['paths'])} paths)")


if __name__ == "__main__":
    main()
