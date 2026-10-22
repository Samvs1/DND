"""`GET /api/tips` (M28.1): every tooltip text as static JSON, built once by `aidm.rules.explain`.

Body: `{"tips": {"<kind>:<id>": {"title": str, "lines": [str, ...]}}}`. The client caches it.

Public API: `add_tip_routes(app)`.
"""

from fastapi import FastAPI

from aidm.rules.explain import tips_payload


def add_tip_routes(app: FastAPI) -> None:
    def tips() -> dict[str, dict[str, dict[str, object]]]:
        return {"tips": tips_payload()}

    app.add_api_route("/api/tips", tips, methods=["GET"], include_in_schema=False)
