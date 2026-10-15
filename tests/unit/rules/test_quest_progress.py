"""M23.2 quest progress, one pass at a time (rules/quest_progress.py) on the sample campaign."""

import random

from aidm.models.campaign import RegionPlan
from aidm.models.character import Keepsake
from aidm.models.encounter import Encounter, Side, SurpriseKind
from aidm.models.encounter_events import EncounterStarted
from aidm.models.events import AnyEvent
from aidm.models.quest_events import QuestStepDone, RouteDiscovered
from aidm.models.quests import FORCE_ROUTE_ID, QuestKind
from aidm.models.state import GameState
from aidm.models.world import QuestState, RouteProgress
from aidm.models.world_events import AttitudeChanged, QuestUpdated, RewardGranted
from aidm.rules.encounter_offer import arrival_offer_events, offer_fight_events
from aidm.rules.milestones import clear_key
from aidm.rules.quest_progress import current_act, quest_progress_events, route_effects
from aidm.rules.quest_rewards import quest_payout
from aidm.rules.social import ALLY_BAR, attitude_score
from tests.session.progression_fixtures import DATA, REGS, apply_all, campaign_state, pending

MAIN = "main-gullmere-quay"
MAIN2 = "main-kelpglass-reach"
BOSS = "boss-gullmere-quay"
LEDGER = "missing-ledger"
TUNNELS = "saltcellar-tunnels"
PEACE = "the-tide-orders"


def _pass(state: GameState) -> list[AnyEvent]:
    return apply_all(state, quest_progress_events(state, REGS.tiers, REGS.catalogue))


def _started(away: bool = True) -> GameState:
    """Installed, the main quest backfilled; `away`: the party stands in a spoke (no hint NPC)."""
    state = campaign_state()[1]
    if away:
        state.world.current_node = "rotting-boathouse"
    _pass(state)
    return state


def _accept(state: GameState, quest_id: str) -> None:
    quest = state.world.quests[quest_id].model_copy(update={"state": QuestState.ACTIVE})
    apply_all(state, [QuestUpdated(quest=quest)])


def _hero_keeps(state: GameState, name: str, quest_id: str) -> None:
    hero = next(c for _, c in sorted(state.creatures.items()) if c.pc is not None)
    assert hero.pc is not None
    hero.pc.keepsakes.append(
        Keepsake(id=name.lower().replace(" ", "-"), name=name, quest_id=quest_id)
    )


def test_backfill_adds_the_current_act_main_quest_once() -> None:
    state = campaign_state()[1]
    assert current_act(state) == 1
    events = quest_progress_events(state, REGS.tiers, REGS.catalogue)
    added = [e.quest for e in events if isinstance(e, QuestUpdated)]
    assert [(q.id, q.kind, q.state) for q in added] == [(MAIN, QuestKind.MAIN, QuestState.ACTIVE)]
    assert added[0].routes == (RouteProgress(route_id=FORCE_ROUTE_ID),)
    apply_all(state, events)
    assert not any(isinstance(e, QuestUpdated) for e in _pass(state))


def test_offered_quests_never_move() -> None:
    state = _started()
    assert state.campaign is not None
    state.campaign.milestones.append(clear_key(TUNNELS))
    assert state.world.quests[LEDGER].state is QuestState.OFFERED
    assert _pass(state) == []


def test_active_side_quest_steps_then_completes_and_pays_once() -> None:
    state = _started()
    assert state.campaign is not None
    _accept(state, LEDGER)
    state.campaign.milestones.append(clear_key(TUNNELS))
    first = _pass(state)
    line = "Drive the smugglers out of the Saltcellar Tunnels"
    assert first == [QuestStepDone(quest_id=LEDGER, step=0, log_line=line)]
    assert _pass(state) == []  # Tobin is at the docks, the party is not
    state.world.current_node = "gullmere-quay-docks"
    assert [type(e) for e in _pass(state)] == [RouteDiscovered, QuestStepDone]
    done = _pass(state)
    assert isinstance(done[0], QuestUpdated) and done[0].quest.state is QuestState.COMPLETED
    payout = quest_payout(state, done[0].quest, REGS.tiers)
    assert payout is not None and payout.items == ("harbour-ledger",)
    assert [e.source for e in done if isinstance(e, RewardGranted)] == [LEDGER]
    assert any(isinstance(e, AttitudeChanged) and e.npc_id == "tobin-marrow" for e in done)
    assert _pass(state) == []


