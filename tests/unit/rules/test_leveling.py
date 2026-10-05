"""Level-up 1 -> 5 for every class, XP table goldens and typed refusals (SPEC 7.2, 7.5).

SRD 5.1 citations: "Character Advancement" table (XP and proficiency bonus), class tables
(features, cantrips/spells known, slots), "Hit Points at Higher Levels" (fixed value).
"""

from __future__ import annotations

import pytest

from aidm.data.character_data import character_registries
from aidm.models.abilities import Ability
from aidm.models.creation import CreationErrorCode
from aidm.models.events import AnyEvent, CreatureAdded, LevelGained
from aidm.models.leveling import LevelUpChoices
from aidm.models.state import Creature, CreatureKind, GameState
from aidm.rules.creation import build_character
from aidm.rules.creation_checks import class_spell_indexes
from aidm.rules.features import attacks_per_action
from aidm.rules.leveling import (
    MAX_LEVEL,
    LevelUpInvalid,
    can_level_up,
    gain_xp,
    level_for_xp,
    level_up,
    validate_level_up,
    xp_for_level,
)
from aidm.rules.spellcasting import (
    cantrips_known_count,
    class_slot_maximums,
    slot_maximum_events,
    spells_known_count,
    spend_slot,
)
from aidm.session.reducer import apply, replay
from tests.unit.rules.creation_fixtures import default_choices
from tests.unit.rules.leveling_fixtures import level_to, run_events, script_choices

REGS = character_registries()
E = CreationErrorCode
CLASSES = [c.index for c in REGS.classes.all()]


def _state(cls: str, race: str = "dwarf", sub: str | None = "hill-dwarf") -> GameState:
    pc = build_character(default_choices(cls, race, sub), REGS, "pc1")
    return apply(GameState(campaign_id="c", seed=1), CreatureAdded(creature=pc))


def _codes(creature: Creature, choices: LevelUpChoices) -> list[tuple[CreationErrorCode, str]]:
    return [(e.code, e.field) for e in validate_level_up(creature, choices, REGS)]


def _ready(state: GameState, level: int) -> Creature:
    """The PC at `level` with enough XP for the next one."""
    log: list[AnyEvent] = []
    level_to(state, "pc1", level, REGS, log)
    pc = state.creatures["pc1"].pc
    assert pc is not None
    run_events(state, gain_xp(state.creatures["pc1"], xp_for_level(level + 1) - pc.xp), log)
    return state.creatures["pc1"]


def test_golden_xp_table() -> None:
    # SRD Character Advancement: 0 / 300 / 900 / 2,700 / 6,500 XP for levels 1-5.
    assert [xp_for_level(n) for n in range(1, 6)] == [0, 300, 900, 2700, 6500]
    assert [level_for_xp(x) for x in (0, 299, 300, 899, 900, 2700, 6499, 6500, 99999)] == [
        1, 1, 2, 2, 3, 4, 4, 5, 5,
    ]  # fmt: skip
    assert MAX_LEVEL == 5


@pytest.mark.parametrize("class_index", CLASSES)
def test_level_1_to_5_invariants(class_index: str) -> None:
    state = _state(class_index)
    initial = GameState(campaign_id="c", seed=1)
    log: list[AnyEvent] = [CreatureAdded(creature=state.creatures["pc1"])]
    cls = REGS.classes.get(class_index)
    hps = [state.creatures["pc1"].max_hp]
    for level in range(2, MAX_LEVEL + 1):
        level_to(state, "pc1", level, REGS, log)
        pc = state.creatures["pc1"]
        assert pc.pc is not None and pc.pc.level == level
        hps.append(pc.max_hp)
        assert pc.hp == pc.max_hp
        assert (pc.pc.subclass is not None) == (level >= cls.subclass_level)
        slots = {k: r.maximum for k, r in pc.resources.items() if "slot" in k}
        assert slots == class_slot_maximums(cls, level)
        assert set(cls.level(level).features) <= set(pc.pc.features)
    assert all(b > a for a, b in zip(hps, hps[1:], strict=False))
    final = state.creatures["pc1"]
    assert final.pc is not None
    assert final.proficiency_bonus == 3  # SRD: +3 from 5th level
    expected_attacks = 2 if class_index in ("fighter", "ranger") else 1
    assert attacks_per_action(final, REGS.features) == expected_attacks
    assert len(final.pc.cantrips) == cantrips_known_count(cls, MAX_LEVEL)
    casting = cls.spellcasting
    if casting is not None and casting.kind != "prepared":
        assert len(final.pc.spells_known) == spells_known_count(cls, MAX_LEVEL)
    if casting is not None and casting.spellbook_start:
        assert len(final.pc.spellbook) == 6 + 2 * 4  # SRD Wizard: 6, then 2 per level
    assert replay(initial, log) == state


