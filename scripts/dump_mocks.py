"""Regenerate contracts/mocks/*.json from the live API.

    python -m foodos.ingest.seed
    python scripts/dump_mocks.py

Generated rather than hand-written, so the mocks C builds against can never
drift from what B actually returns. Re-run it whenever the contract changes
and tell C in the same breath.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from fastapi.testclient import TestClient  # noqa: E402

from foodos.api.app import app  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "contracts" / "mock"

ENDPOINTS = [
    ("health", "get", "/api/health", None),
    ("today", "get", "/api/today", None),
    ("attribution", "get", "/api/attribution", None),
    ("plan", "get", "/api/plan", None),
    ("plan.lambda-0", "get", "/api/plan?lambda=0", None),
    ("plan.lambda-3", "get", "/api/plan?lambda=3", None),
    ("frontier", "get", "/api/frontier", None),
    ("ledger", "get", "/api/ledger", None),
    ("rescue", "get", "/api/rescue", None),
    ("impact", "get", "/api/impact", None),
    ("tracks.retail", "get", "/api/tracks/retail", None),
    ("tracks.production", "get", "/api/tracks/production", None),
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    client = TestClient(app)
    written = []

    for name, method, url, payload in ENDPOINTS:
        response = getattr(client, method)(url, **({"json": payload} if payload else {}))
        response.raise_for_status()
        path = OUT / f"{name}.json"
        path.write_text(
            json.dumps(response.json(), indent=2, ensure_ascii=False), encoding="utf-8"
        )
        written.append(f"{path.name}  <-  {method.upper()} {url}")

    # Lifecycle endpoints mutate, so they are dumped last and against a
    # recommendation we know exists.
    today = client.get("/api/today").json()
    if today["recommendations"]:
        rec_id = today["recommendations"][0]["id"]
        for name, url, payload in [
            ("recommendations.accept", f"/api/recommendations/{rec_id}/accept", None),
            (
                "recommendations.override",
                f"/api/recommendations/{rec_id}/override",
                {"reason": "Friday footfall is always higher", "value": 72},
            ),
        ]:
            response = client.post(url, **({"json": payload} if payload else {}))
            response.raise_for_status()
            path = OUT / f"{name}.json"
            path.write_text(
                json.dumps(response.json(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            written.append(f"{path.name}  <-  POST {url}")

    print("\n".join(written))
    print(f"\n{len(written)} mocks written to {OUT}")
    print("Reseed before using these for anything but frontend mocking:")
    print("  python -m foodos.ingest.seed")


if __name__ == "__main__":
    main()
