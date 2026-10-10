"""Live-manifest picks for asset tests.

Tests name a key by its status, never a fixed key, so installing new art cannot silently turn a
"placeholder" test into a real-art test (M12.2 filled most placeholders and broke the fixed picks).
Since 2026-10-10 every picture is real art, so picture-placeholder tests use `artless_manifest`:
the manifest `build_manifest` makes for a web root with no art at all.
"""

import json
from pathlib import Path
from typing import Any

from aidm.server.asset_keys import AUDIO_KINDS

MANIFEST_FILE = (
    Path(__file__).resolve().parent.parent / "aidm" / "web" / "static" / "assets" / "manifest.json"
)


def live_manifest() -> dict[str, dict[str, Any]]:
    return json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))


def image_placeholder(manifest: dict[str, dict[str, Any]] | None = None) -> str:
    """The first image key (not music or sfx) that is still on a placeholder."""
    entries = live_manifest() if manifest is None else manifest
    keys = sorted(
        key
        for key, entry in entries.items()
        if entry["status"] == "placeholder" and entry["kind"] not in AUDIO_KINDS
    )
    assert keys, "no image placeholder left in the manifest: point this test at a temp manifest"
    return keys[0]


VOICE_FILES = MANIFEST_FILE.parent.parent / "audio" / "voice" / "scribe"


def expected_audio_url(line_id: str) -> str:
    """The Scribe line URL rule: the mp3 path when the built file exists, else "" (text only)."""
    exists = (VOICE_FILES / f"{line_id}.mp3").is_file()
    return f"/static/audio/voice/scribe/{line_id}.mp3" if exists else ""


def artless_manifest(tmp_path: Path) -> dict[str, dict[str, Any]]:
    """The manifest of a web root without any art: every picture key is a placeholder."""
    from tests.unit.scripts.helpers import load_script

    web = tmp_path / "artless-web"
    (web / "static").mkdir(parents=True)
    built: dict[str, dict[str, Any]] = load_script("build_manifest").build_manifest(web)
    return built
