"""Downed heroes outside a fight (M20.2, playtest 3: a hero at 0 HP after a won fight could not be
raised by anything outside a fight): stable when the fight ends, helped up to 1 HP by an ally."""

import pytest

from aidm.models.damage import DamagePacket, DamageType
from aidm.models.encounter import Encounter
from aidm.models.events import CreatureDied, HpChanged, Stabilized
from aidm.models.state import GameState
from aidm.rules.damage import UNCONSCIOUS, resolve_damage
from aidm.rules.death import is_dying
from aidm.rules.downed import (
    HelpUpRefusal,
    HelpUpRefused,
    downed_heroes,
    help_up_events,
    stabilise_after_fight,
)
from aidm.session.reducer import apply, replay
from tests.ai.tool_fixtures import party_state
from tests.unit.rules.combat_fixtures import small_map


def _down(state: GameState, cid: str) -> None:
    target = state.creatures[cid]
    packet = DamagePacket(amount=target.hp, damage_type=DamageType.PIERCING)
    for event in resolve_damage(target, [packet]):
        apply(state, event)


def _state(*down: str) -> GameState:
    state = party_state()
    for cid in down:
        _down(state, cid)
    return state


def test_downed_heroes_are_the_living_at_zero() -> None:
    state = _state("rogue", "wizard")
    apply(state, CreatureDied(creature_id="wizard"))
    assert [c.id for c in downed_heroes(state)] == ["rogue"]


def test_stabilise_after_fight_only_the_dying() -> None:
    state = _state("rogue", "wizard")
    apply(state, Stabilized(creature_id="wizard"))
    assert stabilise_after_fight(state) == [Stabilized(creature_id="rogue")]
    for event in stabilise_after_fight(state):
        apply(state, event)
    assert not is_dying(state.creatures["rogue"]) and state.creatures["rogue"].hp == 0
    assert stabilise_after_fight(state) == []


def test_help_up_raises_a_downed_ally_to_one_hp() -> None:
    initial = _state("rogue")
    state = initial.model_copy(deep=True)
    events = help_up_events(state, "fighter", "rogue")
    assert events[0] == HpChanged(creature_id="rogue", delta=1, new_hp=1)
    for event in events:
        apply(state, event)
    rogue = state.creatures["rogue"]
    assert rogue.hp == 1 and UNCONSCIOUS not in {c.name for c in rogue.conditions}
    assert rogue.death_save_failures == 0 and not rogue.stable
    assert replay(initial, events) == state


@pytest.mark.parametrize(
    ("helper", "target", "reason"),
    [
        ("rogue", "fighter", HelpUpRefusal.HELPER_DOWN),
        ("fighter", "wizard", HelpUpRefusal.NOT_DOWN),
        ("fighter", "fighter", HelpUpRefusal.UNKNOWN_TARGET),
        ("fighter", "nobody", HelpUpRefusal.UNKNOWN_TARGET),
        ("fighter", "cleric", HelpUpRefusal.FALLEN),
    ],
)
def test_help_up_refusals(helper: str, target: str, reason: HelpUpRefusal) -> None:
    state = _state("rogue", "cleric")
    apply(state, CreatureDied(creature_id="cleric"))
    with pytest.raises(HelpUpRefused) as refused:
        help_up_events(state, helper, target)
    assert refused.value.reason is reason and refused.value.detail


def test_help_up_in_a_fight_is_the_help_action() -> None:
    state = _state("rogue")
    state.encounter = Encounter(id="f1", zone_map=small_map())
    with pytest.raises(HelpUpRefused) as refused:
        help_up_events(state, "fighter", "rogue")
    assert refused.value.reason is HelpUpRefusal.IN_FIGHT
