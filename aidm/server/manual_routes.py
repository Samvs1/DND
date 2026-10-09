"""The in-game player manual (M14.1): `/manual` (HTML shell) and `/api/manual` (the Markdown text).

The text is read from docs/PLAYER_MANUAL.md at request time, so an edit shows without a restart.
A missing file is a plain 404, never a crash.

Public API: `add_manual_routes(app, web_dir, manual_path=MANUAL_PATH)`.
"""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, Response

from aidm.data.manual_gen import MANUAL_PATH

PLACEHOLDER = "<!doctype html><title>Player manual</title><h1>Player manual</h1>"


def add_manual_routes(app: FastAPI, web_dir: Path, manual_path: Path = MANUAL_PATH) -> None:
    def page() -> Response:
        shell = web_dir / "manual.html"
        if shell.is_file():
            return FileResponse(shell)
        return HTMLResponse(PLACEHOLDER)

    def text() -> Response:
        try:
            body = manual_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise HTTPException(status_code=404, detail="manual not found") from exc
        return Response(body, media_type="text/markdown; charset=utf-8")

    app.add_api_route("/manual", page, methods=["GET"], include_in_schema=False)
    app.add_api_route("/api/manual", text, methods=["GET"], include_in_schema=False)