def test_a_done_step_discovers_an_unknown_route_first() -> None:
    state = _started()
    _hero_keeps(state, "Choir tide-orders", MAIN)
    events = _pass(state)
    assert events == [
        RouteDiscovered(quest_id=MAIN, route_id=PEACE),
        QuestStepDone(
            quest_id=MAIN,
            route_id=PEACE,
            step=0,
            log_line="Find the Choir's tide-orders in the Saltcellar Tunnels",
        ),
    ]


def test_meeting_the_hint_npc_discovers_the_route() -> None:
    state = _started(away=False)
    assert _pass(state) == [RouteDiscovered(quest_id=MAIN, route_id=PEACE)]
    assert state.world.quests[MAIN].route(PEACE) == RouteProgress(route_id=PEACE)


def test_finished_peace_route_gives_the_boss_the_deeds_to_ally() -> None:
    state = _started()
    _hero_keeps(state, "Choir tide-orders", MAIN)
    _pass(state)
    state.world.npcs[BOSS].keepsakes.append(
        Keepsake(id="orders", name="Choir tide-orders", quest_id=MAIN)
    )
    assert [e.step for e in _pass(state) if isinstance(e, QuestStepDone)] == [1]
    deeds = _pass(state)
    assert [type(e) for e in deeds] == [AttitudeChanged]
    assert attitude_score(state.world.npcs[BOSS]) == ALLY_BAR
    assert _pass(state) == []  # the alliance itself is progression's job (session test)


def _act2_at_gateway(level: int = 1) -> tuple[GameState, RegionPlan]:
    state = campaign_state(level)[1]
    assert state.campaign is not None
    region = state.campaign.plan.acts[1].region
    state.world.current_node = region.arrival.id
    _pass(state)
    assert set(state.world.quests) >= {MAIN, MAIN2}
    state.world.visited += [s.id for s in region.spokes]
    state.world.current_node = region.gateway.id
    return state, region


def _cunning_done(state: GameState, quest_id: str, route_id: str) -> None:
    quest = state.world.quests[quest_id]
    routes = (*quest.routes, RouteProgress(route_id=route_id, steps_done=2))
    apply_all(state, [QuestUpdated(quest=quest.model_copy(update={"routes": routes}))])


def _boss_fight(state: GameState) -> Encounter:
    apply_all(state, arrival_offer_events(state, DATA, None))
    offer = pending(state)
    assert offer.boss_npc_id is not None
    events = offer_fight_events(state, offer, DATA, random.Random(2), SurpriseKind.NONE)
    return next(e.encounter for e in events if isinstance(e, EncounterStarted))


def test_cunning_route_surprises_the_boss() -> None:
    state, region = _act2_at_gateway()
    assert route_effects(state, region) == frozenset()
    plain = _boss_fight(state.model_copy(deep=True))
    assert not any(c.surprised for c in plain.combatants.values())
    _cunning_done(state, MAIN2, "the-back-stair")
    assert route_effects(state, region) == frozenset({"boss_surprised"})
    fight = _boss_fight(state)
    hostile = [c for c in fight.combatants.values() if c.side is Side.HOSTILE]
    assert hostile and all(c.surprised for c in hostile)


def test_cunning_route_sends_the_boss_alone() -> None:
    state, region = _act2_at_gateway(level=5)
    assert state.campaign is not None
    plan = state.campaign.plan
    act = plan.acts[1]
    assert act.main is not None
    routes = tuple(
        r.model_copy(update={"effect": "boss_alone"}) if r.effect else r for r in act.main.routes
    )
    main = act.main.model_copy(update={"routes": routes})
    acts = (plan.acts[0], act.model_copy(update={"main": main}), *plan.acts[2:])
    state.campaign.plan = plan.model_copy(update={"acts": acts})
    assert pending_company(state) > 0
    _cunning_done(state, MAIN2, "the-back-stair")
    assert route_effects(state, region) == frozenset({"boss_alone"})
    assert pending_company(state) == 0


def pending_company(state: GameState) -> int:
    trial = state.model_copy(deep=True)
    apply_all(trial, arrival_offer_events(trial, DATA, None))
    return len(pending(trial).monster_ids)
