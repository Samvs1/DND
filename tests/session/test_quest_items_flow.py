"""M23.3 quest items through the session: the golden Peace walk of sample act 1 with the PLACED
tide-orders (search, pick up, hand to Gorran -> Peace done -> allied -> region resolved by
alliance), the next act's items on resolution, the old-save backfill, and the table's typed
pick-up / give and the `give` command."""

from pathlib import Path

from aidm.dm.precheck import TakeIntent, precheck
from aidm.dm.tool_context import ToolContext
from aidm.dm.tool_exec import execute_tool
from aidm.models.campaign_events import RegionResolved
from aidm.models.campaign_state import OfferChoice, RegionResolution
from aidm.models.encounter import EncounterStatus, Side
from aidm.models.events import AnyEvent, CreatureDied, event_adapter
from aidm.models.protocol_client import Give, SubmitAction
from aidm.models.protocol_server import ErrorMsg, NarrationChunkMsg
from aidm.models.quest_events import KeepsakeGiven, QuestStepDone
from aidm.models.state import GameState
from aidm.models.world import QuestState
from aidm.models.world_events import ItemDiscovered, ItemPlaced, PartyMoved
from aidm.rules.encounter import end_encounter
from aidm.rules.equipment import take_events
from aidm.rules.handing import give_events
from aidm.rules.plan_ids import boss_npc_id, main_quest_id, quest_item_id
from aidm.session.quest_flow import settle_after
from aidm.session.reducer import replay
from tests.ai.tool_fixtures import tool_call
from tests.session.progression_fixtures import (
    REGS,
    Rigged,
    answer,
    apply_all,
    campaign_state,
    move,
    plan,
)
from tests.session.table_fixtures import assert_replays, fake_llm, join, of_type, running

R1 = plan().acts[0].region
MAIN = main_quest_id(R1)
BOSS = boss_npc_id(R1)
PEACE = "the-tide-orders"
ORDERS = quest_item_id(MAIN, PEACE, 0, 0)
TUNNELS = "saltcellar-tunnels"


def _settle(state: GameState, batch: list[AnyEvent], log: list[AnyEvent]) -> list[AnyEvent]:
    return settle_after(state, REGS, batch, lambda events: apply_all(state, events, log))


def _go(state: GameState, node: str, log: list[AnyEvent]) -> list[AnyEvent]:
    mark = len(log)
    move(state, node, log)
    return _settle(state, log[mark:], log)


def _fight_and_win(state: GameState, log: list[AnyEvent]) -> None:
    mark = len(log)
    answer(state, OfferChoice.FIGHT, log)
    enc = state.encounter
    assert enc is not None
    for cid, combatant in sorted(enc.combatants.items()):
        if combatant.side is Side.HOSTILE:
            apply_all(state, [CreatureDied(creature_id=cid)], log)
    apply_all(state, end_encounter(state, EncounterStatus.VICTORY), log)
    _settle(state, log[mark:], log)


def _search_and_take(state: GameState, log: list[AnyEvent]) -> list[AnyEvent]:
    call = tool_call(
        "request_check", actor="fighter", ability_or_skill="perception", dc_tier="hard"
    )
    result = execute_tool(state, call, ToolContext("fighter"), Rigged(True), REGS)
    assert result.ok, result.error
    assert ItemDiscovered(item_id=ORDERS, creature_id="fighter") in result.events
    apply_all(state, list(result.events), log)
    intent = precheck(state, "fighter", "I pick up the Choir tide-orders")
    assert intent == TakeIntent("fighter", ORDERS)
    taken = apply_all(state, take_events(state, state.creatures["fighter"], ORDERS), log)
    return _settle(state, taken, log)


def _peace_steps(log: list[AnyEvent]) -> list[int]:
    return [e.step for e in log if isinstance(e, QuestStepDone) and e.route_id == PEACE]


