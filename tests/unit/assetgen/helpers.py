"""A tiny throwaway repo for asset generator tests: manifest, style references, v1 sheet."""

import json
from pathlib import Path
from typing import Any

from aidm.server.assetgen.prompts import PORTRAIT_REFS, SCENE_REFS, V1_SHEET
from aidm.server.assetgen.synthetic_png import synthetic_png

REPO_ROOT = Path(__file__).resolve().parents[3]
SENTINEL = "SENTINEL-KEY-0123456789-do-not-leak"


def _entry(kind: str, file: str, status: str, *, source: str = "", size: list[int] | None = None):
    transparent = kind not in ("portrait", "zone_card", "region_banner")
    return {
        "kind": kind,
        "file": file,
        "size": size or ([512, 512] if kind == "portrait" else [128, 128]),
        "transparent": transparent,
        "status": status,
        "prompt": "",
        "source": source,
        "license": "",
    }


def small_manifest() -> dict[str, dict[str, Any]]:
    return {
        "portrait.race.elf.f": _entry("portrait", "img/portraits/race_elf_f.png", "placeholder"),
        "portrait.class.wizard": _entry(
            "portrait", "img/portraits/wizard_cropped.png", "real", source="v1"
        ),
        "portrait.npc.werewolf-human": _entry(
            "portrait", "img/portraits/npc/werewolf-human.png", "placeholder"
        ),
        "portrait.npc.werewolf-wolf": _entry(
            "portrait", "img/portraits/npc/werewolf-wolf.png", "placeholder"
        ),
        "monster_token.goblin": _entry(
            "monster_token", "img/monsters/goblin.png", "placeholder", size=[256, 256]
        ),
        "monster_token.bandit": _entry(
            "monster_token", "img/monsters/bandit.png", "placeholder", size=[256, 256]
        ),
        "item_icon.tool": _entry("item_icon", "img/icons/items/tool.png", "placeholder"),
        "item_icon.weapon": _entry(
            "item_icon", "img/icons/equipment/weapon.png", "real", source="v1"
        ),
        "region_banner.tier1": _entry(
            "region_banner", "img/banners/tier1.png", "placeholder", size=[1024, 256]
        ),
        "zone_card.cave": _entry("zone_card", "img/zones/cave.png", "placeholder", size=[640, 360]),
        "condition_icon.asleep": _entry(
            "condition_icon", "img/icons/conditions/asleep.png", "placeholder"
        ),
        "sfx.hit": {**_entry("sfx", "audio/sfx/hit.mp3", "placeholder"), "size": None},
    }


def make_repo(root: Path, manifest: dict[str, dict[str, Any]] | None = None) -> Path:
    """Write the manifest and the reference images under `root`; returns the v1 root."""
    static = root / "aidm" / "web" / "static"
    target = static / "assets" / "manifest.json"
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps(manifest or small_manifest(), indent=1), encoding="utf-8")
    for rel in (*PORTRAIT_REFS, *SCENE_REFS):
        path = static / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(synthetic_png(8, 8, rel, sheet=False))
    v1_root = root / "v1"
    sheet = v1_root.joinpath(*V1_SHEET)
    sheet.parent.mkdir(parents=True)
    sheet.write_bytes(synthetic_png(16, 16, "v1 sheet", sheet=True))
    return v1_root


def read_text_tree(base: Path) -> str:
    """Every file under `base` decoded leniently, for leak checks."""
    if not base.exists():
        return ""
    parts = [
        p.read_bytes().decode("utf-8", "replace") for p in sorted(base.rglob("*")) if p.is_file()
    ]
    return "\n".join(parts)
