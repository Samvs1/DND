"""The FastAPI app (SPEC 4): static hosting, `/ws`, `/healthz`, LAN helpers (M6.4).

`create_app(settings)` builds the app; its lifespan creates the one `LlmClient` (FakeLLM when
`AIDM_FAKE_LLM=1`), the `TableRegistry` and the table tasks, and closes them at shutdown.
Tests may pass `llm`, `state` or `config` to start from a prepared table.

Routes: `/`, `/play`, `/screen` (the web shell), `/static/*` and `/web/*` (files of `aidm/web`),
`/ws`, `/healthz` (booleans only), `/api/saves`, `/api/lan`, `/api/lan-qr.svg`,
`/assets/placeholder/<kind>/<slug>.svg` and `/api/assets/manifest` (asset_routes.py, A1),
`/api/creation-data` (creation_data.py, M7.2), `/tts/<hash>.mp3` (tts_routes.py, M8.1).
`settings.web_root` (env `AIDM_WEB_ROOT`) serves another copy of `aidm/web` (A3).

Public API: `create_app`, `WEB_DIR`.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from aidm.dm.llm_client import LlmClient
from aidm.dm.llm_factory import make_llm_client
from aidm.dm.llm_log import LlmCallLog
from aidm.models.state import GameState
from aidm.server.asset_routes import add_asset_routes
from aidm.server.assets import AssetCatalog
from aidm.server.creation_data import add_creation_routes
from aidm.server.lan import qr_svg
from aidm.server.registry import TableRegistry
from aidm.server.scribe_routes import add_scribe_routes
from aidm.server.settings import ServerSettings
from aidm.server.tts_routes import add_tts_routes
from aidm.server.ws import serve_socket
from aidm.session.table_core import TableConfig

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
PLACEHOLDER = "<!doctype html><title>AI Dungeon Master</title><h1>AI Dungeon Master</h1>"


def create_app(
    settings: ServerSettings,
    *,
    llm: LlmClient | None = None,
    state: GameState | None = None,
    campaign_id: str | None = None,
    config: TableConfig | None = None,
) -> FastAPI:
    client = llm or make_llm_client(settings.llm, LlmCallLog(settings.llm.log_path))
    registry = TableRegistry(settings, client, state=state, campaign_id=campaign_id, config=config)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        await client.discover_models()
        await registry.start()
        try:
            yield
        finally:
            await registry.stop()

    app = FastAPI(title="aidm", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.registry = registry
    app.state.settings = settings
    web_dir = settings.web_root or WEB_DIR
    _add_pages(app, web_dir)
    _add_api(app, settings, registry, client)
    add_asset_routes(app, AssetCatalog(web_dir))
    add_creation_routes(app)
    add_tts_routes(app, settings.fish.cache_dir)
    add_scribe_routes(app, web_dir / "static")
    return app


def _add_pages(app: FastAPI, web_dir: Path) -> None:
    def index() -> Response:
        page = web_dir / "index.html"
        if page.is_file():
            return FileResponse(page)
        return HTMLResponse(PLACEHOLDER)

    for route in ("/", "/play", "/screen"):
        app.add_api_route(route, index, methods=["GET"], include_in_schema=False)
    for prefix, folder in (("/static", web_dir / "static"), ("/web", web_dir)):
        if folder.is_dir():
            app.mount(prefix, StaticFiles(directory=folder), name=prefix.strip("/"))


def _add_api(
    app: FastAPI, settings: ServerSettings, registry: TableRegistry, client: LlmClient
) -> None:
    @app.websocket("/ws")
    async def ws(socket: WebSocket) -> None:
        await serve_socket(socket, registry)

    @app.get("/healthz")
    def healthz() -> dict[str, object]:
        return {
            "ok": True,
            "deepseek": settings.llm.has_key and client.available,
            "fish": settings.fish_ready,
            "tts_enabled": registry.table.tts_enabled,
            "version": settings.version,
        }

    @app.get("/api/saves")
    def saves() -> list[dict[str, object]]:
        return [
            {"campaign_id": s.campaign_id, "seq": s.seq, "saved_at": s.saved_at}
            for s in registry.list_saves()
        ]

    @app.get("/api/lan")
    def lan() -> dict[str, object]:
        return {"lan": settings.lan_url is not None, "url": settings.lan_url}

    @app.get("/api/lan-qr.svg")
    def lan_qr() -> Response:
        if settings.lan_url is None:
            raise HTTPException(status_code=404)
        return Response(qr_svg(settings.lan_url), media_type="image/svg+xml")
