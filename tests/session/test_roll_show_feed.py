"""M26.2 roll data on the wire: DiceView kind/target/source/parts/adv_why/difficulty, EventMsg
subject and amount, and old event logs (no M26.2 fields) still replaying to the same snapshot."""

from __future__ import annotations

import random
from typing import Any

from aidm.models.abilities import Ability, Skill
from aidm.models.checks import CheckKind, DcTier
from aidm.models.combat_events import AttackRolled
from aidm.models.commands import AttackCommand
from aidm.models.dice import AdvState, D20Roll, RollKind, RollPart
from aidm.models.encounter import Side
from aidm.models.events import (
    AnyEvent,
    CheckResolved,
    CreatureDied,
    DamageTaken,
    DeathSaveRolled,
    DiceRolled,
    HpChanged,
    LoggedEvent,
    event_adapter,
)
from aidm.models.protocol_server import EventMsg
from aidm.models.state import GameState
from aidm.rules.checks import skill_check
from aidm.rules.condition_timing import new_condition
from aidm.session.dice_view import dice_view
from aidm.session.public_feed import PublicFeed
from aidm.session.reducer import replay
from tests.unit.rules.combat_fixtures import ScriptedRng, do, fight, monster
from tests.unit.rules.encounter_fixtures import make_pc


def _sneak_attack() -> tuple[GameState, GameState, list[AnyEvent]]:
    state = fight(
        [
            (make_pc("a", class_index="rogue"), Side.PARTY, "gate"),
            (monster("gob", hp=40, ac=12), Side.HOSTILE, "gate"),
        ]
    )
    state.creatures["gob"].conditions.append(new_condition("prone"))
    initial = state.model_copy(deep=True)
    cmd = AttackCommand(actor_id="a", target_id="gob", option="main_hand")
    return initial, state, do(state, cmd, ScriptedRng(15, 2, 3, 4))


def test_attack_view_has_kind_target_and_reasons() -> None:
    _, _, events = _sneak_attack()
    views = [v for v in map(dice_view, events) if v is not None]
    assert [v.kind for v in views] == [RollKind.ATTACK, RollKind.DAMAGE, RollKind.DAMAGE]
    assert all(v.target_id == "gob" for v in views)
    assert views[0].adv_why == ("Prone",) and views[0].adv is AdvState.ADVANTAGE
    assert views[2].label == "Sneak Attack"


def test_check_view_carries_parts_difficulty_and_source() -> None:
    rogue = make_pc("a", class_index="rogue")
    result = skill_check(random.Random(3), rogue, Skill.STEALTH, 15)
    result = result.model_copy(update={"tier": DcTier.MEDIUM})
    view = dice_view(CheckResolved(creature_id="a", result=result))
    assert view is not None
    assert (view.kind, view.difficulty, view.source_id) == (RollKind.CHECK, "medium", None)
    assert view.parts == result.parts and sum(p.value for p in view.parts) == view.modifier
    save = result.model_copy(update={"kind": CheckKind.SAVE, "skill": None, "ability": Ability.DEX})
    saved = dice_view(CheckResolved(creature_id="gob", result=save, source_id="c"))
    assert saved is not None and (saved.kind, saved.source_id) == (RollKind.SAVE, "c")


def test_death_save_and_plain_dice_views() -> None:
    roll = D20Roll(rolls=(12,), natural=12, total=12)
    death = dice_view(DeathSaveRolled(creature_id="a", roll=roll, successes=1, failures=0))
    assert death is not None and (death.label, death.kind) == ("Death save", RollKind.DEATH_SAVE)
    assert death.parts == () and death.difficulty is None


def test_event_msg_names_subject_and_amount() -> None:
    _, state, _ = _sneak_attack()
    feed = PublicFeed()
    taken = feed.add_event(state, 5, DamageTaken(creature_id="gob", total=10, hp_lost=10))
    assert isinstance(taken, EventMsg)
    assert (taken.line, taken.subject_id, taken.amount) == ("", "gob", 10)
    healed = feed.add_event(state, 6, HpChanged(creature_id="a", delta=4, new_hp=9))
    assert isinstance(healed, EventMsg) and (healed.subject_id, healed.amount) == ("a", 4)
    lost = feed.add_event(state, 7, HpChanged(creature_id="gob", delta=-3, new_hp=27))
    assert isinstance(lost, EventMsg) and (lost.subject_id, lost.amount) == ("gob", None)
    died = feed.add_event(state, 8, CreatureDied(creature_id="gob"))
    assert isinstance(died, EventMsg) and (died.subject_id, died.amount) == ("gob", None)
    texts = [e.text for e in feed.history().entries]
    assert "" not in texts and len(texts) == 3


def _old_format(event: AnyEvent) -> dict[str, Any]:
    """The event as an event log written before M26.2 stored it (no M26.2 fields)."""
    data = event.model_dump(mode="json")
    if isinstance(event, DiceRolled):
        data.pop("kind")
        data.pop("target_id")
    if isinstance(event, AttackRolled):
        data.pop("adv_why")
    if isinstance(event, CheckResolved):
        data.pop("source_id")
        for key in ("parts", "adv_why", "tier"):
            data["result"].pop(key)
    return data


def test_an_old_event_log_still_replays_to_the_same_snapshot() -> None:
    initial, snapshot, events = _sneak_attack()
    rogue = snapshot.creatures["a"]
    check = skill_check(random.Random(4), rogue, Skill.STEALTH, 10)
    events = [*events, CheckResolved(creature_id="a", result=check, reason="sneak")]
    snapshot = replay(snapshot, events[-1:])
    old = [event_adapter.validate_python(_old_format(e)) for e in events]
    assert replay(initial, old).model_dump() == snapshot.model_dump()
    old_rolls = [e for e in old if isinstance(e, DiceRolled)]
    assert old_rolls and all(e.kind is RollKind.OTHER and e.target_id is None for e in old_rolls)
    old_check = old[-1]
    assert isinstance(old_check, CheckResolved) and old_check.result.parts == ()
    log = [LoggedEvent(seq=i, event=e) for i, e in enumerate(old)]
    feed = PublicFeed.rebuild(initial, log)
    assert [r.dice.kind for r in feed.rolls][0] is RollKind.ATTACK
    assert feed.rolls[-1].dice.parts == ()


def test_roll_part_is_a_plain_named_number() -> None:
    assert RollPart(name="DEX", value=3).model_dump() == {"name": "DEX", "value": 3}
