"""`GET /tts/<hash>.mp3`: serves cached synthesized sentences only (M8.1).

The name must be 40 lowercase hex digits plus `.mp3` and the file must already be in the cache;
anything else is a 404. Nothing is rendered on request (the table pre-renders what it narrates).

Public API: `add_tts_routes`.
"""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from aidm.server.tts import valid_tts_name


def add_tts_routes(app: FastAPI, cache_dir: Path) -> None:
    root = cache_dir.resolve()

    @app.get("/tts/{name}")
    def tts_file(name: str) -> FileResponse:
        path = root / name
        if not valid_tts_name(name) or not path.is_file():
            raise HTTPException(status_code=404)
        return FileResponse(
            path, media_type="audio/mpeg", headers={"Cache-Control": "public, max-age=86400"}
        )
