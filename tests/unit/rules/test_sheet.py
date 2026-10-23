"""Derived character sheet (SPEC 8): snapshot goldens for two builds plus cited spot checks.

Snapshots live in tests/unit/rules/goldens/; regenerate deliberately with
`$env:AIDM_UPDATE_GOLDENS="1"; pytest tests/unit/rules/test_sheet.py` and review the diff.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from aidm.data.character_data import character_registries
from aidm.models.abilities import Ability, Skill
from aidm.models.events import CreatureAdded
from aidm.models.sheet import CharacterSheet
from aidm.models.state import Creature, CreatureKind, GameState
from aidm.rules.creation import build_character
from aidm.rules.sheet import build_sheet
from aidm.session.reducer import apply
from tests.unit.rules.creation_fixtures import default_choices
from tests.unit.rules.leveling_fixtures import level_to

REGS = character_registries()
GOLDENS = Path(__file__).resolve().parent / "goldens"


def _snapshot(name: str, sheet: CharacterSheet) -> None:
    path = GOLDENS / f"{name}.json"
    data = sheet.model_dump(mode="json")
    if os.environ.get("AIDM_UPDATE_GOLDENS") == "1":
        path.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    assert data == json.loads(path.read_text(encoding="utf-8"))


def _fighter() -> Creature:
    return build_character(default_choices("fighter", "dwarf", "hill-dwarf"), REGS, "pc1")


def _wizard_l3() -> Creature:
    pc = build_character(default_choices("wizard", "elf", "high-elf"), REGS, "pc2")
    state = apply(GameState(campaign_id="c", seed=1), CreatureAdded(creature=pc))
    level_to(state, "pc2", 3, REGS, [])
    return state.creatures["pc2"]


def test_golden_sheet_hill_dwarf_fighter_l1() -> None:
    sheet = build_sheet(_fighter(), REGS)
    # M9.2: "gold" 0 -> 15 in both sheet goldens: the acolyte background purse (PHB 15 gp,
    # RULES_DECISIONS M9.2); nothing else in the snapshots changed.
    # M19.3: "keepsakes": [] (story objects the hero carries) joined both sheet goldens.
    # M27.6: "gear_uses": [] (fight uses of carried gear; none in these packs) joined both.
    # M27.7: "scroll_copies": [] (scrolls a wizard may copy; none carried) joined both.
    _snapshot("sheet_fighter_hill_dwarf_l1", sheet)
    # Chain mail 16 + shield 2 (SRD Armor table); HP 10 + 2 + Dwarven Toughness 1.
    assert (sheet.ac, sheet.max_hp, sheet.speed, sheet.initiative_bonus) == (18, 13, 25, 2)
    longsword, crossbow = sheet.attacks[0], sheet.attacks[1]
    # STR 15 (+2) + PB 2; one-handed with a shield: 1d8 + 2 slashing (SRD Weapons table).
    assert (longsword.attack_bonus, longsword.damage, longsword.range_band) == (4, "1d8+2", "melee")
    # DEX 14 (+2) + PB 2 + Archery 2; light crossbow 80/320.
    assert (crossbow.attack_bonus, crossbow.range_normal, crossbow.range_long) == (6, 80, 320)
    assert sheet.spellcasting is None and sheet.resistances == ["poison"]
    assert sheet.passive_perception == 10
    assert {r.key for r in sheet.resources} == {"second-wind"}


def test_golden_sheet_high_elf_wizard_l3() -> None:
    sheet = build_sheet(_wizard_l3(), REGS)
    # M3.6b: the default picks come from SHIPPED spells only, so the snapshot's cantrip and
    # spellbook indexes changed (Dancing Lights, Alarm... are hidden from pickers).
    # M29.9a T20: level-ups fill the prepared room from the book, so 4 spells are prepared
    # (the limit below) where the snapshot had kept the level 1 list.
    _snapshot("sheet_wizard_high_elf_l3", sheet)
    casting = sheet.spellcasting
    assert casting is not None
    # INT 12 + 1 = 13 (+1): DC 8 + 2 + 1 = 11, attack +3 (SRD Spellcasting Ability).
    assert (casting.ability, casting.save_dc, casting.attack_bonus) == (Ability.INT, 11, 3)
    assert casting.prepared_limit == 4  # INT mod 1 + wizard level 3
    prepared = [s for g in casting.levels for s in g.spells if s.prepared and not s.always_prepared]
    assert len(prepared) == 4
    assert len(casting.cantrips) == 3 + 1  # class cantrips + high elf cantrip
    slots = {g.level: [(s.current, s.maximum) for s in g.slots] for g in casting.levels}
    assert slots == {1: [(4, 4)], 2: [(2, 2)]}  # SRD Wizard table, 3rd level
    assert sum(len(g.spells) for g in casting.levels) == 6 + 2 * 2
    assert sheet.subclass == "evocation" and sheet.xp == 900 and sheet.xp_next == 2700
    perception = next(s for s in sheet.skills if s.skill is Skill.PERCEPTION)
    assert perception.proficient and perception.bonus == 0 + 2  # WIS 10, keen senses


def test_sheet_expertise_conditions_and_inventory() -> None:
    rogue = build_character(default_choices("rogue", "human", None), REGS, "r")
    sheet = build_sheet(rogue, REGS)
    expert = [s for s in sheet.skills if s.expertise]
    assert len(expert) == 2 and all(s.proficient for s in expert)
    worn = {line.equipped_slot for line in sheet.inventory if line.equipped_slot}
    assert {"armor", "main_hand"} <= worn
    off = next(a for a in sheet.attacks if a.hand == "off_hand")
    assert "+" not in off.damage  # SRD Two-Weapon Fighting: no positive modifier off-hand
    assert sheet.death_saves.successes == 0 and sheet.conditions == []
    sneak = next(f for f in sheet.features if f.index == "sneak-attack")
    assert sneak.source == "class" and sneak.name == "Sneak Attack"


def test_sheet_rejects_non_pc() -> None:
    monster = Creature(id="m", name="M", kind=CreatureKind.MONSTER, max_hp=1, hp=1)
    with pytest.raises(ValueError):
        build_sheet(monster, REGS)
