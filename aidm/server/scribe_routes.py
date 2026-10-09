"""`GET /api/scribe/lines`: the Scribe's lines for the UI (M13.2).

Every line of data/voice/scribe.json as `{id, group, text, audio_url}` (file order), so the phone
tab can show his in-character explanation (in combat, no funds, nobody fallen) without a round
trip. `audio_url` is "" while the voice build has not made the line's file. Texts only: the voice
settings and the sound chain stay on the server.

Public API: `add_scribe_routes`.
"""

from pathlib import Path

from fastapi import FastAPI

from aidm.data.scribe_lines import audio_url, scribe_lines


def add_scribe_routes(app: FastAPI, static_dir: Path) -> None:
    @app.get("/api/scribe/lines")
    def lines() -> list[dict[str, str]]:
        return [
            {
                "id": line.id,
                "group": line.group.value,
                "text": line.display,
                "audio_url": audio_url(line.id, static_dir),
            }
            for line in scribe_lines().lines
        ]
