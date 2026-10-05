"""Picker policy (M3.6b, SPEC 7.4): only shipped spells are offered or accepted, and a table
count larger than the shipped options still open becomes min(table count, open options)."""

from __future__ import annotations

import pytest

from aidm.data.character_data import character_registries
from aidm.data.spell_defs import shipped_spell_ids
from aidm.models.creation import CreationError
from aidm.models.creation import CreationErrorCode as E
from aidm.models.events import CreatureAdded
from aidm.models.state import GameState
from aidm.rules import creation_checks, feature_build
from aidm.rules.creation import build_character, validate_creation
from aidm.rules.creation_checks import class_spell_indexes, pick_count
from aidm.rules.feature_build import granted_spells
from aidm.rules.leveling import gain_xp, validate_level_up, xp_for_level
from aidm.session.reducer import apply
from tests.unit.rules.creation_fixtures import default_choices
from tests.unit.rules.leveling_fixtures import script_choices

REGS = character_registries()


def _ship_without(monkeypatch: pytest.MonkeyPatch, *hidden: str) -> None:
    shipped = shipped_spell_ids() - set(hidden)
    monkeypatch.setattr(creation_checks, "shipped_spell_ids", lambda: shipped)
    monkeypatch.setattr(feature_build, "shipped_spell_ids", lambda: shipped)


def _codes(errors: list[CreationError]) -> list[tuple[E, str]]:
    return [(e.code, e.field) for e in errors]


def test_pick_count_is_capped_by_open_options() -> None:
    assert pick_count(3, {"a", "b"}) == 2
    assert pick_count(2, {"a", "b", "c"}, taken=["a", "b"]) == 1
    assert pick_count(1, {"a", "b", "c"}) == 1


def test_pickers_offer_only_shipped_spells() -> None:
    shipped = shipped_spell_ids()
    for cls in ("cleric", "warlock", "wizard", "ranger"):
        assert class_spell_indexes(REGS.spells, cls, 0, 3) <= shipped
    assert "light" not in class_spell_indexes(REGS.spells, "cleric", 0, 0)
    choices = default_choices("cleric", "human", None)
    unshipped = choices.model_copy(update={"cantrips": [*choices.cantrips[:2], "light"]})
    assert (E.PICK_NOT_ALLOWED, "cantrips") in _codes(validate_creation(unshipped, REGS))


def test_cleric_cantrips_shrink_to_the_shipped_count(monkeypatch: pytest.MonkeyPatch) -> None:
    # The table asks for 3 cantrips; with only Sacred Flame shipped the cleric picks 1.
    _ship_without(monkeypatch, "guidance", "resistance", "spare-the-dying")
    choices = default_choices("cleric", "human", None)
    assert choices.cantrips == ["sacred-flame"]
    assert validate_creation(choices, REGS) == []
    two = choices.model_copy(update={"cantrips": ["sacred-flame", "guidance"]})
    codes = _codes(validate_creation(two, REGS))
    assert (E.PICK_COUNT, "cantrips") in codes and (E.PICK_NOT_ALLOWED, "cantrips") in codes


def test_warlock_spells_shrink_and_unshipped_patron_spells_vanish(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Level 1 warlock: 2 spells known, but only Charm Person is left (the fiend's Burning Hands
    # is hidden here and its Command is never shipped).
    _ship_without(monkeypatch, "burning-hands", "expeditious-retreat")
    choices = default_choices("warlock", "human", None)
    assert choices.spells == ["charm-person"]
    assert validate_creation(choices, REGS) == []
    pc = build_character(choices, REGS, "w")
    assert pc.pc is not None
    expanded = [g.spell for g in granted_spells(pc.pc.features, 5, "fiend", REGS.features)]
    assert "command" not in expanded and "burning-hands" not in expanded
    assert "scorching-ray" in expanded


def test_ranger_level_two_learns_what_is_shipped(monkeypatch: pytest.MonkeyPatch) -> None:
    # SRD Ranger level 2: 2 spells known; with one shipped level-1 ranger spell the pick is 1.
    hidden = ("animal-friendship", "fog-cloud", "hunters-mark", "longstrider")
    _ship_without(monkeypatch, *hidden)
    assert class_spell_indexes(REGS.spells, "ranger", 1, 1) == {"cure-wounds"}
    pc = build_character(default_choices("ranger", "human", None), REGS, "r")
    state = apply(GameState(campaign_id="c", seed=1), CreatureAdded(creature=pc))
    for event in gain_xp(state.creatures["r"], xp_for_level(2)):
        apply(state, event)
    base = script_choices(state.creatures["r"], REGS)
    one = base.model_copy(update={"spells": ["cure-wounds"]})
    assert validate_level_up(state.creatures["r"], one, REGS) == []
    two = base.model_copy(update={"spells": ["cure-wounds", "hunters-mark"]})
    assert (E.PICK_COUNT, "spells") in _codes(validate_level_up(state.creatures["r"], two, REGS))


def test_life_domain_grants_only_shipped_spells() -> None:
    domain = ["domain-spells-1", "domain-spells-2", "domain-spells-3"]
    grants = [g.spell for g in granted_spells(domain, 5, "life", REGS.features)]
    # SRD Life Domain spells to level 5: bless, cure wounds, lesser restoration, spiritual
    # weapon, beacon of hope, revivify; the unshipped Spiritual Weapon and Beacon of Hope are
    # not granted (docs/RULES_DECISIONS.md M3.6b).
    assert grants == ["bless", "cure-wounds", "lesser-restoration", "revivify"]
