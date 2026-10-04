"""Schema and SRD cross-reference tests for data/bg3/classes/*.json (aidm.data.class_defs)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from aidm.data.class_defs import CLASS_ORDER, DEFAULT_CLASSES_DIR, ClassDef, class_defs
from aidm.data.class_defs import load_class_defs
from aidm.data.srd import srd

SUBCLASS_LEVEL = {"cleric": 1, "warlock": 1, "wizard": 2, "fighter": 3, "rogue": 3, "ranger": 3}
SUBCLASS = {
    "fighter": "champion",
    "rogue": "thief",
    "wizard": "evocation",
    "cleric": "life",
    "ranger": "hunter",
    "warlock": "fiend",
}


def _raw(name: str) -> dict[str, Any]:
    return json.loads((DEFAULT_CLASSES_DIR / f"{name}.json").read_text(encoding="utf-8"))


def test_six_classes_in_order() -> None:
    assert tuple(c.index for c in class_defs().all()) == CLASS_ORDER


@pytest.mark.parametrize("key", CLASS_ORDER)
def test_class_matches_srd_basics(key: str) -> None:
    d = class_defs().get(key)
    s = srd().classes.get(key)
    assert d.name == s.name
    assert d.hit_die == s.hit_die
    assert set(d.saving_throws) == {r.index for r in s.saving_throws}
    granted = {*d.armor, *d.weapons, *d.tools}
    srd_profs = {
        p.index
        for p in s.proficiencies
        if srd().proficiencies.get(p.index).type not in ("Saving Throws", "Skills")
    }
    assert granted == srd_profs


@pytest.mark.parametrize("key", CLASS_ORDER)
def test_skill_choice_matches_srd(key: str) -> None:
    d = class_defs().get(key)
    choice: Any = srd().classes.get(key).proficiency_choices[0]
    expected = {o["item"]["index"].removeprefix("skill-") for o in choice["from"]["options"]}
    assert d.skill_choice.choose == choice["choose"]
    assert set(d.skill_choice.options) == expected
    assert all(s in srd().skills for s in d.skill_choice.options)


@pytest.mark.parametrize("key", CLASS_ORDER)
def test_proficiency_indexes_exist(key: str) -> None:
    d = class_defs().get(key)
    for index in (*d.armor, *d.weapons, *d.tools):
        assert index in srd().proficiencies, index


@pytest.mark.parametrize("key", CLASS_ORDER)
def test_equipment_indexes_exist_and_groups_have_options(key: str) -> None:
    d = class_defs().get(key)
    ids = [c.id for c in d.equipment.choices]
    assert len(ids) == len(set(ids))
    items = [i for i in d.equipment.fixed]
    for choice in d.equipment.choices:
        assert len(choice.options) >= 2
        for option in choice.options:
            assert option, choice.id
            items.extend(option)
    assert items
    for entry in items:
        assert entry.item in srd().equipment, entry.item


@pytest.mark.parametrize("key", ["rogue", "wizard", "cleric", "ranger", "warlock"])
def test_fixed_equipment_matches_srd(key: str) -> None:
    fixed = {(e.item, e.qty) for e in class_defs().get(key).equipment.fixed}
    srd_rows: list[Any] = list(srd().classes.get(key).starting_equipment)
    srd_fixed = {(e["equipment"]["index"], e["quantity"]) for e in srd_rows}
    assert fixed == srd_fixed


@pytest.mark.parametrize("key", CLASS_ORDER)
def test_feature_ids_exist_or_are_bg3(key: str) -> None:
    d = class_defs().get(key)
    rows = [f for r in d.levels for f in r.features] + [
        f for lf in d.subclass_features for f in lf.features
    ]
    for fid in rows:
        assert fid.startswith("bg3-") or fid in srd().features, fid
    for choice in d.choices:
        assert all(o in srd().features for o in choice.pick.options)


@pytest.mark.parametrize("key", CLASS_ORDER)
def test_srd_features_per_level_match_srd_levels(key: str) -> None:
    d = class_defs().get(key)
    for row in d.levels:
        srd_row = srd().levels.get(f"{key}-{row.level}")
        got = [f for f in row.features if not f.startswith("bg3-")]
        assert got == [f.index for f in srd_row.features]
        # SRD ability_score_bonuses is cumulative: a new ASI is an increase over the last level.
        prev = srd().levels.get(f"{key}-{row.level - 1}").ability_score_bonuses if row.level > 1 else 0
        assert row.asi == ((srd_row.ability_score_bonuses or 0) > (prev or 0))


@pytest.mark.parametrize("key", CLASS_ORDER)
def test_subclass_matches_srd(key: str) -> None:
    d = class_defs().get(key)
    assert d.subclass_index == SUBCLASS[key]
    assert d.subclass_level == SUBCLASS_LEVEL[key]
    sub = srd().subclasses.get(d.subclass_index)
    assert sub.class_ref.index == key
    assert d.subclass_index in {r.index for r in srd().classes.get(key).subclasses}
    for lf in d.subclass_features:
        assert lf.level >= d.subclass_level
        for fid in lf.features:
            feat = srd().features.get(fid)
            assert feat.subclass is not None and feat.subclass.index == d.subclass_index
            assert feat.level == lf.level


@pytest.mark.parametrize("key", CLASS_ORDER)
def test_asi_at_level_4_only(key: str) -> None:
    assert [r.level for r in class_defs().get(key).levels if r.asi] == [4]


@pytest.mark.parametrize("key", CLASS_ORDER)
def test_slots_and_spells_match_srd_levels(key: str) -> None:
    d = class_defs().get(key)
    for row in d.levels:
        sc = srd().levels.get(f"{key}-{row.level}").spellcasting
        if d.spellcasting is None:
            assert sc is None and not any(row.slots) and row.cantrips_known == 0
            continue
        assert sc is not None
        assert row.slots == tuple(sc.get(f"spell_slots_level_{n}", 0) for n in range(1, 6))
        assert row.cantrips_known == sc.get("cantrips_known", 0)
        assert row.spells_known == (sc["spells_known"] if "spells_known" in sc else None)


def test_spellcasting_blocks() -> None:
    kinds: dict[str, tuple[str, str]] = {}
    for key in CLASS_ORDER:
        sc = class_defs().get(key).spellcasting
        if sc is not None:
            kinds[key] = (sc.ability, sc.kind)
    assert kinds == {
        "wizard": ("int", "prepared"),
        "cleric": ("wis", "prepared"),
        "ranger": ("wis", "known"),
        "warlock": ("cha", "pact"),
    }
    assert class_defs().get("fighter").spellcasting is None
    ranger_sc = class_defs().get("ranger").spellcasting
    assert ranger_sc is not None and ranger_sc.first_level == 2


def test_golden_wizard_level_3_slots() -> None:
    # SRD 5.1 Wizard table, level 3: 3 cantrips, four 1st-level and two 2nd-level slots.
    row = class_defs().get("wizard").level(3)
    assert row.slots == (4, 2, 0, 0, 0)
    assert row.cantrips_known == 3


def test_golden_warlock_pact_slots() -> None:
    # SRD 5.1 Warlock table: level 1 -> 1 slot (lvl 1); 2 -> 2 (lvl 1); 3 -> 2 (lvl 2);
    # 5 -> 2 slots of 3rd level. Spells known 2,3,4,5,6; cantrips 2,2,2,3,3.
    w = class_defs().get("warlock")
    assert [r.slots for r in w.levels] == [
        (1, 0, 0, 0, 0),
        (2, 0, 0, 0, 0),
        (0, 2, 0, 0, 0),
        (0, 2, 0, 0, 0),
        (0, 0, 2, 0, 0),
    ]
    assert [r.spells_known for r in w.levels] == [2, 3, 4, 5, 6]
    assert [r.cantrips_known for r in w.levels] == [2, 2, 2, 3, 3]


def test_golden_ranger_and_cleric_tables() -> None:
    # SRD 5.1 Ranger: no spells at level 1, spells known 2,3,3,4 and slots 4/2 at level 5.
    r = class_defs().get("ranger")
    assert [row.spells_known for row in r.levels] == [0, 2, 3, 3, 4]
    assert r.level(5).slots == (4, 2, 0, 0, 0)
    # SRD 5.1 Cleric level 5: 4 cantrips, slots 4/3/2.
    c = class_defs().get("cleric")
    assert c.level(5).slots == (4, 3, 2, 0, 0) and c.level(5).cantrips_known == 4


def test_golden_hit_dice_and_saves() -> None:
    # SRD 5.1 class tables: d10 fighter and ranger, d8 rogue, cleric and warlock, d6 wizard.
    expected = {"fighter": 10, "rogue": 8, "wizard": 6, "cleric": 8, "ranger": 10, "warlock": 8}
    assert {k: class_defs().get(k).hit_die for k in CLASS_ORDER} == expected
    assert set(class_defs().get("rogue").saving_throws) == {"dex", "int"}


def test_fighting_style_choices() -> None:
    f = class_defs().get("fighter").choices[0]
    assert (f.kind, f.level, f.pick.choose, len(f.pick.options)) == ("fighting_style", 1, 1, 6)
    styles = [c for c in class_defs().get("ranger").choices if c.kind == "fighting_style"]
    assert styles[0].level == 2 and len(styles[0].pick.options) == 4


def test_bg3_features_are_declared_with_notes() -> None:
    declared = {f.id for k in CLASS_ORDER for f in class_defs().get(k).bg3_features}
    assert declared == {"bg3-scroll-copy", "bg3-pact-short-rest"}
    for k in CLASS_ORDER:
        for f in class_defs().get(k).bg3_features:
            assert f.note and f.description


def test_unknown_field_rejected() -> None:
    raw = _raw("fighter")
    raw["nope"] = 1
    with pytest.raises(ValidationError):
        ClassDef.model_validate(raw)


def test_levels_must_be_one_to_five() -> None:
    raw = _raw("fighter")
    raw["levels"] = raw["levels"][:4]
    with pytest.raises(ValidationError, match="levels must be exactly"):
        ClassDef.model_validate(raw)


def test_undeclared_bg3_feature_rejected() -> None:
    raw = _raw("fighter")
    raw["levels"][0]["features"].append("bg3-ghost")
    with pytest.raises(ValidationError, match="bg3 feature ids"):
        ClassDef.model_validate(raw)


def test_non_caster_with_slots_rejected() -> None:
    raw = _raw("fighter")
    raw["levels"][0]["slots"] = [1, 0, 0, 0, 0]
    with pytest.raises(ValidationError, match="non-caster"):
        ClassDef.model_validate(raw)


def test_known_caster_needs_spells_known() -> None:
    raw = _raw("warlock")
    del raw["levels"][2]["spells_known"]
    with pytest.raises(ValidationError, match="spells_known"):
        ClassDef.model_validate(raw)


def test_pick_cannot_exceed_options() -> None:
    raw = _raw("fighter")
    raw["skill_choice"]["choose"] = 99
    with pytest.raises(ValidationError):
        ClassDef.model_validate(raw)


def test_loader_requires_matching_file_name(tmp_path: Path) -> None:
    raw = _raw("fighter")
    (tmp_path / "other.json").write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="must match the file name"):
        load_class_defs(tmp_path)