def test_golden_peace_walk_with_the_placed_tide_orders() -> None:
    start, state, log = campaign_state()
    _settle(state, list(log), log)
    assert state.world.items[ORDERS].hidden
    for spoke in R1.spokes:
        if state.world.current_node != R1.arrival.id:
            _go(state, R1.arrival.id, log)
        _go(state, spoke.id, log)
        _fight_and_win(state, log)
        if spoke.id == TUNNELS:
            moved = _search_and_take(state, log)
            assert [(type(e), getattr(e, "route_id", None)) for e in moved] == [
                (QuestStepDone, PEACE)
            ]
    _go(state, R1.gateway.id, log)
    given = apply_all(state, give_events(state, "fighter", BOSS, ORDERS, REGS.tiers), log)
    assert given == [KeepsakeGiven(creature_id="fighter", keepsake_id=ORDERS, npc_id=BOSS)]
    allied = _settle(state, given, log)
    resolved = [(e.region_id, e.how) for e in allied if isinstance(e, RegionResolved)]
    assert resolved == [(R1.id, RegionResolution.ALLIANCE)]
    assert [k.id for k in state.world.npcs[BOSS].keepsakes] == [ORDERS]
    main = state.world.quests[MAIN]
    assert main.state is QuestState.COMPLETED and main.log[-1] == "Gorran Hookhand was won over."
    assert _peace_steps(log) == [0, 1]
    # act 2 starts: its quest items lie in the next region (the drowned hymnal)
    act2 = [e.item for e in allied if isinstance(e, ItemPlaced)]
    assert [(i.name, i.node_id) for i in act2] == [("Drowned hymnal", "salt-barrow")]
    assert _settle(state, [], log) == []
    decoded = [event_adapter.validate_json(e.model_dump_json()) for e in log]
    assert replay(start, decoded).model_dump() == state.model_dump()


def test_old_saves_get_their_current_act_items_through_the_settle() -> None:
    _, state, log = campaign_state()
    del state.world.items[ORDERS]  # a save from before M23.3
    placed = [e for e in _settle(state, [], log) if isinstance(e, ItemPlaced)]
    assert [e.item.id for e in placed] == [ORDERS]
    assert not [e for e in _settle(state, [], log) if isinstance(e, ItemPlaced)]


def _table_state() -> GameState:
    _, state, log = campaign_state()
    _settle(state, list(log), log)
    world = state.world
    for node in (TUNNELS,):
        moved = PartyMoved(
            from_node=world.current_node, to_node=node, scene_index=world.scene_index + 1
        )
        apply_all(state, [moved])
    apply_all(state, [ItemDiscovered(item_id=ORDERS, creature_id="fighter")])
    return state


async def test_typed_pick_up_and_give_at_the_table(tmp_path: Path) -> None:
    llm, _ = fake_llm(tmp_path)
    async with running(llm, _table_state()) as (table, _):
        ann = await join(table, "Ann", "fighter")
        ann.send(SubmitAction(text="I pick up the Choir tide-orders"))
        await table.settle()
        told = " ".join(m.text for m in of_type(ann.drain(), NarrationChunkMsg))
        assert "picks up the Choir tide-orders" in told
        peace = table.state.world.quests[MAIN].route(PEACE)
        assert peace is not None and peace.steps_done == 1
        ann.send(SubmitAction(text="I give the tide-orders to Gorran"))
        await table.settle()
        refused = of_type(ann.drain(), ErrorMsg)
        assert [m.text for m in refused] == ["Gorran Hookhand is not here."]
        world = table.state.world
        moved = PartyMoved(from_node=world.current_node, to_node=R1.gateway.id, scene_index=9)
        table.apply(moved)
        ann.send(Give(npc_id=BOSS, item_id=ORDERS))
        await table.settle()
        assert [k.id for k in table.state.world.npcs[BOSS].keepsakes] == [ORDERS]
        assert table.state.world.quests[MAIN].state is QuestState.COMPLETED
        assert_replays(table)
