"""Spell DSL data: every data/bg3/spells/*.json entry validates and agrees with the SRD."""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest
from pydantic import ValidationError

from aidm.data.condition_defs import condition_defs
from aidm.data.spell_defs import (
    AcBuffEffect,
    ApplyConditionEffect,
    AttackRollEffect,
    DamageEffect,
    Effect,
    HealEffect,
    MultiTargetEffect,
    RemoveConditionEffect,
    SaveEffect,
    SpellDef,
    SurfaceEffect,
    TempHpEffect,
    load_spell_defs,
    spell_defs,
)
from aidm.data.srd import srd
from aidm.data.surface_defs import surface_defs
from aidm.rules.dice import parse_dice

CASTING_TIME = {
    "1 action": "action",
    "1 bonus action": "bonus_action",
    "1 reaction": "reaction",
    "10 minutes": "minutes",
}


def _walk(effects: Sequence[Effect]) -> Iterator[Effect]:
    for effect in effects:
        yield effect
        if isinstance(effect, AttackRollEffect):
            yield from _walk(effect.on_hit)
        elif isinstance(effect, SaveEffect):
            yield from _walk(effect.on_fail)
            if not isinstance(effect.on_success, str):
                yield from _walk(effect.on_success)
        elif isinstance(effect, MultiTargetEffect):
            yield from _walk(effect.effects)


def test_reference_spells_are_shipped() -> None:
    expected = {
        "fire-bolt", "sacred-flame", "eldritch-blast", "magic-missile", "cure-wounds",
        "healing-word", "bless", "burning-hands", "hold-person", "shield-of-faith",
    }
    assert expected <= {s.index for s in spell_defs().all()}


@pytest.mark.parametrize("spell", spell_defs().all(), ids=lambda s: s.index)
def test_spell_matches_srd(spell: SpellDef) -> None:
    entry = srd().spells.get(spell.index)
    assert spell.level == entry.level
    assert spell.concentration == entry.concentration
    assert spell.school == entry.school.index
    assert spell.casting_time == CASTING_TIME[entry.casting_time]
    known_classes = {c.index for c in srd().classes.all()}
    assert set(spell.classes) <= known_classes


@pytest.mark.parametrize("spell", spell_defs().all(), ids=lambda s: s.index)
def test_spell_references_resolve(spell: SpellDef) -> None:
    conditions = condition_defs()
    for effect in _walk(spell.effects):
        if isinstance(effect, (ApplyConditionEffect, AcBuffEffect)):
            assert effect.condition in conditions
        if isinstance(effect, AcBuffEffect):
            assert conditions.get(effect.condition).ac_bonus > 0
        if isinstance(effect, RemoveConditionEffect):
            assert all(name in conditions for name in effect.conditions)
        if isinstance(effect, SurfaceEffect):
            assert effect.surface in surface_defs()
        if isinstance(effect, (DamageEffect, HealEffect, TempHpEffect)):
            parse_dice(effect.dice)
            if effect.upcast_dice:
                parse_dice(effect.upcast_dice)


def _write(tmp_path: Path, name: str, data: dict[str, object]) -> Path:
    (tmp_path / f"{name}.json").write_text(json.dumps(data), encoding="utf-8")
    return tmp_path


BASE: dict[str, object] = {
    "index": "fire-bolt", "level": 0, "school": "evocation", "classes": ["wizard"],
    "range": {"kind": "feet", "feet": 120}, "targeting": {"kind": "creature"},
    "effects": [{"type": "damage", "dice": "1d10", "damage_type": "fire"}],
}


def test_loader_requires_file_name_to_match_index(tmp_path: Path) -> None:
    bad = tmp_path / "bad"
    bad.mkdir()
    with pytest.raises(ValueError, match="file name"):
        load_spell_defs(_write(bad, "other", BASE))
    ok = tmp_path / "ok"
    ok.mkdir()
    assert [s.index for s in load_spell_defs(_write(ok, "fire-bolt", BASE)).all()] == ["fire-bolt"]


@pytest.mark.parametrize(
    "patch",
    [
        {"range": {"kind": "feet"}},
        {"targeting": {"kind": "area"}},
        {"concentration": True},
        {"effects": [{"type": "explode", "dice": "1d6"}]},
        {"effects": [{"type": "damage", "dice": "1d6", "damage_type": "laser"}]},
        {"level": 1, "targeting": {"kind": "creatures", "count_by_character_level": {"5": 2}}},
        {"targeting": {"kind": "self"}},
    ],
)
def test_invalid_entries_are_rejected(patch: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        SpellDef.model_validate({**BASE, **patch})
