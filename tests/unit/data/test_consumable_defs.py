"""Consumables data: every entry validates; healing potion tiers match SRD 5.1."""

from __future__ import annotations

import json

from aidm.data.combat_data import combat_registries
from aidm.data.consumable_defs import consumable_defs
from aidm.data.srd import DEFAULT_SRD_ROOT


def test_golden_healing_potion_tiers() -> None:
    # SRD 5.1 Potion of Healing table: common 2d4+2, greater 4d4+4, superior 8d4+8, supreme 10d4+20.
    heal = {c.index: c.heal for c in consumable_defs().all() if c.source.startswith("SRD")}
    assert heal == {
        "potion-of-healing": "2d4+2",
        "potion-of-healing-greater": "4d4+4",
        "potion-of-healing-superior": "8d4+8",
        "potion-of-healing-supreme": "10d4+20",
    }


def test_consumables_are_srd_magic_items() -> None:
    raw = json.loads((DEFAULT_SRD_ROOT / "magic_items.json").read_text(encoding="utf-8"))
    magic = {entry["index"] for entry in raw}
    srd_items = {c.index for c in consumable_defs().all() if c.source.startswith("SRD")}
    assert srd_items <= magic


def test_combat_registries_bundle() -> None:
    regs = combat_registries()
    assert regs.consumables.find("potion-of-healing") is not None
    assert regs.chars.features.find("sneak-attack") is not None
