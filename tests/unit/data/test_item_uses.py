"""Item uses (M27.1): the loader validates, the batch loads, goldens match SRD 5.1."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aidm.data.item_uses import (
    Boon,
    DamageUse,
    ItemUseError,
    Unlock,
    item_use_data,
    load_item_use_data,
    uses_for_item,
)
from aidm.data.surface_defs import surface_defs
from aidm.data.zone_templates import zone_templates
from aidm.models.character import InventoryItem


def _use(use_id: str):
    return next(u for u in item_use_data().uses if u.id == use_id)


def _bad_file(tmp_path: Path, **patch: object) -> Path:
    raw = json.loads(
        (Path(__file__).resolve().parents[3] / "data" / "bg3" / "item_uses.json").read_text(
            encoding="utf-8"
        )
    )
    entry = dict(raw["uses"][0])
    entry.update(patch)
    raw["uses"] = [entry]
    path = tmp_path / "item_uses.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    return path


def test_item_uses_batch_loads() -> None:
    data = item_use_data()
    assert len(data.uses) >= 25
    assert uses_for_item("scroll-of-sleep")[0].id == "scroll-read"


def test_item_uses_bad_item_id_is_typed(tmp_path: Path) -> None:
    with pytest.raises(ItemUseError) as caught:
        load_item_use_data(_bad_file(tmp_path, item="no-such-item"))
    assert caught.value.entry == "torch-light"


def test_item_uses_bad_surface_id_is_typed(tmp_path: Path) -> None:
    path = _bad_file(tmp_path, effect={"kind": "surface", "surface": "no-such-surface"})
    with pytest.raises(ItemUseError, match="unknown surface"):
        load_item_use_data(path)


def test_item_uses_bad_skill_is_typed(tmp_path: Path) -> None:
    path = _bad_file(tmp_path, effect={"kind": "boon", "skills": ["no-such-skill"]})
    with pytest.raises(ItemUseError, match="unknown skill"):
        load_item_use_data(path)


def test_item_uses_bad_shape_names_the_entry(tmp_path: Path) -> None:
    with pytest.raises(ItemUseError) as caught:
        load_item_use_data(_bad_file(tmp_path, effect={"kind": "teleport"}))
    assert caught.value.entry == "torch-light"


def test_inventory_item_without_charges_loads() -> None:
    old = InventoryItem.model_validate({"item": "rope-hempen-50-feet", "qty": 2})
    assert old.charges is None
    assert "charges" in InventoryItem(item="healers-kit", charges=10).model_dump()


def test_dark_flag_on_cave_and_crypt_only() -> None:
    dark = {t.index for t in zone_templates().all() if t.dark}
    assert dark == {"cave", "crypt"}


def test_golden_crowbar_advantage() -> None:
    # SRD 5.1 Adventuring Gear: a crowbar gives advantage on Strength checks where leverage helps.
    use = _use("crowbar-force")
    assert isinstance(use.effect, Unlock)
    assert use.effect.advantage and use.effect.skill == "athletics" and use.noise


def test_golden_ball_bearings_dc_10() -> None:
    # SRD 5.1 Ball Bearings: DC 10 Dexterity save or fall prone.
    surface = surface_defs().get("ball-bearings")
    assert surface.dc == 10
    assert surface.harms[0].save == "dex" and surface.harms[0].condition == "prone"


def test_golden_caltrops_dc_15() -> None:
    # SRD 5.1 Caltrops: DC 15 Dexterity save or take 1 piercing damage.
    surface = surface_defs().get("caltrops")
    assert surface.dc == 15 and surface.difficult
    assert surface.harms[0].damage == "1" and surface.harms[0].damage_type == "piercing"


@pytest.mark.parametrize(
    ("use_id", "dice", "damage_type", "types"),
    [
        ("alchemists-fire-throw", "1d4", "fire", ()),  # SRD 5.1 Alchemist's Fire: 1d4 fire
        ("acid-vial-throw", "2d6", "acid", ()),  # SRD 5.1 Acid: 2d6 acid
        ("holy-water-throw", "2d6", "radiant", ("undead", "fiend")),  # SRD 5.1 Holy Water
    ],
)
def test_golden_thrown_flask_damage(
    use_id: str, dice: str, damage_type: str, types: tuple[str, ...]
) -> None:
    effect = _use(use_id).effect
    assert isinstance(effect, DamageUse)
    assert (effect.dice, effect.damage_type, effect.creature_types) == (dice, damage_type, types)


def test_golden_healers_kit_ten_uses() -> None:
    # SRD 5.1 Healer's Kit: ten uses.
    assert _use("healers-kit-stabilize").charges == 10


def test_golden_antitoxin_poison_saves() -> None:
    # SRD 5.1 Antitoxin: advantage on saving throws against poison for 1 hour (here: to long rest).
    effect = _use("antitoxin-drink").effect
    assert isinstance(effect, Boon) and effect.saves_against == ("poison",)


def test_golden_spell_scroll_table() -> None:
    # SRD 5.1 Spell Scroll table: level -> (save DC, attack bonus).
    expected = {0: (13, 5), 1: (13, 5), 2: (13, 5), 3: (15, 7), 4: (15, 7), 5: (17, 9),
                6: (17, 9), 7: (18, 10), 8: (18, 10), 9: (19, 11)}  # fmt: skip
    for level, (dc, bonus) in expected.items():
        row = item_use_data().scroll_power(level)
        assert (row.save_dc, row.attack_bonus) == (dc, bonus)
