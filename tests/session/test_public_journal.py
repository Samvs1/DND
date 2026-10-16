"""Journal, map and shop fields of the public projection (M7.6): nothing private leaks."""

from aidm.data.item_catalogue import item_catalogue
from aidm.models.memory import SceneSummary
from aidm.models.protocol_views import TablePhase
from aidm.models.state import GameState
from aidm.models.world import Quest, QuestState
from aidm.models.world_events import QuestUpdated
from aidm.rules.progression import node_plan
from aidm.rules.quest_plan import main_world_quest
from aidm.rules.shop import StockEntry
from aidm.session.reducer import apply
from aidm.session.views import (
    public_map,
    public_quests,
    public_scene,
    public_state,
    public_summaries,
    stock_lines,
)
from tests.ai.guard_fixtures import inn_state
from tests.session.progression_fixtures import campaign_state


def _quest(state: GameState, quest_id: str) -> Quest:
    return state.world.quests[quest_id]


def test_offered_quest_shows_giver_and_objective_the_giver_asked_in_person() -> None:
    _start, state, _log = campaign_state()
    offered = {q.id: q for q in public_quests(state)}["missing-ledger"]
    assert offered.state == "offered" and "ledger" in offered.objective.lower()
    assert offered.giver == "Tobin Marrow"
    state.world.current_node = "gullmere-quay-docks"
    quest = _quest(state, "missing-ledger").model_copy(update={"state": QuestState.ACTIVE})
    apply(state, QuestUpdated(quest=quest))
    taken = {q.id: q for q in public_quests(state)}["missing-ledger"]
    assert taken.giver == "Tobin Marrow"
    assert "ledger" in taken.objective.lower()


def test_quest_objective_naming_private_text_is_left_out() -> None:
    _start, state, _log = campaign_state()
    plan_quest = state.campaign.plan.quests[0] if state.campaign else None
    assert plan_quest is not None
    quest = _quest(state, plan_quest.id).model_copy(update={"state": QuestState.ACTIVE})
    apply(state, QuestUpdated(quest=quest))
    state.world.npcs[plan_quest.giver_npc_id].motive = plan_quest.objective
    assert {q.id: q for q in public_quests(state)}[plan_quest.id].objective == ""


def test_summaries_drop_lines_with_private_text() -> None:
    state = inn_state()
    state.world.npcs["npc-mira"].motive = "secretly sells maps to the cult"
    state.memory.summaries.append(SceneSummary(title="Arrival", text="The party reached the inn."))
    state.memory.summaries.append(
        SceneSummary(title="Rumour", text="Mira secretly sells maps to the cult, they say.")
    )
    shown = public_summaries(state)
    assert [s.title for s in shown] == ["Arrival"]
    view = public_state(state, phase=TablePhase.PLAY, paused=False, players=[])
    assert view.summaries == shown


def test_map_fogs_unvisited_nodes_and_marks_the_current_one() -> None:
    _start, state, _log = campaign_state()
    view = public_map(state)
    assert view is not None
    current = [n for n in view.nodes if n.current]
    assert len(current) == 1
    far = [n for n in view.nodes if not n.visited and not n.current]
    assert far and all(n.name == "Unexplored" for n in far)


def test_scene_lists_shopkeepers_present_and_peaceful() -> None:
    state = inn_state()
    scene = public_scene(state)
    assert scene is not None and scene.shopkeepers == ()
    state.world.npcs["npc-mira"].role = "merchant"
    scene = public_scene(state)
    assert scene is not None and scene.shopkeepers == ("npc-mira",)
    state.world.npcs["npc-mira"].hostile = True
    scene = public_scene(state)
    assert scene is not None and scene.shopkeepers == ()


def test_scene_terrain_is_the_first_terrain_tag_of_the_place() -> None:
    _start, state, _log = campaign_state()
    scene = public_scene(state)
    assert scene is not None
    node = node_plan(state, scene.node_id)
    assert node is not None and node.terrain_tags
    assert scene.terrain == node.terrain_tags[0]  # art key region_banner.<terrain> (M24)


def test_stock_lines_carry_category_and_camp_supplies() -> None:
    lines = stock_lines(
        [StockEntry(item="camp-stew-kit", price_gp=5), StockEntry(item="longsword", price_gp=15)],
        item_catalogue(),
    )
    assert (lines[0].category, lines[0].supply) == ("supply", 5)
    assert (lines[1].category, lines[1].supply) == ("weapon", 0)


def test_public_quests_send_done_steps_only_and_no_unmet_boss_name() -> None:
    _start, state, _log = campaign_state()
    plan = state.campaign.plan if state.campaign else None
    assert plan is not None
    apply(state, QuestUpdated(quest=main_world_quest(plan, 1)))
    main = next(q for q in public_quests(state) if q.kind == "main")
    assert main.steps_done == () and main.routes
    blob = " ".join(
        [r.title for r in main.routes] + [s for r in main.routes for s in r.steps_done]
    ).lower()
    boss_names = [n.name.lower() for n in state.world.npcs.values() if n.role == "boss"]
    assert all(name not in blob for name in boss_names)
    for route in main.routes:
        assert route.steps_done == ()
