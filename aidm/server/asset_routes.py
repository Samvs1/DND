"""Asset routes: `/assets/placeholder/<kind>/<slug>.svg` and `/api/assets/manifest` (Addendum A.3).

Public API: `add_asset_routes`.
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response

from aidm.server.assets import AssetCatalog, placeholder_meta, safe_slug
from aidm.server.placeholders import render_placeholder

PLACEHOLDER_CACHE = "public, max-age=86400, immutable"


def add_asset_routes(app: FastAPI, catalog: AssetCatalog) -> None:
    @app.get("/assets/placeholder/{kind}/{slug}.svg")
    def placeholder(kind: str, slug: str) -> Response:
        clean = safe_slug(slug)
        svg = render_placeholder(kind, clean, placeholder_meta(kind, clean))
        return Response(
            svg, media_type="image/svg+xml", headers={"Cache-Control": PLACEHOLDER_CACHE}
        )

    @app.get("/api/assets/manifest")
    def manifest() -> JSONResponse:
        return JSONResponse(catalog.urls(), headers={"Cache-Control": "no-cache"})
