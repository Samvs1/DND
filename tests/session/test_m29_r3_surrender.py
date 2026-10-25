"""M29.9a T12: a successful demand to surrender changes the fight (docs/playtests/M29_round3.md),
reproduced from the r3-items save: Tamsin calls on Sorrel Myn (the region master, 2 HP) and her
three standing cultists to surrender (663-664)."""

from pathlib import Path

from aidm.data.dm_tiers import dm_tiers
from aidm.dm.surrender_intent import surrender_intent
from aidm.models.abilities import Skill
from aidm.models.campaign_events import RegionResolved
from aidm.models.damage import DamagePacket, DamageType
from aidm.models.encounter import EncounterStatus
from aidm.models.encounter_events import EncounterEnded
from aidm.models.events import CheckResolved, ConditionApplied, ConditionRemoved, DamageTaken
from aidm.models.protocol_client import SubmitAction
from aidm.models.state import GameState
from aidm.rules.acts_fight import SurrenderIntent
from aidm.rules.damage import resolve_damage
from aidm.rules.encounter import encounter_outcome, end_encounter, kill_xp
from aidm.rules.harm_ends import harm_ended_events
from aidm.rules.progression import region_resolution_events
from aidm.rules.surrender import demand_surrender, surrender_dc
from aidm.session import combat_flow
from aidm.session.reducer import apply
from tests.session.playtest_saves import replay_until
from tests.session.table_fixtures import assert_replays, disabled_llm, join, running
from tests.unit.rules.combat_fixtures import ScriptedRng

TEXT = "I lower my bow and call out for Sorrel Myn and her cultists to surrender, they are beaten"
STANDING = ["cultist-1", "cultist-3", "cultist-4", "cultist-5"]


def _surrendered() -> GameState:
    state = replay_until("r3-items", 663)
    events = demand_surrender(ScriptedRng(18), state, "pc-p8", Skill.INTIMIDATION, dm_tiers())
    for event in events:
        apply(state, event)
    return state


def test_m29_surrender_demand_is_read() -> None:
    state = replay_until("r3-items", 663)
    assert surrender_intent(state, "pc-p8", TEXT) == SurrenderIntent("pc-p8", Skill.INTIMIDATION)
    spare = surrender_intent(state, "pc-p8", "I plead with them to yield, we will spare them")
    assert spare == SurrenderIntent("pc-p8", Skill.PERSUASION)
    assert surrender_intent(state, "pc-p8", "I surrender") is None
    # tier 1, the master among the foes, one cultist already down: the boss table's easy DC
    assert surrender_dc(state, dm_tiers()) == 10


def test_m29_successful_surrender_ends_the_fight_as_victory() -> None:
    state = _surrendered()
    held = [
        c.id for c in state.creatures.values() if any(x.name == "surrendered" for x in c.conditions)
    ]
    assert sorted(held) == STANDING
    assert encounter_outcome(state) is EncounterStatus.VICTORY
    assert kill_xp(state) == 125  # 5 cultists x 25 XP (SRD 5.1 Cultist, CR 1/8)
    for event in end_encounter(state, EncounterStatus.VICTORY):
        apply(state, event)
    resolved = [e for e in region_resolution_events(state) if isinstance(e, RegionResolved)]
    assert [(e.region_id, e.how.value) for e in resolved] == [("skarelen-vale", "defeat")]


def test_m29_failed_surrender_changes_nothing_but_the_action() -> None:
    state = replay_until("r3-items", 663)
    events = demand_surrender(ScriptedRng(2), state, "pc-p8", Skill.INTIMIDATION, dm_tiers())
    assert not any(isinstance(e, ConditionApplied) for e in events)
    for event in events:
        apply(state, event)
    assert state.encounter is not None
    assert not state.encounter.combatants["pc-p8"].economy.action
    assert encounter_outcome(state) is None


def test_m29_party_blow_ends_a_surrender_but_old_fire_does_not() -> None:
    state = _surrendered()
    cultist = state.creatures["cultist-3"]
    hit = resolve_damage(
        cultist, [DamagePacket(amount=1, damage_type=DamageType.FIRE)], source_id="pc-p2"
    )
    taken = hit[0]
    assert isinstance(taken, DamageTaken)
    burn = harm_ended_events(state, taken, direct=False)  # oil the party lit before
    assert burn == []
    blow = harm_ended_events(state, taken)  # a hero's attack or spell
    assert [(e.creature_id, e.name) for e in blow if isinstance(e, ConditionRemoved)] == [
        ("cultist-3", "surrendered")
    ]


def test_m29_the_mindless_never_surrender() -> None:
    state = replay_until("r3-items", 663)
    state.creatures["cultist-4"].creature_type = "undead"
    events = demand_surrender(ScriptedRng(18), state, "pc-p8", Skill.INTIMIDATION, dm_tiers())
    held = sorted(e.creature_id for e in events if isinstance(e, ConditionApplied))
    assert held == ["cultist-1", "cultist-3", "cultist-5"]
    for event in events:
        apply(state, event)
    assert encounter_outcome(state) is None  # the undead one fights on


async def test_m29_typed_surrender_is_one_engine_check(tmp_path: Path) -> None:
    """r3-items 663: the typed demand at the table rolls ONE surrender check (not a story roll)
    and, on a success, the yielding foes end the fight."""
    state = replay_until("r3-items", 663)
    async with running(disabled_llm(tmp_path), state) as (table, _):
        table.in_combat = True
        seat = await join(table, "Ann", "pc-p8")
        table.schedule(lambda: combat_flow.advance(table))
        await table.settle()
        start = table.state.event_count
        seat.send(SubmitAction(text=TEXT))
        await table.settle()
        assert_replays(table)
        events = [e.event for e in table.log if e.seq >= start]
    checks = [e for e in events if isinstance(e, CheckResolved)]
    assert [c.reason for c in checks][:1] == ["surrender"]
    yielded = any(
        isinstance(e, ConditionApplied) and e.condition.name == "surrendered" for e in events
    )
    assert yielded == checks[0].result.success
    if yielded:
        assert any(
            isinstance(e, EncounterEnded) and e.status is EncounterStatus.VICTORY for e in events
        )
