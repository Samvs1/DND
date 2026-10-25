"""M32.1a X6 and X7 (docs/playtests/M31_round5.md): compound and counted lines, travel further
than the next road, hand-overs to masters, and the reason for a turn that changed nothing, on
the real round-5 states."""

from pathlib import Path

from aidm.dm.narration_templates import QUIET_LINE, template_narration
from aidm.dm.refusal_text import NOT_DONE, NOTHING_ALLOWS, refusal_line
from aidm.models.combat_events import AttackRolled, CombatantMoved
from aidm.models.dm_tiers import DeltaTier
from aidm.models.protocol_client import ConfirmHostile, SubmitAction
from aidm.models.quest_events import KeepsakeGiven, QuestStepDone
from aidm.models.world_events import AttitudeChanged, EquipmentChanged, PartyMoved
from aidm.rules.offer_answer import sure_parley
from aidm.rules.social import hostile_attitude_events, social_attitude_events
from aidm.session import combat_flow
from tests.session.m32_play import FULL, QUESTS, TYPED, play, typed
from tests.session.playtest_saves import replay_until
from tests.session.table_fixtures import assert_replays, join, menu_down, pick, running

SALT = "qi-salt-for-the-elders-own-0-"
LANTERN = "qi-main-the-rookery-reaches-salt-the-wound-0-"
BARROW = "barrow-of-the-hollow-king"


async def test_v1_m32_compound_gear_line_does_both_halves(tmp_path: Path) -> None:
    """X6, typed 37: the sword half of "I sheathe my sword and sling my shield" was dropped."""
    stow = pick(("unequip:longsword", [], None), ("unequip:shield", [], None))
    played = await play(tmp_path, TYPED, 35, picks=[stow])
    worn = [(e.equipped.main_hand, e.equipped.shield) for e in played.of(EquipmentChanged)]
    assert worn[-1] == (None, None)


async def test_v1_m32_pick_up_then_hand_over_does_both(tmp_path: Path) -> None:
    """X6, full 611-614: "I pick up the Free-Given Salt ... and hand all the salt we have
    gathered to Gran Tevin" only picked it up. Now it picks up, then hands every salt over."""
    salt = pick(("take:free-given-salt", [], None), ("give:free-given-salt", ["gran-tevin"], 2))
    played = await play(tmp_path, FULL, 610, picks=[salt])
    given = [(e.keepsake_id, e.npc_id) for e in played.of(KeepsakeGiven)]
    assert given == [(f"{SALT}0", "gran-tevin"), (f"{SALT}2", "gran-tevin")]


async def test_v1_m32_counted_hand_over_gives_them_all(tmp_path: Path) -> None:
    three = pick(("give:salt-lanterns", ["bram-velde"], 3))
    played = await play(tmp_path, QUESTS, 284, picks=[three])
    assert [e.keepsake_id for e in played.of(KeepsakeGiven)] == [f"{LANTERN}{i}" for i in range(3)]
    five = pick(("give:salt-lanterns", ["bram-velde"], 5))  # M36.10a: a give's count as said
    text = "Brienne hands the five salt-lanterns to Bram Velde"
    fewer = await play(tmp_path, QUESTS, 284, text, picks=[five])
    assert len(fewer.of(KeepsakeGiven)) == 3
    assert "Brienne had only 3 of those to give." in fewer.notices()


async def test_v1_m32_charge_and_cleave_moves_then_attacks(tmp_path: Path) -> None:
    """X6, typed 429-431: "I charge the zombie and cleave it with my longsword" only moved."""
    actor, text = typed(TYPED, 428)
    cleave = pick(("attack:longsword", ["zombie-1"], None))  # out of reach: the menu approaches
    async with running(menu_down(tmp_path, cleave), replay_until(TYPED, 428)) as (table, _):
        table.in_combat = True
        seat = await join(table, "Ann", actor)
        table.schedule(lambda: combat_flow.advance(table))
        await table.settle()
        start = table.state.event_count
        seat.send(SubmitAction(text=text))
        await table.settle()
        assert_replays(table)
        events = [e.event for e in table.log if e.seq >= start]
    moved = [i for i, e in enumerate(events) if isinstance(e, CombatantMoved)]
    rolled = [i for i, e in enumerate(events) if isinstance(e, AttackRolled)]
    assert moved and rolled and moved[0] < rolled[0]
    first = events[rolled[0]]
    assert isinstance(first, AttackRolled) and (first.attack, first.target_id) == (
        "Longsword",
        "zombie-1",
    )
    assert [e.type for e in events].count("action_declared") == 1


