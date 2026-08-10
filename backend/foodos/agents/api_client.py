"""Read-only client for Person B's API.

Person D calls Person B's endpoints. Person D does not edit Person B's files, does not
import from ``foodos.engine``, and does not touch the database. This module is the entire
seam between the two.

Built on ``urllib`` from the standard library rather than an HTTP package, because no HTTP
client is on the approved stack and this needs exactly one verb.

Until the contract is live, ``FixtureClient`` reads the same shapes out of
``contracts/mock/``, so the agent layer is testable and demoable before H20.

Owner: Person D.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Protocol

from .settings import MOCK_DIR, get_settings


class ApiError(Exception):
    """The API could not be reached, or answered with something unusable."""


class ApiSource(Protocol):
    def get(self, path: str, **params: Any) -> dict[str, Any]: ...


class FoodosApiClient:
    """Live client against a running FastAPI instance."""

    def __init__(self, base_url: str | None = None, timeout: float | None = None) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.api_base_url).rstrip("/")
        self.timeout = timeout or settings.request_timeout_s

    def get(self, path: str, **params: Any) -> dict[str, Any]:
        query = {k: v for k, v in params.items() if v is not None}
        url = f"{self.base_url}{path}"
        if query:
            url = f"{url}?{urllib.parse.urlencode(query)}"

        request = urllib.request.Request(url, headers={"Accept": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            raise ApiError(f"GET {url} -> HTTP {exc.code} {exc.reason}") from exc
        except urllib.error.URLError as exc:
            raise ApiError(
                f"GET {url} failed: {exc.reason}. Is the backend running "
                f"(uvicorn foodos.api.main:app --port 8000)?"
            ) from exc

        try:
            return json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ApiError(f"GET {url} returned invalid JSON: {payload[:200]}") from exc

    # --- the endpoints the agent layer reads --------------------------------
    def today(self) -> dict[str, Any]:
        return self.get("/api/today")

    def why(self) -> dict[str, Any]:
        return self.get("/api/why")

    def plan(self, lambda_: float = 0.5) -> dict[str, Any]:
        return self.get("/api/plan", **{"lambda": lambda_})

    def ledger(self) -> dict[str, Any]:
        return self.get("/api/ledger")

    def rescue(self, batch_id: str | None = None) -> dict[str, Any]:
        return self.get("/api/rescue", batch_id=batch_id)


class FixtureClient:
    """Reads ``contracts/mock/*.json``. Same shapes, no backend, no network.

    Person C builds the entire frontend against these fixtures until H22. The agent layer
    uses them for exactly the same reason: nobody waits for anybody.
    """

    #: path -> fixture filename. Update in one place when the contract freezes at H3.
    ROUTES = {
        "/api/today": "today.json",
        "/api/why": "why.json",
        "/api/plan": "plan.json",
        "/api/ledger": "ledger.json",
        "/api/rescue": "rescue.json",
    }

    def __init__(self, directory: Path | str | None = None) -> None:
        self.directory = Path(directory) if directory else MOCK_DIR

    def get(self, path: str, **params: Any) -> dict[str, Any]:
        try:
            filename = self.ROUTES[path]
        except KeyError:
            raise ApiError(f"no fixture mapped for {path}") from None
        file = self.directory / filename
        if not file.exists():
            raise ApiError(
                f"fixture {file} not found. Copy contracts/mock/ into place, or point "
                f"--fixture at a directory that has it."
            )
        return json.loads(file.read_text(encoding="utf-8"))

    def today(self) -> dict[str, Any]:
        return self.get("/api/today")

    def why(self) -> dict[str, Any]:
        return self.get("/api/why")

    def plan(self, lambda_: float = 0.5) -> dict[str, Any]:
        return self.get("/api/plan", **{"lambda": lambda_})

    def ledger(self) -> dict[str, Any]:
        return self.get("/api/ledger")

    def rescue(self, batch_id: str | None = None) -> dict[str, Any]:
        return self.get("/api/rescue", batch_id=batch_id)