def test_golden_hill_dwarf_fighter_hp_and_features() -> None:
    # d10: 10 + CON 2 = 12 at 1st, then 4 x (6 + 2) = 32, plus Dwarven Toughness 5 x 1 = 49.
    state = _state("fighter")
    level_to(state, "pc1", 5, REGS, [])
    pc = state.creatures["pc1"]
    assert pc.pc is not None and pc.max_hp == 49
    assert pc.abilities[Ability.STR] == 17  # standard array 15 + ASI 2 at 4th level
    assert pc.pc.subclass == "champion" and "improved-critical" in pc.pc.features
    assert pc.resources["action-surge"].maximum == 1


def test_wizard_learns_level_two_spells_and_slots() -> None:
    state = _state("wizard", "elf", "high-elf")
    level_to(state, "pc1", 3, REGS, [])
    pc = state.creatures["pc1"]
    assert pc.pc is not None
    levels = {REGS.spells.get(s).level for s in pc.pc.spellbook}
    assert levels == {1, 2}
    assert pc.resources["spell-slot-2"].maximum == 2


def test_spent_slots_stay_spent_through_level_up() -> None:
    state = _state("cleric")
    creature = _ready(state, 1)
    run_events(state, spend_slot(creature, 1), [])
    creature = state.creatures["pc1"]
    run_events(state, level_up(creature, script_choices(creature, REGS), REGS), [])
    slot = state.creatures["pc1"].resources["spell-slot-1"]
    assert (slot.current, slot.maximum) == (2, 3)
    assert state.creatures["pc1"].resources["channel-divinity"].current == 1


def test_refusals_are_typed_and_consume_nothing() -> None:
    state = _state("fighter")
    creature = state.creatures["pc1"]
    assert _codes(creature, LevelUpChoices()) == [(E.NOT_ENOUGH_XP, "xp")]
    assert not can_level_up(creature)
    with pytest.raises(LevelUpInvalid):
        level_up(creature, LevelUpChoices(), REGS)
    at2 = _ready(state, 2)
    assert can_level_up(at2)
    assert (E.SUBCLASS_INVALID, "subclass") in _codes(at2, LevelUpChoices())
    wrong = LevelUpChoices(subclass="champion", spells=["fireball"])
    assert (E.PICK_COUNT, "spells") in _codes(at2, wrong)
    early = _ready(_state("fighter"), 1)
    assert (E.SUBCLASS_INVALID, "subclass") in _codes(early, LevelUpChoices(subclass="champion"))
    assert (E.ASI_INVALID, "asi") in _codes(early, LevelUpChoices(asi={Ability.STR: 2}))


def test_asi_rules() -> None:
    at3 = _ready(_state("rogue"), 3)
    assert _codes(at3, LevelUpChoices(asi={Ability.DEX: 2})) == []
    assert _codes(at3, LevelUpChoices(asi={Ability.DEX: 1, Ability.CON: 1})) == []
    for bad in ({Ability.DEX: 3}, {Ability.DEX: 1}, {Ability.STR: 1, Ability.DEX: 2}, {}):
        assert (E.ASI_INVALID, "asi") in _codes(at3, LevelUpChoices(asi=bad))
    capped = at3.model_copy(update={"abilities": {**at3.abilities, Ability.DEX: 19}})
    assert (E.ASI_INVALID, "asi") in _codes(capped, LevelUpChoices(asi={Ability.DEX: 2}))


