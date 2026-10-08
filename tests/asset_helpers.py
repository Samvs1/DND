"""Live-manifest picks for asset tests.

Tests name a key by its status, never a fixed key, so installing new art cannot silently turn a
"placeholder" test into a real-art test (M12.2 filled most placeholders and broke the fixed picks).
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
