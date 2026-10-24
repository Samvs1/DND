"""M23.2 step checks: every step kind reads the state (rules/quest_steps.py)."""

from aidm.models.character import InventoryItem, Keepsake
from aidm.models.dm_tiers import AttitudeBand
from aidm.models.quests import QuestStep, StepKind
from aidm.models.state import GameState
from aidm.models.world import Fact, Quest
from aidm.rules.milestones import clear_key
from aidm.rules.quest_steps import npc_meetable, step_count, step_met, steps_met
from aidm.rules.social import ALLY_BAR
from tests.session.progression_fixtures import campaign_state

OWNER = "missing-ledger"
BOSS = "boss-gullmere-quay"
TOBIN = "tobin-marrow"
DOCKS = "gullmere-quay-docks"
SPOKES = ("rotting-boathouse", "saltcellar-tunnels", "heron-marsh-causeway")


def _state() -> GameState:
    return campaign_state()[1]


def _hero(state: GameState) -> str:
    return next(cid for cid, c in sorted(state.creatures.items()) if c.pc is not None)


def _active(state: GameState, step: QuestStep) -> None:
    """`OWNER` accepted now (M29.9b: only arrivals after `active_since` count)."""
    quest = Quest(id=OWNER, title="Ledger", steps=(step,), active_since=state.event_count)
    state.world.quests[OWNER] = quest


def test_visit_counts_each_place() -> None:
    state = _state()
    step = QuestStep(kind=StepKind.VISIT, text="Explore", nodes=SPOKES)
    _active(state, step)
    assert step_count(state, step, OWNER) == 0
    state.world.visited += list(SPOKES)  # earlier visits never count (T3 T14)
    assert step_count(state, step, OWNER) == 0
    for node in SPOKES[:2]:
        state.world.arrived[node] = state.event_count + 1
    assert step_count(state, step, OWNER) == 2 and not step_met(state, step, OWNER)
    state.world.arrived[SPOKES[2]] = state.event_count + 2
    assert step_met(state, step, OWNER)


def test_clear_reads_the_spoke_milestone_and_the_gateway_boss() -> None:
    state = _state()
    assert state.campaign is not None
    step = QuestStep(kind=StepKind.CLEAR, text="Clear", nodes=(SPOKES[1],))
    assert not step_met(state, step, OWNER)
    state.campaign.milestones.append(clear_key(SPOKES[1]))
    assert step_met(state, step, OWNER)
    gate = QuestStep(kind=StepKind.CLEAR, text="Clear the vestry", nodes=("sunken-vestry",))
    assert not step_met(state, gate, OWNER)


def test_defeat_needs_the_npc_dead() -> None:
    state = _state()
    step = QuestStep(kind=StepKind.DEFEAT, text="Defeat", npc=BOSS)
    assert not step_met(state, step, OWNER)
    state.world.npcs[BOSS].dead = True
    assert step_met(state, step, OWNER)


def test_obtain_counts_quest_items_and_inventory_never_flavour() -> None:
    state = _state()
    pc = state.creatures[_hero(state)].pc
    assert pc is not None
    step = QuestStep(kind=StepKind.OBTAIN, text="Gather", item="Ember-stone", count=3, nodes=SPOKES)
    pc.keepsakes.append(Keepsake(id="flavour", name="Ember-stone"))
    assert step_count(state, step, OWNER) == 0
    pc.keepsakes.append(Keepsake(id="e1", name="Ember-stone", quest_id=OWNER))
    pc.keepsakes.append(Keepsake(id="e2", name="ember stone", quest_id=OWNER))
    assert step_count(state, step, OWNER) == 2 and not step_met(state, step, OWNER)
    pc.inventory.append(InventoryItem(item="ember-stone", qty=1))
    assert step_met(state, step, OWNER)
    # M29.7c R11: one quest item serves every quest that needs it (DECISIONS M29.7c)
    assert step_count(state, step, "another-quest") == 3


def test_deliver_needs_the_npc_to_hold_it() -> None:
    state = _state()
    step = QuestStep(kind=StepKind.DELIVER, text="Show him", item="Choir tide-orders", npc=BOSS)
    assert not step_met(state, step, OWNER)
    state.world.npcs[BOSS].keepsakes.append(
        Keepsake(id="orders", name="Choir tide-orders", quest_id=OWNER)
    )
    assert step_met(state, step, OWNER)


def _taken_on_early(state: GameState, step: QuestStep, since: int = 0) -> None:
    """`OWNER` accepted at seq `since` (0: before the party arrived at the docks)."""
    state.world.quests[OWNER] = Quest(id=OWNER, title="Ledger", steps=(step,), active_since=since)


def test_meet_needs_the_npc_here_alive_and_not_hostile() -> None:
    state = _state()
    step = QuestStep(kind=StepKind.MEET, text="Bring word", npc=TOBIN)
    _taken_on_early(state, step, since=state.event_count)
    assert not step_met(state, step, OWNER)  # M29.9b: standing with Tobin when accepting
    _taken_on_early(state, step)
    assert state.world.current_node == DOCKS and step_met(state, step, OWNER)
    state.world.npcs[TOBIN].hostile = True
    assert not npc_meetable(state, TOBIN)
    state.world.npcs[TOBIN].hostile = False
    state.world.npcs[TOBIN].dead = True
    assert not step_met(state, step, OWNER)
    state.world.npcs[TOBIN].dead = False
    state.world.current_node = SPOKES[0]
    assert not step_met(state, step, OWNER)


def test_win_over_reaches_the_band_floor() -> None:
    state = _state()
    step = QuestStep(kind=StepKind.WIN_OVER, text="Win", npc=BOSS, band=AttitudeBand.ALLY)
    assert not step_met(state, step, OWNER)
    boss = state.world.npcs[BOSS]
    boss.deeds = ALLY_BAR - boss.base
    assert step_met(state, step, OWNER)
    boss.hostile = True
    assert not step_met(state, step, OWNER)


def test_learn_reads_what_the_engine_knows_never_ledger_facts() -> None:
    state = _state()
    step = QuestStep(kind=StepKind.LEARN, text="Find the tunnels", tag="saltcellar")
    _taken_on_early(state, step, since=state.event_count)
    state.world.facts.append(Fact(id="f1", text="The saltcellar tunnels exist"))
    assert not step_met(state, step, OWNER)
    state.world.visited.append(SPOKES[1])
    assert not step_met(state, step, OWNER)  # M29.7c R1: an old visit is not learned for it
    state.world.current_node = SPOKES[1]
    assert not step_met(state, step, OWNER)  # M29.9b: there at acceptance, no arrival since
    state.world.arrived[SPOKES[1]] = state.event_count + 1
    assert not step_met(state, step, OWNER)  # M31.1b V13c: the arrival alone teaches nothing
    state.world.learned["saltcellar"] = state.event_count + 2  # a look there recorded it
    assert step_met(state, step, OWNER)


def test_free_never_moves_and_steps_are_sequential() -> None:
    state = _state()
    free = QuestStep(kind=StepKind.FREE, text="Something only the story can judge")
    meet = QuestStep(kind=StepKind.MEET, text="Bring word", npc=TOBIN)
    _taken_on_early(state, meet)
    assert not step_met(state, free, OWNER)
    assert steps_met(state, (free, meet), 0, OWNER) == 0
    assert steps_met(state, (free, meet), 1, OWNER) == 2
    assert steps_met(state, (meet, free), 0, OWNER) == 1
