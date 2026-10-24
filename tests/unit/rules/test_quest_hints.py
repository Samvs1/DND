"""What now? (M23.8): goldens on the sample campaign and the Slendee act-2 save, the hidden-item
and undiscovered-route rules, travel hops, and why a locked way is shut (`rules.gateway_lock`)."""

from aidm.models.state import GameState
from aidm.models.world import RouteProgress
from aidm.rules.gateway_lock import locked_reason, short_reason
from aidm.rules.quest_hints import FIGHTING, MAX_LINES, NOTHING, ONE_ROUTE, what_now
from aidm.rules.world_graph import travel_route
from tests.session.quest_offer_fixtures import (
    R1,
    accept,
    fresh,
    go,
    resolve_region_one,
    settle,
    slendee_in_act_two,
)

MAIN = "main-gullmere-quay"
LEDGER = "missing-ledger"
FORCE_LINE = (
    "Defeat the master of Gullmere Quay: Explore every corner of Gullmere Quay. "
    "0 of 3 places seen; next: Rotting Boathouse."
)
PEACE_LINE = (
    "Turn the master of Gullmere Quay against the Choir: Find the Choir tide-orders at Saltcellar"
    " Tunnels. Where: Saltcellar Tunnels. It is hidden there: search when you arrive."
)


def _slendee() -> GameState:
    _, state, log, _ = slendee_in_act_two()
    settle(state, list(log[-2:]), log)
    return state


def test_golden_what_now_sample_fresh_act_one() -> None:
    _, state, _ = fresh()
    assert what_now(state) == (
        FORCE_LINE,
        PEACE_LINE,
        ONE_ROUTE,
        "Tobin Marrow is waiting for your answer: The Missing Ledger (Play tab).",
    )


def test_golden_what_now_after_accepting_the_ledger() -> None:
    _, state, log = fresh()
    accept(state, LEDGER, log)
    assert what_now(state)[3] == (
        "The Missing Ledger (for Tobin Marrow): Win the fight at Saltcellar Tunnels."
        " Where: Saltcellar Tunnels."
    )


def test_golden_what_now_away_from_the_docks_shows_the_card_and_the_lead() -> None:
    _, state, log = fresh()
    accept(state, LEDGER, log)
    go(state, "rotting-boathouse", log)
    lines = what_now(state)
    assert lines[0] == "Danger bars the way here: choose what to do on the encounter card."
    assert lines[1].endswith("1 of 3 places seen; next: Saltcellar Tunnels.")
    assert lines[-1] == "Someone at Gullmere Quay may need help."


def test_golden_what_now_names_the_next_hop_two_places_away() -> None:
    _, state, log = fresh()
    go(state, "rotting-boathouse", log)
    assert state.campaign is not None
    state.campaign.offer = None
    state.world.visited.append("saltcellar-tunnels")
    assert travel_route(state.world, "rotting-boathouse", "heron-marsh-causeway") == (
        "gullmere-quay-docks",
        "heron-marsh-causeway",
    )
    assert what_now(state)[0].endswith(
        "2 of 3 places seen; next: Heron Marsh Causeway, two places away via Gullmere Quay."
    )


def test_golden_what_now_after_resolution_the_way_on_is_open() -> None:
    _, state, log = fresh()
    accept(state, LEDGER, log)
    resolve_region_one(state, log)
    assert what_now(state) == (
        "The way on to Lamplighters' Rest is open.",
        "Harbourmaster Odalys Prend at Gullmere Quay asked you: Break the Smugglers.",
    )


def test_golden_what_now_slendee_act_two() -> None:
    lines = what_now(_slendee())
    assert lines == (
        "Defeat the master of Gloomfen Wetlands: Explore every corner of Gloomfen Wetlands."
        " 0 of 3 places seen; next: Sorrow Runnel.",
        "Old Carrion Vess is waiting for your answer: The Man in the Runnel (Play tab).",
        "Mistress Kree the Ragged at Mirkfall Thicket asked you: Roots Over Water.",
    )
    text = " ".join(lines)
    for act_one in ("Bell's False Tongue", "Ferrystones", "False Saint", "Knight's Penance"):
        assert act_one not in text
    assert "Raveth" not in text  # a boss the party has not reached is not named


def test_hidden_item_place_is_never_told_beyond_the_step_text() -> None:
    _, state, _ = fresh()
    item = next(i for i in state.world.items.values() if i.quest_id == MAIN)
    item.node_id = "rotting-boathouse"  # hidden somewhere the step text does not name
    peace = what_now(state)[1]
    assert peace.endswith("It is hidden: search the places you visit.")
    assert "Rotting Boathouse" not in peace


def _without_peace(state: GameState) -> None:
    quest = state.world.quests[MAIN]
    routes = (RouteProgress(route_id="force"),)
    state.world.quests[MAIN] = quest.model_copy(update={"routes": routes})


def test_undiscovered_route_only_as_the_nudge() -> None:
    _, state, _ = fresh()
    _without_peace(state)
    with_offer = " ".join(what_now(state))
    assert "tide-orders" not in with_offer and "Dessa" not in with_offer  # the card is open
    state.world.quest_ask = None
    del state.world.quests[LEDGER]
    lines = what_now(state)
    assert lines == (
        FORCE_LINE,
        "Dessa Orrin here with you may know another way past the master of Gullmere Quay.",
    )


def test_no_hint_npc_falls_back_to_the_unexplored_exits() -> None:
    _, state, _ = fresh()
    _without_peace(state)
    state.world.quest_ask = None
    del state.world.quests[LEDGER]
    state.world.npcs["dessa-orrin"].dead = True
    assert what_now(state)[-1] == (
        "Unexplored from here: Rotting Boathouse, Saltcellar Tunnels, Heron Marsh Causeway."
    )


def test_what_now_is_short_has_no_ids_and_never_changes_the_state() -> None:
    _, state, log = fresh()
    accept(state, LEDGER, log)
    before = state.model_dump()
    lines = what_now(state)
    assert state.model_dump() == before
    assert 1 <= len(lines) <= MAX_LINES
    ids = [*state.world.npcs, *state.world.node_names, MAIN, LEDGER]
    assert not any(i in line for i in ids if "-" in i for line in lines)


def test_fight_comes_first_and_no_campaign_says_nothing() -> None:
    assert what_now(GameState(campaign_id="none", seed=1)) == (NOTHING,)
    assert FIGHTING.startswith("First win this fight")


def test_golden_locked_gateway_says_why() -> None:
    _, state, _ = fresh()
    assert locked_reason(state, R1.gateway.id) == (
        "The Sunken Vestry stays shut while Gullmere Quay still hides places you have not seen:"
        " 3 left (Rotting Boathouse, Saltcellar Tunnels, Heron Marsh Causeway)."
    )
    assert short_reason(state, R1.gateway.id) == (
        "locked until every place of Gullmere Quay is seen, 3 left"
    )
    assert locked_reason(state, "rotting-boathouse") is None  # not locked


def test_golden_locked_way_on_until_the_master_is_dealt_with() -> None:
    _, state, _ = fresh()
    for spoke in R1.spokes:
        state.world.visited.append(spoke.id)
    state.world.current_node = R1.gateway.id
    state.world.visited.append(R1.gateway.id)
    assert "lamplighters-rest" in state.world.locked_nodes
    assert locked_reason(state, "lamplighters-rest") == (
        "The way on opens once the master of Gullmere Quay is dealt with."
    )
    assert short_reason(state, "lamplighters-rest") == (
        "locked until the master of Gullmere Quay is dealt with"
    )
