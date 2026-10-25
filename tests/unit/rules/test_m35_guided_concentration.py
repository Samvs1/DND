"""M35.3 round 6 Y2 + Y3 (docs/playtests/M34_round6.md): Guiding Bolt's guided is used up by the
next attack roll against the target, and a concentration whose last linked effect ended ends.
"""

from __future__ import annotations

from aidm.models.abilities import Ability
from aidm.models.combat import AttackProfile
from aidm.models.combat_events import AttackRolled
from aidm.models.conditions import ConditionLink
from aidm.models.dice import AdvState
from aidm.models.events import (
    AnyEvent,
    ConcentrationEnded,
    ConditionRemoved,
    CreatureAdded,
    CreatureRemoved,
)
from aidm.models.state import ActiveCondition, Creature, CreatureKind, GameState
from aidm.rules.attacks import roll_attack
from aidm.rules.concentration import (
    end_concentration,
    orphaned_concentration_events,
    start_concentration,
)
from aidm.rules.condition_timing import new_condition
from aidm.rules.conditions import condition_def
from aidm.rules.hit_chance import hit_chance
from aidm.session.reducer import apply
from tests.unit.rules.combat_fixtures import REGS, ScriptedRng
from tests.unit.rules.spell_fixtures import battle, cast, caster, conditions_of, next_turn, of

CLAW = AttackProfile(key="claw", name="Claw", attack_bonus=4)
FEATS = REGS.chars.features


def _run(state: GameState, events: list[AnyEvent]) -> None:
    for event in events:
        apply(state, event)


def _guided_fight() -> GameState:
    cleric = caster("c", "cleric", spells=["guiding-bolt"], slots={1: 1})
    state = battle(cleric, ("gob", "yard"), ("b", "gate"))
    cast(state, "c", "guiding-bolt", ScriptedRng(10, 1, 2, 3, 4), targets=["gob"])
    assert conditions_of(state, "gob") == ["guided"]
    return state


def _attack(state: GameState, *d20: int) -> AttackRolled:
    rolled = roll_attack(ScriptedRng(*d20), state, "b", "gob", CLAW, FEATS)
    _run(state, rolled.events)
    return of(rolled.events, AttackRolled)[0]


def test_golden_guided_advantage_on_the_next_attack_only() -> None:
    # SRD 5.1 Guiding Bolt: "the next attack roll made against this target before the end of
    # your next turn has advantage". The first claw rolls 2d20 (advantage), the second 1d20.
    state = _guided_fight()
    first = _attack(state, 15, 3)
    assert first.roll.adv is AdvState.ADVANTAGE and first.roll.natural == 15
    assert conditions_of(state, "gob") == []
    second = _attack(state, 9)
    assert second.roll.adv is AdvState.NORMAL and second.roll.rolls == (9,)
    assert hit_chance(state, "b", "gob", CLAW, FEATS).adv is AdvState.NORMAL


def test_v1_m35_guided_is_used_up_by_a_miss_too() -> None:
    """Y2: the dagger and the longsword both rolled with it; a missed roll is still the roll."""
    state = _guided_fight()
    missed = _attack(state, 2, 1)
    assert not missed.hit and missed.roll.adv is AdvState.ADVANTAGE
    assert conditions_of(state, "gob") == []


def test_golden_guided_ends_at_the_end_of_the_casters_next_turn() -> None:
    # SRD 5.1 Guiding Bolt: unused, the advantage lasts until the end of the caster's next turn.
    state = _guided_fight()
    seen: list[list[str]] = []
    for _ in range(3):  # c ends, gob, b, then c's next turn starts
        next_turn(state, ScriptedRng())
        seen.append(conditions_of(state, "gob"))
    assert seen == [["guided"]] * 3
    enc = state.encounter
    assert enc is not None and enc.active_id() == "c"
    next_turn(state, ScriptedRng())  # the end of the caster's next turn
    assert conditions_of(state, "gob") == []


def test_only_guided_is_consumed_by_an_attack_against_its_bearer() -> None:
    names = ("guided", "blurred", "dodging", "prone", "invisibility", "hidden", "true-strike")
    assert {c for c in names if condition_def(c).consumed_by_attack_against} == {"guided"}


def _make(cid: str, *conds: ActiveCondition) -> Creature:
    return Creature(
        id=cid,
        name=cid.upper(),
        kind=CreatureKind.PC,
        max_hp=30,
        hp=30,
        abilities={a: 10 for a in Ability},
        conditions=list(conds),
    )


def _blessed() -> GameState:
    """The cleric concentrates on Bless on two allies."""
    state = GameState(campaign_id="t", seed=1)
    bless = new_condition("blessed", source_id="cleric", rounds=10, tick_creature_id="cleric")
    for c in (_make("cleric"), _make("a", bless), _make("b", bless)):
        apply(state, CreatureAdded(creature=c))
    links = [ConditionLink(creature_id=cid, name="blessed") for cid in ("a", "b")]
    _run(state, start_concentration(state, "cleric", "bless", links))
    return state


def _drop(state: GameState, cid: str) -> None:
    apply(state, ConditionRemoved(creature_id=cid, name="blessed", source_id="cleric"))


def test_v1_m35_concentration_ends_with_its_last_effect() -> None:
    """Y3 (typed 262-313): Guidance ended at the fight's end and Tamsin kept concentrating on
    nothing. One target left keeps it; the last one gone ends it."""
    state = _blessed()
    _drop(state, "a")
    assert orphaned_concentration_events(state) == []
    _drop(state, "b")
    assert orphaned_concentration_events(state) == [
        ConcentrationEnded(creature_id="cleric", spell_id="bless", reason="its last effect ended")
    ]
    _run(state, orphaned_concentration_events(state))
    assert state.creatures["cleric"].concentrating_on is None
    assert orphaned_concentration_events(state) == []


def test_concentration_on_a_removed_creature_ends() -> None:
    state = _blessed()
    _drop(state, "a")
    apply(state, CreatureRemoved(creature_id="b"))
    ended = orphaned_concentration_events(state)
    assert [type(e) for e in ended] == [ConcentrationEnded]


def test_concentration_without_links_is_left_alone() -> None:
    state = GameState(campaign_id="t", seed=1)
    apply(state, CreatureAdded(creature=_make("cleric")))
    _run(state, start_concentration(state, "cleric", "hold-person"))
    assert state.creatures["cleric"].concentrating_on is not None
    assert orphaned_concentration_events(state) == []


def test_ending_concentration_removes_every_linked_condition() -> None:
    """The reverse direction: concentration ends -> its conditions end, with the end first so
    the orphan check never fires half way through the list."""
    state = _blessed()
    events = end_concentration(state, "cleric", "x")
    assert isinstance(events[0], ConcentrationEnded)
    assert [e.creature_id for e in of(events, ConditionRemoved)] == ["a", "b"]
    for event in events:
        apply(state, event)
        assert orphaned_concentration_events(state) == []
    assert conditions_of(state, "a") == conditions_of(state, "b") == []
