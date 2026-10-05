"""The frontend references art only through assets.js (Addendum A.5, grep-style)."""

import re
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent.parent / "aidm" / "web"
FORBIDDEN = re.compile(
    r"/static/(?:img|audio)|\bimg/(?:portraits|icons|ui|monsters|zones)\b|\.(?:png|jpe?g|webp|mp3)\b"
)


def _sources() -> list[Path]:
    files = [*(WEB / "js").rglob("*.js"), *(WEB / "css").rglob("*.css"), WEB / "index.html"]
    return [f for f in files if f.name != "assets.js"]


def test_no_hardcoded_image_or_audio_paths_outside_assets_js() -> None:
    offenders = [
        f"{path.relative_to(WEB)}: {match.group(0)}"
        for path in _sources()
        for match in FORBIDDEN.finditer(path.read_text(encoding="utf-8"))
    ]
    assert offenders == []


def test_ui_code_asks_assets_js_for_art() -> None:
    source = (WEB / "js" / "assets.js").read_text(encoding="utf-8")
    assert "export function assetUrl" in source and "/api/assets/manifest" in source