async def test_v1_m32_travel_further_walks_every_road(tmp_path: Path) -> None:
    roads = pick(("travel", ["hollowgate-cross"], None), ("travel", [BARROW], None))
    played = await play(tmp_path, TYPED, 394, picks=[roads])
    moved = [(e.from_node, e.to_node) for e in played.of(PartyMoved)]
    assert moved == [
        ("the-briar-vein", "hollowgate-cross"),
        ("hollowgate-cross", "barrow-of-the-hollow-king"),
    ]


async def test_v1_m32_route_item_to_a_waiting_master_closes_the_step(tmp_path: Path) -> None:
    """X7, full 519-522: "Rook steps forward and gives Caul's Bait-Cache to Abbess Marwen Salt"
    did nothing and told the filler line, so the peaceful route could not be finished. Now the
    cache is handed over, the route step closes and the waiting offer shows the sure parley."""
    cache = pick(("give:caul-s-bait-cache", ["boss-the-saltlow-marshes"], None))
    played = await play(tmp_path, FULL, 519, picks=[cache])
    assert [e.npc_id for e in played.of(KeepsakeGiven)] == ["boss-the-saltlow-marshes"]
    steps = [e.log_line for e in played.of(QuestStepDone)]
    assert "Give Caul's Bait-Cache to Abbess Marwen Salt" in steps
    offer = played.state.campaign.offer if played.state.campaign is not None else None
    assert offer is not None and sure_parley(played.state, offer)
    assert QUIET_LINE not in played.told()


async def test_v1_m32_gift_to_a_yielded_master_moves_and_never_turns_him(tmp_path: Path) -> None:
    """X7, typed 853-855: the ring given to the yielded Duke never moved, and an attitude change
    while he was still hostile printed "turns hostile"."""
    ring = pick(("give:broken-signet-ring", ["boss-the-rookwood-marches"], None))
    played = await play(tmp_path, TYPED, 853, picks=[ring])
    assert [e.npc_id for e in played.of(KeepsakeGiven)] == ["boss-the-rookwood-marches"]
    assert not any(e.turned for e in played.of(AttitudeChanged))
    assert "turns hostile" not in played.told()


async def test_v1_m32_refused_move_says_why(tmp_path: Path) -> None:
    """X7, full 619: a move to a place that is not next door got the filler line, no reason.
    Now the walk goes road by road; the crossing into the next region asks first, and once
    confirmed the party reaches The Skiff-Road."""
    skiff = pick(("travel", ["the-skiff-road"], None))
    played = await play(tmp_path, FULL, 617, then=(ConfirmHostile(),), picks=[skiff])
    said = " ".join([played.told(), *played.notices()])
    assert QUIET_LINE not in said
    assert played.asked() and "Crossing into" in played.asked()[0]
    assert [e.to_node for e in played.of(PartyMoved)] == ["the-brine-veil", "the-skiff-road"]


def test_v1_m32_refused_turn_says_why() -> None:
    """X7: a storyteller turn with no events whose call the engine refused tells the refusal,
    never the stock filler line; a reason written for the model is not told as is."""
    state = replay_until(FULL, 617)
    line = refusal_line(state, ["'the-skiff-road' is not a neighbour; legal exits: x"])
    assert line == "That does not happen: The Skiff-Road is not a neighbour."
    assert refusal_line(state, ["'vorpal-sword' is not a catalogue item"]) == NOT_DONE.format(
        why=NOTHING_ALLOWS
    )
    assert refusal_line(state, []) is None


def test_v1_m32_only_a_flip_is_told_turning_hostile() -> None:
    """X7, typed 855: an attitude change while the Duke was already hostile read "turns
    hostile"; only the event that makes an NPC hostile is a turn."""
    state = replay_until(TYPED, 853)
    duke = state.world.npcs["boss-the-rookwood-marches"]
    assert duke.hostile
    warmer = social_attitude_events(duke, DeltaTier.IMPROVE_SLIGHT, "a ring")
    assert [e.turned for e in warmer if isinstance(e, AttitudeChanged)] == [False]
    assert "turns hostile" not in " ".join(template_narration(warmer, state))
    friend = state.world.npcs["mother-marrow"]
    flip = hostile_attitude_events(friend, "attacked")
    assert [e.turned for e in flip if isinstance(e, AttitudeChanged)] == [True]