def test_con_increase_is_retroactive() -> None:
    # SRD: a Constitution modifier increase raises max HP by 1 per level already gained.
    at3 = _ready(_state("rogue", "human", None), 3)  # human CON 13 + 1 = 14 (+2)
    events = level_up(at3, LevelUpChoices(asi={Ability.CON: 2}), REGS)
    gained = next(e for e in events if isinstance(e, LevelGained))
    # d8: 8 + 3 at 1st, then 3 x (5 + 3) = 35 at 4th level with CON 16 (+3).
    assert (at3.max_hp, gained.max_hp) == (8 + 2 + 2 * 7, 35)


def test_known_caster_replacement_and_counts() -> None:
    # Level 2 -> 3 (pact slots of level 2 open): the shipped warlock levels 1-2 pool is large
    # enough to swap (M3.6b: only shipped spells are offered; unshipped Unseen Servant is not).
    at2 = _ready(_state("warlock", "human", None), 2)
    assert at2.pc is not None
    base = script_choices(at2, REGS)
    old = at2.pc.spells_known[0]
    new = next(s for s in ("misty-step", "darkness") if s not in base.spells)
    swap = base.model_copy(update={"replace_spell": old, "replacement": new})
    assert _codes(at2, swap) == []
    gained = next(e for e in level_up(at2, swap, REGS) if isinstance(e, LevelGained))
    assert old not in gained.pc.spells_known and new in gained.pc.spells_known
    bad = base.model_copy(update={"replace_spell": "fireball", "replacement": new})
    assert (E.REPLACEMENT_INVALID, "replace_spell") in _codes(at2, bad)
    unshipped = base.model_copy(update={"replace_spell": old, "replacement": "unseen-servant"})
    assert (E.REPLACEMENT_INVALID, "replace_spell") in _codes(at2, unshipped)
    extra = base.model_copy(update={"spells": [*base.spells, new]})
    assert (E.PICK_COUNT, "spells") in _codes(at2, extra)
    assert (E.PICK_NOT_ALLOWED, "prepared") in _codes(at2, base.model_copy(update={"prepared": []}))


def test_prepared_limit_on_level_up() -> None:
    at1 = _ready(_state("cleric"), 1)
    pool = sorted(class_spell_indexes(REGS.spells, "cleric", 1, 1))
    # SRD Cleric: WIS modifier + level; hill dwarf WIS 10 + 1 = 11 (+0), level 2 -> 2.
    codes = _codes(at1, LevelUpChoices(prepared=pool[:3]))
    assert (E.PREPARED_OVER_LIMIT, "prepared") in codes
    assert _codes(at1, LevelUpChoices(prepared=pool[:2])) == []


def test_gate_codes() -> None:
    monster = Creature(id="m", name="M", kind=CreatureKind.MONSTER, max_hp=5, hp=5)
    assert _codes(monster, LevelUpChoices()) == [(E.NOT_A_PC, "creature")]
    at4 = _ready(_state("rogue"), 4)
    downed = at4.model_copy(update={"hp": 0})
    assert _codes(downed, LevelUpChoices()) == [(E.CANNOT_LEVEL_NOW, "creature")]
    state = _state("rogue")
    level_to(state, "pc1", 5, REGS, [])
    capped = state.creatures["pc1"].model_copy(deep=True)
    assert _codes(capped, LevelUpChoices()) == [(E.MAX_LEVEL_REACHED, "level")]
    with pytest.raises(ValueError):
        gain_xp(monster, 10)
    with pytest.raises(ValueError):
        gain_xp(capped, -1)
    assert slot_maximum_events(capped, REGS.classes.get("rogue"), 5) == []
