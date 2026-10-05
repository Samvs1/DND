"""Asset resolution (Addendum A.3): the ONE server-side `asset_url(key)`.

A key resolves to the real file's `/static/...` URL when the manifest knows it and the file exists,
otherwise to a placeholder `/assets/placeholder/<kind>/<slug>.svg` (any unknown key gets the generic
one). Music and sfx never get a placeholder: a missing file resolves to "" (silence).

Public API: `AssetCatalog`, `asset_url`, `MANIFEST_PATH`, `WEB_ROOT`, `placeholder_url`.
"""

import json
import re
from pathlib import Path

from aidm.data.item_catalogue import item_catalogue
from aidm.data.spell_defs import spell_defs
from aidm.data.srd import srd
from aidm.server.asset_keys import AUDIO_KINDS, split_key

WEB_ROOT = Path(__file__).resolve().parent.parent / "web"
MANIFEST_RELATIVE = Path("static") / "assets" / "manifest.json"
MANIFEST_PATH = WEB_ROOT / MANIFEST_RELATIVE
SAFE_SLUG = re.compile(r"[^a-z0-9._-]")
MAX_SLUG = 80


def safe_slug(slug: str) -> str:
    return SAFE_SLUG.sub("-", slug.lower())[:MAX_SLUG] or "unknown"


def placeholder_url(key: str) -> str:
    kind, slug = split_key(key)
    return f"/assets/placeholder/{kind or 'asset'}/{safe_slug(slug)}.svg"


def placeholder_meta(kind: str, slug: str) -> dict[str, str]:
    """Data facts a placeholder needs beyond its slug (type and CR, school, category)."""
    if kind == "monster_token":
        monster = srd().monsters.find(slug)
        if monster is not None:
            return {"creature_type": monster.type, "cr": str(monster.challenge_rating)}
    if kind == "spell_icon":
        spell = spell_defs().find(slug)
        if spell is not None:
            return {"school": spell.school}
    if kind == "item_icon":
        item = item_catalogue().find(slug)
        if item is not None:
            return {"category": item.category.value}
    return {}


class AssetCatalog:
    """The manifest of one web root (re-read when the file changes) plus URL resolution."""

    def __init__(self, web_root: Path = WEB_ROOT) -> None:
        self.web_root = web_root
        self._manifest_file = web_root / MANIFEST_RELATIVE
        self._stamp: float | None = None
        self._entries: dict[str, dict[str, object]] = {}

    def entries(self) -> dict[str, dict[str, object]]:
        try:
            stamp = self._manifest_file.stat().st_mtime
        except OSError:
            self._stamp, self._entries = None, {}
            return self._entries
        if stamp != self._stamp:
            try:
                raw = json.loads(self._manifest_file.read_text(encoding="utf-8"))
                self._entries = raw if isinstance(raw, dict) else {}
            except (OSError, ValueError):
                self._entries = {}
            self._stamp = stamp
        return self._entries

    def real_file(self, key: str) -> str | None:
        """The manifest `file` of `key` when that file exists under static/, else None."""
        entry = self.entries().get(key)
        file = entry.get("file") if entry else None
        if isinstance(file, str) and (self.web_root / "static" / file).is_file():
            return file
        return None

    def url(self, key: str) -> str:
        file = self.real_file(key)
        if file is not None:
            return f"/static/{file}"
        if split_key(key)[0] in AUDIO_KINDS:
            return ""
        return placeholder_url(key)

    def urls(self) -> dict[str, str]:
        """Every manifest key with its resolved URL (what the frontend loads once)."""
        return {key: self.url(key) for key in sorted(self.entries())}


_DEFAULT: AssetCatalog | None = None


def asset_url(key: str, catalog: AssetCatalog | None = None) -> str:
    """The URL the UI uses for `key`: the real file, a placeholder SVG, or "" for missing audio."""
    global _DEFAULT
    if catalog is None:
        if _DEFAULT is None:
            _DEFAULT = AssetCatalog()
        catalog = _DEFAULT
    return catalog.url(key)
