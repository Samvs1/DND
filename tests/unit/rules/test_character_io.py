"""Character JSON export/import (SPEC 8): round trip for the six golden builds, typed refusals,
and re-derivation of tampered stats (docs/DECISIONS.md M2.6)."""

from __future__ import annotations

import json
from typing import Any

import pytest

from aidm.models.creation import CreationErrorCode
from aidm.models.state import Creature, CreatureKind
from aidm.rules.character_io import CharacterImportInvalid, export_character, import_character
from tests.unit.rules.golden_builds import GOLDEN_CLASSES, REGS, golden_levels

E = CreationErrorCode


def _doc(class_index: str = "wizard", level: int = 5) -> dict[str, Any]:
    return json.loads(export_character(golden_levels(class_index)[level]))


def _import(doc: dict[str, Any]) -> Creature:
    return import_character(json.dumps(doc), REGS)


def _codes(doc: dict[str, Any] | str) -> list[E]:
    text = doc if isinstance(doc, str) else json.dumps(doc)
    with pytest.raises(CharacterImportInvalid) as info:
        import_character(text, REGS)
    return [e.code for e in info.value.errors]


@pytest.mark.parametrize("class_index", GOLDEN_CLASSES)
def test_round_trip_level_5_golden_build(class_index: str) -> None:
    original = golden_levels(class_index)[5]
    restored = import_character(export_character(original), REGS)
    assert restored.model_dump() == original.model_dump()


@pytest.mark.parametrize("class_index", GOLDEN_CLASSES)
def test_round_trip_every_level(class_index: str) -> None:
    for creature in golden_levels(class_index).values():
        assert import_character(export_character(creature), REGS) == creature


def test_export_is_json_with_format_and_version() -> None:
    doc = _doc("fighter", 1)
    assert (doc["format"], doc["version"]) == ("aidm.character", 1)
    assert doc["character"]["pc"]["class_index"] == "fighter"


def test_export_refuses_a_monster() -> None:
    monster = Creature(id="m", name="M", kind=CreatureKind.MONSTER, max_hp=1, hp=1)
    with pytest.raises(ValueError):
        export_character(monster)


def test_import_refuses_malformed_text_and_wrong_format() -> None:
    assert _codes("not json") == [E.IMPORT_INVALID]
    assert _codes('{"format": "other", "version": 1, "character": {}}')[0] is E.IMPORT_INVALID
    doc = _doc("fighter", 1)
    doc["version"] = 2
    assert _codes(doc) == [E.IMPORT_INVALID]
    doc = _doc("fighter", 1)
    doc["character"]["surprise"] = 1
    assert _codes(doc) == [E.IMPORT_INVALID]


def test_import_refuses_a_non_pc() -> None:
    doc = _doc("fighter", 1)
    doc["character"]["pc"] = None
    assert _codes(doc) == [E.NOT_A_PC]


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("race", "gnoll", E.UNKNOWN_RACE),
        ("class_index", "artificer", E.UNKNOWN_CLASS),
        ("background", "pirate-king", E.UNKNOWN_BACKGROUND),
        ("subrace", "hill-dwarf", E.UNKNOWN_SUBRACE),
        ("subclass", "tempest", E.SUBCLASS_INVALID),
        ("level", 6, E.NOT_ENOUGH_XP),
        ("xp", 0, E.NOT_ENOUGH_XP),
    ],
)
def test_import_refuses_unknown_or_impossible_references(
    field: str, value: object, code: E
) -> None:
    doc = _doc("wizard", 5)
    doc["character"]["pc"][field] = value
    assert code in _codes(doc)


def test_import_refuses_unknown_content_ids() -> None:
    doc = _doc("wizard", 5)
    pc = doc["character"]["pc"]
    pc["features"].append("godhood")
    pc["spellbook"].append("wish-upon-a-star")
    pc["inventory"].append({"item": "vorpal-greatsword", "qty": 1})
    assert _codes(doc).count(E.PICK_NOT_ALLOWED) == 3


def test_import_refuses_impossible_ability_scores() -> None:
    doc = _doc("fighter", 1)
    doc["character"]["abilities"]["str"] = 30
    assert E.SCORE_OUT_OF_RANGE in _codes(doc)
    doc = _doc("fighter", 1)
    for ability in doc["character"]["abilities"]:
        doc["character"]["abilities"][ability] = 20
    assert E.SCORE_OUT_OF_RANGE in _codes(doc)


def test_import_rederives_tampered_derived_stats() -> None:
    original = golden_levels("rogue")[5]
    doc = _doc("rogue", 5)
    sheet = doc["character"]
    sheet.update({"max_hp": 999, "hp": 999, "ac": 30, "proficiency_bonus": 9, "speed": 90})
    sheet.update({"save_proficiencies": [], "immunities": ["fire"], "resistances": ["acid"]})
    restored = _import(doc)
    assert restored.max_hp == original.max_hp == 38
    assert restored.hp == original.max_hp  # clamped to the recomputed maximum
    assert (restored.ac, restored.proficiency_bonus, restored.speed) == (15, 3, 30)
    assert restored.save_proficiencies == original.save_proficiencies
    assert restored.immunities == [] and restored.resistances == original.resistances


def test_import_clamps_inflated_resources() -> None:
    doc = _doc("wizard", 5)
    slot = doc["character"]["resources"]["spell-slot-3"]
    slot["maximum"], slot["current"] = 9, 9
    restored = _import(doc)
    assert (
        restored.resources["spell-slot-3"].current,
        restored.resources["spell-slot-3"].maximum,
    ) == (2, 2)


def test_import_keeps_spent_resources_and_damage() -> None:
    doc = _doc("wizard", 5)
    doc["character"]["resources"]["spell-slot-1"]["current"] = 1
    doc["character"]["hp"] = 10
    restored = _import(doc)
    assert restored.resources["spell-slot-1"].current == 1 and restored.hp == 10
