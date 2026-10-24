"""Schema and coverage tests for data/bg3/features.json (aidm.data.feature_defs)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from aidm.data.class_defs import class_defs
from aidm.data.condition_defs import condition_defs
from aidm.data.feature_defs import DEFAULT_FEATURES, FeatureDef, feature_defs, load_feature_defs
from aidm.data.feature_hooks import (
    BonusActionHook,
    DropToOneHook,
    ExtraActionHook,
    ProficiencyHook,
    ResourceHook,
    SlotRecoveryHook,
    SpellGrantHook,
    ToggleHook,
    UnsupportedHook,
)
from aidm.data.master_template import master_template
from aidm.data.race_defs import race_defs
from aidm.data.srd import srd
from aidm.models.abilities import Skill
from aidm.rules.monster_keys import ability_slug

RULES_DECISIONS = Path(__file__).resolve().parents[3] / "docs" / "RULES_DECISIONS.md"


def _referenced_ids() -> set[str]:
    ids: set[str] = set()
    for cls in class_defs().all():
        ids |= {f for row in cls.levels for f in row.features}
        ids |= {f for row in cls.subclass_features for f in row.features}
        ids |= {o for choice in cls.choices for o in choice.pick.options}
    for race in race_defs().all():
        ids |= set(race.traits)
        for sub in race.subraces:
            ids |= set(sub.traits)
    return ids


def _monster_traits() -> set[str]:
    """Stat block traits, plus the M31.1d master template's trait (stamped on masters)."""
    found = {ability_slug(a.name) for m in srd().monsters.all() for a in m.special_abilities}
    trait = master_template().trait
    return found | ({trait} if trait else set[str]())


def test_every_referenced_feature_has_an_entry() -> None:
    registry = feature_defs()
    missing = sorted(i for i in _referenced_ids() if i not in registry)
    assert missing == []


def test_every_entry_is_referenced_or_a_pick_option() -> None:
    registry = feature_defs()
    options = {o for e in registry.all() if e.pick for o in e.pick.options}
    known = _referenced_ids() | options | _monster_traits()
    orphans = sorted(e.index for e in registry.all() if e.index not in known)
    assert orphans == []


def test_unsupported_features_are_listed_in_rules_decisions() -> None:
    text = RULES_DECISIONS.read_text(encoding="utf-8")
    unsupported = [
        e.index for e in feature_defs().all() if any(isinstance(h, UnsupportedHook) for h in e.hooks)
    ]
    assert unsupported, "the shipped data has known unsupported mechanics"
    assert [i for i in unsupported if f"`{i}`" not in text] == []


def test_m29_no_unsupported_feature_shows_a_resource() -> None:
    """M29.9a T18: a feature whose effect is not modelled never shows a usable-looking counter
    (Relentless Endurance showed 1/1 while its hook was `unsupported`)."""
    shown = [
        e.index
        for e in feature_defs().all()
        if any(isinstance(h, UnsupportedHook) for h in e.hooks)
        and any(isinstance(h, ResourceHook) for h in e.hooks)
    ]
    assert shown == []


def test_resources_used_by_hooks_are_defined() -> None:
    registry = feature_defs()
    defined = {h.key for e in registry.all() for h in e.hooks if isinstance(h, ResourceHook)}
    used: set[str] = set()
    for entry in registry.all():
        for hook in entry.hooks:
            if isinstance(hook, BonusActionHook | ToggleHook) and hook.resource:
                used.add(hook.resource)
            elif isinstance(hook, ExtraActionHook | SlotRecoveryHook | DropToOneHook):
                used.add(hook.resource)
            elif isinstance(hook, SpellGrantHook):
                used |= {g.resource for g in hook.spells if g.resource}
    assert used - defined == set()


def test_references_resolve_against_srd() -> None:
    data = srd()
    skills = {s.value for s in Skill}
    for entry in feature_defs().all():
        for hook in entry.hooks:
            if isinstance(hook, SpellGrantHook):
                assert all(g.spell in data.spells for g in hook.spells), entry.index
            if isinstance(hook, ProficiencyHook):
                profs = (*hook.armor, *hook.weapons, *hook.tools)
                assert all(p in data.proficiencies for p in profs), entry.index
                assert set(hook.skills) <= skills, entry.index
            if isinstance(hook, ToggleHook):
                assert hook.condition in condition_defs(), entry.index


def test_summaries_are_ascii_and_short() -> None:
    for entry in feature_defs().all():
        assert entry.summary.isascii() and len(entry.summary) <= 200, entry.index


def test_unknown_hook_kind_rejected() -> None:
    with pytest.raises(ValidationError):
        FeatureDef.model_validate(
            {"index": "x", "name": "X", "summary": "s", "hooks": [{"kind": "teleport"}]}
        )


def test_unknown_pick_option_rejected(tmp_path: Path) -> None:
    raw = [{"index": "x", "name": "X", "summary": "s", "pick": {"choose": 1, "options": ["y"]}}]
    path = tmp_path / "features.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="unknown features"):
        load_feature_defs(path)


def test_default_file_loads() -> None:
    assert len(load_feature_defs(DEFAULT_FEATURES)) == len(feature_defs())
