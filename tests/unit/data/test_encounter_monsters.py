"""data/bg3/encounter_monsters.json: schema, curation rules and the candidate lookup (M3.9)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aidm.data.combat_data import combat_registries
from aidm.data.encounter_monsters import (
    DEFAULT_ENCOUNTER_MONSTERS,
    EncounterMonster,
    encounter_candidates,
    encounter_monsters,
    load_encounter_monsters,
    tier_for_cr,
)
from aidm.data.zone_templates import zone_templates
from aidm.rules.monster_catalog import monster_catalog

REGS = combat_registries()
ROLES = {"brute", "skirmisher", "artillery", "caster", "controller", "leader", "minion"}
ENTRIES = encounter_monsters().all()


def test_schema_and_count() -> None:
    raw = json.loads(DEFAULT_ENCOUNTER_MONSTERS.read_text(encoding="utf-8"))
    assert len(raw) == len(ENTRIES) >= 60
    assert all(isinstance(e, EncounterMonster) for e in ENTRIES)
    assert {e.role for e in ENTRIES} == ROLES
    assert {e.tier for e in ENTRIES} == {1, 2, 3}


def test_tags_are_zone_template_terrains() -> None:
    terrains = {t.index for t in zone_templates().all()}
    for entry in ENTRIES:
        assert set(entry.tags) <= terrains, entry.index
    assert {t for e in ENTRIES for t in e.tags} >= {
        "forest",
        "cave",
        "ruins",
        "swamp",
        "village",
        "keep",
        "bridge",
        "wilds",
        "crypt",
    }


@pytest.mark.parametrize("entry", ENTRIES, ids=[e.index for e in ENTRIES])
def test_entry_is_encounter_ready(entry: EncounterMonster) -> None:
    block = REGS.monsters.get(entry.index)
    assert block.challenge_rating == entry.cr <= 8
    assert tier_for_cr(block.challenge_rating) == entry.tier
    catalog = monster_catalog(block, REGS.monster_overlay, REGS.spells)
    assert [o for o in catalog.options if o.shape != "spell"]
    assert set(catalog.unsupported) == set(entry.cosmetic_unsupported)
    # No immunity to mundane weapons: a low-level party must be able to hurt it.
    assert not [s for s in block.damage_immunities if "nonmagical" in s]


def test_cosmetic_exceptions_are_few_and_never_signature_actions() -> None:
    excepted = {e.index: e.cosmetic_unsupported for e in ENTRIES if e.cosmetic_unsupported}
    assert len(excepted) <= 10
    for index, names in excepted.items():
        assert all(
            n.startswith("spell ") or n in {"Leadership", "Enlarge", "Invisibility"} for n in names
        ), index


def test_has_a_breath_dragon_and_casters() -> None:
    breathers = []
    for entry in ENTRIES:
        block = REGS.monsters.get(entry.index)
        catalog = monster_catalog(block, REGS.monster_overlay, REGS.spells)
        if block.type == "dragon" and any(o.shape == "save" for o in catalog.options):
            breathers.append(entry.index)
    assert len(breathers) >= 3
    casters = [e.index for e in ENTRIES if e.role == "caster"]
    assert len(casters) >= 2
    assert {"mage", "priest"} <= set(casters)
    assert any(REGS.monsters.get(i).is_spellcaster for i in casters)


def test_humanoid_and_type_spread() -> None:
    kinds = {REGS.monsters.get(e.index).type for e in ENTRIES}
    assert {"humanoid", "beast", "undead", "monstrosity", "fiend", "elemental", "dragon"} <= kinds
    for index in ("bandit", "cultist", "goblin", "hobgoblin", "orc", "gnoll", "kobold"):
        assert index in encounter_monsters()


def test_candidates_by_tier_and_tags() -> None:
    forest = encounter_candidates(1, ["forest"])
    assert forest and all(m.tier == 1 and "forest" in m.tags for m in forest)
    assert "goblin" in {m.index for m in forest}
    union = encounter_candidates(2, ["cave", "crypt"])
    assert all(set(m.tags) & {"cave", "crypt"} for m in union)
    assert len(encounter_candidates(3)) == sum(e.tier == 3 for e in ENTRIES)
    lower = encounter_candidates(2, ["cave"], include_lower=True)
    assert {m.tier for m in lower} == {1, 2}


def test_unknown_tags_fall_back_to_wilds() -> None:
    fallback = encounter_candidates(2, ["moonbase"])
    assert fallback and all("wilds" in m.tags and m.tier == 2 for m in fallback)


def test_loader_rejects_a_wrong_tier(tmp_path: Path) -> None:
    bad = [{"index": "ogre", "cr": 2, "tier": 3, "tags": ["cave"], "role": "brute"}]
    target = tmp_path / "bad.json"
    target.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(ValueError, match="tier"):
        load_encounter_monsters(target)


def test_loader_rejects_duplicates_and_cr_above_8(tmp_path: Path) -> None:
    row = {"index": "ogre", "cr": 2, "tier": 2, "tags": ["cave"], "role": "brute"}
    dup = tmp_path / "dup.json"
    dup.write_text(json.dumps([row, row]), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        load_encounter_monsters(dup)
    big = tmp_path / "big.json"
    big.write_text(json.dumps([{**row, "cr": 9, "tier": 3}]), encoding="utf-8")
    with pytest.raises(ValueError, match="cr"):
        load_encounter_monsters(big)
