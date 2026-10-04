"""Schema and SRD cross-reference tests for data/bg3/races.json (aidm.data.race_defs)."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import pytest
from pydantic import ValidationError

from aidm.data.race_defs import AbilityBonusDef, RaceDef, SubraceDef, race_defs
from aidm.data.srd import srd

SRD_RACES = (
    "dwarf",
    "elf",
    "halfling",
    "human",
    "dragonborn",
    "gnome",
    "half-elf",
    "half-orc",
    "tiefling",
)


def _bonuses(entries: Iterable[AbilityBonusDef]) -> dict[str, int]:
    return {e.ability: e.bonus for e in entries}


def test_all_srd_races_and_subraces_covered() -> None:
    assert {r.index for r in race_defs().all()} == set(SRD_RACES)
    assert {r.index for r in srd().races.all()} == set(SRD_RACES)
    defined = {s.index for r in race_defs().all() for s in r.subraces}
    assert defined == {s.index for s in srd().subraces.all()}
    assert len(defined) == 4


@pytest.mark.parametrize("key", SRD_RACES)
def test_race_matches_srd(key: str) -> None:
    d = race_defs().get(key)
    s = srd().races.get(key)
    assert (d.name, d.speed, d.size) == (s.name, s.speed, s.size)
    srd_bonuses = {b.ability_score.index: b.bonus for b in s.ability_bonuses}
    assert _bonuses(d.ability_bonuses) == srd_bonuses
    assert d.languages == tuple(item.index for item in s.languages)
    assert d.traits == tuple(t.index for t in s.traits)
    assert tuple(sub.index for sub in d.subraces) == tuple(r.index for r in s.subraces)
    options = s.language_options
    assert d.language_choices == (options["choose"] if isinstance(options, dict) else 0)


@pytest.mark.parametrize("key", SRD_RACES)
def test_subraces_match_srd(key: str) -> None:
    for sub in race_defs().get(key).subraces:
        s = srd().subraces.get(sub.index)
        assert s.race.index == key and sub.name == s.name
        srd_bonuses = {b.ability_score.index: b.bonus for b in s.ability_bonuses}
        assert _bonuses(sub.ability_bonuses) == srd_bonuses
        assert sub.traits == tuple(t.index for t in s.racial_traits)


def test_trait_ids_exist() -> None:
    for race in race_defs().all():
        for entry in (race, *race.subraces):
            for trait in entry.traits:
                assert trait in srd().traits, trait


def test_darkvision_matches_trait_and_srd_text() -> None:
    for race in race_defs().all():
        assert (race.darkvision > 0) == ("darkvision" in race.traits), race.index
    # SRD 5.1 Darkvision trait: "within 60 feet".
    assert "60 feet" in srd().traits.get("darkvision").desc[0]
    with_dv = {r.index for r in race_defs().all() if r.darkvision}
    assert with_dv == {"dwarf", "elf", "gnome", "half-elf", "half-orc", "tiefling"}
    assert all(r.darkvision in (0, 60) for r in race_defs().all())


def test_granted_proficiencies_match_srd_traits() -> None:
    for race in race_defs().all():
        entries = (race, *race.subraces)
        trait_profs = {
            p.index for e in entries for t in e.traits for p in srd().traits.get(t).proficiencies
        }
        granted = {
            *(f"skill-{s}" for e in entries for s in e.skills),
            *(w for e in entries for w in e.weapon_proficiencies),
            *(t for e in entries for t in e.tool_proficiencies),
        }
        assert granted == trait_profs, race.index
        for e in entries:
            assert all(s in srd().skills for s in e.skills)
            assert all(w in srd().proficiencies for w in e.weapon_proficiencies)
            assert all(t in srd().proficiencies for t in e.tool_proficiencies)


def test_dwarf_tool_choice_matches_srd() -> None:
    choice: Any = srd().traits.get("tool-proficiency").proficiency_choices
    expected = {o["item"]["index"] for o in choice["from"]["options"]}
    dwarf = race_defs().get("dwarf").tool_choice
    assert dwarf is not None and set(dwarf.options) == expected and dwarf.choose == 1
    assert all(o in srd().proficiencies for o in dwarf.options)


def test_golden_half_elf_ability_choice() -> None:
    # SRD 5.1 Half-Elf: +2 CHA and two other ability scores of your choice +1 each.
    h = race_defs().get("half-elf")
    assert _bonuses(h.ability_bonuses) == {"cha": 2}
    assert h.ability_choice is not None
    assert (h.ability_choice.choose, h.ability_choice_bonus) == (2, 1)
    assert set(h.ability_choice.options) == {"str", "dex", "con", "int", "wis"}
    assert h.skill_choice is not None and h.skill_choice.choose == 2
    assert h.language_choices == 1


def test_golden_race_numbers() -> None:
    # SRD 5.1 racial traits: dwarf speed 25 and +2 CON, hill dwarf +1 WIS; human +1 to all six;
    # halfling Small; dragonborn +2 STR +1 CHA.
    dwarf = race_defs().get("dwarf")
    assert dwarf.speed == 25 and _bonuses(dwarf.ability_bonuses) == {"con": 2}
    assert _bonuses(dwarf.subraces[0].ability_bonuses) == {"wis": 1}
    assert sum(_bonuses(race_defs().get("human").ability_bonuses).values()) == 6
    assert race_defs().get("halfling").size == "Small"
    assert _bonuses(race_defs().get("dragonborn").ability_bonuses) == {"str": 2, "cha": 1}


def test_high_elf_extras() -> None:
    sub = race_defs().get("elf").subraces[0]
    assert sub.cantrip_choices == 1 and sub.language_choices == 1


def test_schema_rejects_bad_input() -> None:
    with pytest.raises(ValidationError):
        RaceDef.model_validate({"index": "x", "name": "X", "size": "Medium", "speed": 30, "nope": 1})
    with pytest.raises(ValidationError):
        RaceDef.model_validate({"index": "x", "name": "X", "size": "Huge", "speed": 30})
    bad = {"index": "x", "name": "X", "ability_bonuses": [{"ability": "luck", "bonus": 1}]}
    with pytest.raises(ValidationError):
        SubraceDef.model_validate(bad)
