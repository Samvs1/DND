"""data/bg3/weaknesses.json and item substances (M27.6): typed loaders that name the bad entry."""

import json
from pathlib import Path

import pytest

from aidm.data.item_uses import (
    DEFAULT_ITEM_USES,
    DamageUse,
    ItemUseError,
    improvised_use,
    item_substances,
    load_item_use_data,
)
from aidm.data.weakness_defs import WeaknessError, load_weakness_defs, weaknesses_of

WATER_ROW = {
    "trait": "Water Susceptibility",
    "amount": 1,
    "damage_type": "cold",
    "source": "SRD 5.1 Fire Elemental",
}


def _table(tmp_path: Path, table: object) -> Path:
    path = tmp_path / "weaknesses.json"
    path.write_text(json.dumps(table), encoding="utf-8")
    return path


def test_golden_fire_elemental_water_row() -> None:
    row = weaknesses_of("fire-elemental")["water"]
    # SRD 5.1 Fire Elemental, Water Susceptibility: 1 cold damage per gallon splashed on it
    assert (row.trait, row.amount, row.damage_type) == ("Water Susceptibility", 1, "cold")
    assert weaknesses_of("goblin") == {} and weaknesses_of(None) == {}


def test_weakness_unknown_monster_id_is_refused(tmp_path: Path) -> None:
    with pytest.raises(WeaknessError) as caught:
        load_weakness_defs(_table(tmp_path, {"no-such-monster": {"water": WATER_ROW}}))
    assert caught.value.entry == "no-such-monster" and "unknown monster" in caught.value.problem


def test_weakness_unknown_substance_is_refused(tmp_path: Path) -> None:
    with pytest.raises(WeaknessError) as caught:
        load_weakness_defs(_table(tmp_path, {"fire-elemental": {"lava": WATER_ROW}}))
    assert caught.value.entry == "fire-elemental"


def test_weakness_trait_must_be_on_the_stat_block(tmp_path: Path) -> None:
    row = {**WATER_ROW, "trait": "Sunlight Sensitivity"}
    with pytest.raises(WeaknessError, match="no trait"):
        load_weakness_defs(_table(tmp_path, {"fire-elemental": {"water": row}}))


def test_item_substances_are_data() -> None:
    assert item_substances("waterskin") == ("water",)
    assert item_substances("holy-water-flask") == ("holy",)
    assert item_substances("rope-hempen-50-feet") == ()


def test_item_substance_on_an_unknown_item_is_refused(tmp_path: Path) -> None:
    raw = json.loads(DEFAULT_ITEM_USES.read_text(encoding="utf-8"))
    raw["substances"] = {"no-such-item": ["water"]}
    path = tmp_path / "item_uses.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ItemUseError, match="unknown item"):
        load_item_use_data(path)
    raw["substances"] = {"waterskin": ["lava"]}
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ItemUseError):
        load_item_use_data(path)


def test_golden_improvised_throw_is_srd() -> None:
    use = improvised_use("waterskin")
    # SRD 5.1 Improvised Weapons: 1d4 damage, thrown 20/60 ft (the range lives in the attack path)
    assert use.item == "waterskin" and use.consumes and use.cost == "action"
    assert isinstance(use.effect, DamageUse)
    assert use.effect.dice == "1d4" and use.effect.ability_mod
