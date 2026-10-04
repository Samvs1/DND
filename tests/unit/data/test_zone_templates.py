"""data/bg3/zone_templates.json validates and covers the terrain tags the DM uses."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aidm.data.zone_templates import (
    FALLBACK_TERRAIN,
    MIN_TEMPLATE_ZONES,
    load_zone_templates,
    zone_templates,
)

REQUIRED = ["wilds", "forest", "ruins", "bridge", "cave", "village", "swamp", "keep"]


def test_every_required_terrain_exists() -> None:
    reg = zone_templates()
    for tag in REQUIRED:
        assert tag in reg
    assert FALLBACK_TERRAIN in reg


def test_every_terrain_mixes_cover_and_high_ground() -> None:
    for terrain in zone_templates().all():
        assert len(terrain.zones) >= MIN_TEMPLATE_ZONES
        assert any(z.cover != "none" for z in terrain.zones), terrain.index
        assert any(z.high_ground for z in terrain.zones), terrain.index
        assert all(z.names and all(n.isascii() for n in z.names) for z in terrain.zones)


def test_loader_requires_the_fallback(tmp_path: Path) -> None:
    raw = [t.model_dump() for t in zone_templates().all() if t.index != FALLBACK_TERRAIN]
    target = tmp_path / "zones.json"
    target.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="fallback"):
        load_zone_templates(target)


def test_loader_rejects_too_few_zones(tmp_path: Path) -> None:
    wilds = zone_templates().get(FALLBACK_TERRAIN).model_dump()
    wilds["zones"] = wilds["zones"][:2]
    target = tmp_path / "zones.json"
    target.write_text(json.dumps([wilds]), encoding="utf-8")
    with pytest.raises(ValueError, match="needs"):
        load_zone_templates(target)
