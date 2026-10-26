"""Schema tests for data/bg3/conditions.json (aidm.data.condition_defs)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from aidm.data.condition_defs import (
    ConditionDef,
    DefaultDuration,
    condition_defs,
    load_condition_defs,
)
from aidm.data.srd import srd
from aidm.models.abilities import Ability
from aidm.models.damage import DamageType


def test_every_srd_condition_is_defined() -> None:
    srd_keys = {c.index for c in srd().conditions.all()}
    assert len(srd_keys) == 15
    defined = {c.index for c in condition_defs().all() if c.srd_condition}
    assert defined == srd_keys


def test_extras_are_marked_non_srd() -> None:
    extras = {c.index for c in condition_defs().all() if not c.srd_condition}
    spell_extras = {"chilled", "shocked", "true-strike", "guided", "mage-armor", "blurred"}
    spell_extras |= {"invisibility", "slowed", "nauseated"}
    spell_extras |= {"guidance", "resistance", "bane", "longstrider", "barkskin", "poison-ward"}
    spell_extras |= {"hunters-mark", "expeditious-retreat", "asleep", "silenced"}
    spell_extras |= {"turned"}  # M7.5b: Channel Divinity: Turn Undead
    spell_extras |= {"burning"}  # M27.6: SRD Alchemist's Fire
    spell_extras |= {"befriended"}  # M29.7d: Animal Friendship, Charm Person
    spell_extras |= {"acid-burn"}  # M29.9a: Acid Arrow's later acid
    spell_extras |= {"surrendered"}  # M29.9a: a successful demand to surrender
    base = {"dodging", "hidden", "surprised", "helped", "blessed", "shield-of-faith"}
    assert extras == base | spell_extras


def test_entries_use_known_keys() -> None:
    abilities = {a.value for a in Ability}
    damage = {d.value for d in DamageType}
    for entry in condition_defs().all():
        used = {*entry.auto_fail_saves, *entry.save_advantage, *entry.save_disadvantage}
        assert used <= abilities, entry.index
        assert set(entry.damage_immunities) <= damage, entry.index
        assert all(key in condition_defs() for key in entry.implies), entry.index


def test_golden_paralyzed_entry() -> None:
    # SRD 5.1 Conditions: Paralyzed -> incapacitated, cannot move, fails STR/DEX saves,
    # attacks against have advantage, a hit from within 5 feet is a critical hit.
    p = condition_defs().get("paralyzed")
    assert p.implies == ("incapacitated",)
    assert p.speed_factor == 0
    assert set(p.auto_fail_saves) == {"str", "dex"}
    assert p.attacks_against_melee == p.attacks_against_ranged == "advantage"
    assert p.auto_crit_melee


def test_exhaustion_is_single_level_until_long_rest() -> None:
    e = condition_defs().get("exhaustion")
    assert e.own_checks == "disadvantage"
    assert e.duration.kind == "until_long_rest"


def test_default_duration_requires_rounds_for_rounds_kind() -> None:
    with pytest.raises(ValidationError):
        DefaultDuration(kind="rounds")
    with pytest.raises(ValidationError):
        DefaultDuration(kind="until_removed", rounds=2)
    assert DefaultDuration(kind="rounds", rounds=1).rounds == 1


def test_unknown_field_and_bad_speed_rejected() -> None:
    with pytest.raises(ValidationError):
        ConditionDef.model_validate({"index": "x", "name": "X", "source": "s", "nope": 1})
    with pytest.raises(ValidationError):
        ConditionDef(index="x", name="X", source="s", speed_factor=2.0)


def _write(tmp_path: Path, entries: list[dict[str, object]]) -> Path:
    path = tmp_path / "conditions.json"
    path.write_text(json.dumps(entries), encoding="utf-8")
    return path


def test_loader_rejects_unknown_implication(tmp_path: Path) -> None:
    path = _write(tmp_path, [{"index": "a", "name": "A", "source": "s", "implies": ["zz"]}])
    with pytest.raises(ValueError, match="unknown condition"):
        load_condition_defs(path)


def test_loader_rejects_implication_cycle(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        [
            {"index": "a", "name": "A", "source": "s", "implies": ["b"]},
            {"index": "b", "name": "B", "source": "s", "implies": ["a"]},
        ],
    )
    with pytest.raises(ValueError, match="cycle"):
        load_condition_defs(path)


def test_loader_accepts_diamond(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        [
            {"index": "a", "name": "A", "source": "s", "implies": ["b", "c"]},
            {"index": "b", "name": "B", "source": "s", "implies": ["c"]},
            {"index": "c", "name": "C", "source": "s"},
        ],
    )
    assert len(load_condition_defs(path)) == 3
