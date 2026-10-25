"""M33.1 (docs/reviews/M33_ultrareview.md findings 1, 2, 3, 5): typed actions read as the player
meant them, on the real round-5 states: a plain-word cantrip never hijacks a weapon line, a
counted give of a stack gives the count, a courtesy at an offer is no strike, and no part of a
compound line is dropped."""

from pathlib import Path
from typing import Any

import pytest

from aidm.dm import narrator
from aidm.dm.compound_lines import clause_parts, is_lead_in
from aidm.dm.fake_llm import FakeStep
from aidm.dm.intent_router import explore_intent, fight_intent
from aidm.models.campaign_events import OfferResolved
from aidm.models.combat_events import AttackRolled
from aidm.models.commands import AttackCommand, CastCommand
from aidm.models.encounter_events import EncounterStarted
from aidm.models.events import InventoryChanged
from aidm.models.state import GameState
from aidm.rules.acts import GiveIntent, OfferStrikeIntent
from aidm.session import intent_turn, telling
from aidm.session.hand_over import ONLY
from aidm.session.offer_strike import WAITS
from aidm.session.table_core import TableCore
from tests.session.m32_play import QUESTS, TYPED, play, typed
from tests.session.playtest_saves import replay_until
from tests.session.table_fixtures import Step, pick

TAMSIN, ELOWEN, ROOK = "pc-p8", "pc-p4", "pc-p6"


def _fight_with_light() -> GameState:
    state = replay_until(TYPED, 428)  # the zombie fight; Tamsin carries a light crossbow
    pc = state.creatures[TAMSIN].pc
    assert pc is not None
    pc.cantrips = [*pc.cantrips, "light"]
    return state


@pytest.mark.parametrize(
    "text",
    ["I attack the zombie with my light crossbow", "In the dim light I strike the zombie"],
)
def test_v1_m33_light_never_hijacks_a_weapon_line(text: str) -> None:
    """Finding 1: with Light ready, a weapon line naming "light" was cast as Light."""
    found = fight_intent(_fight_with_light(), TAMSIN, text)
    assert not isinstance(found, CastCommand), found
    if "crossbow" in text:
        assert isinstance(found, AttackCommand) and found.target_id == "zombie-1"


@pytest.mark.parametrize("text", ["I cast light on my shield", "I cast light on my light crossbow"])
def test_v1_m33_light_after_a_cast_word_is_still_cast(text: str) -> None:
    found = fight_intent(_fight_with_light(), TAMSIN, text)
    assert isinstance(found, CastCommand) and found.spell_id == "light"


def test_v1_m33_counted_give_of_a_stack_names_the_units() -> None:
    """Finding 2: "give two arrows to Bram" gave one arrow and said "had only 1"."""
    state = replay_until(QUESTS, 284)  # Rook carries 20 arrows; Bram Velde stands here
    two = explore_intent(state, ROOK, "give two arrows to Bram")
    assert two == GiveIntent(ROOK, "bram-velde", "arrow", ("arrow",), 2)
    many = explore_intent(state, ROOK, "give 30 arrows to Bram")
    assert isinstance(many, GiveIntent) and len((many.thing, *many.more)) == 20
    one = explore_intent(state, ROOK, "give the arrow to Bram")
    assert one == GiveIntent(ROOK, "bram-velde", "arrow")


def _taken(events: list[Any], item: str) -> list[int]:
    return [e.qty for e in events if isinstance(e, InventoryChanged) and e.item == item]


GIVE_ONE: Step = ("give:piton", ["bram-velde"], 1)


def _give(qty: int) -> FakeStep:
    """The menu chooser's reading of a counted give of pitons to Bram (M36.10a)."""
    return pick(("give:piton", ["bram-velde"], qty))


async def test_v1_m33_counted_give_of_a_stack_gives_the_count(tmp_path: Path) -> None:
    played = await play(
        tmp_path, QUESTS, 284, "Brienne gives two pitons to Bram Velde", picks=[_give(2)]
    )
    assert _taken(played.events, "piton") == [9, 8]
    assert not [n for n in played.notices() if "had only" in n]
    fewer = await play(
        tmp_path, QUESTS, 284, "Brienne gives 12 pitons to Bram Velde", picks=[_give(12)]
    )
    assert len(_taken(fewer.events, "piton")) == 10
    assert ONLY.format(name="Brienne", n=10) in fewer.notices()
    single = await play(
        tmp_path, QUESTS, 284, "Brienne gives a piton to Bram Velde", picks=[_give(1)]
    )
    assert _taken(single.events, "piton") == [9]


@pytest.mark.parametrize(
    "text",
    [
        "I bow to the bandit",
        "Rook bows low to the bandit",
        "I warm my hands by the fire, watching the bandit",
        "I keep my bow slung and greet the bandit",
        "I won't attack the bandit",
        "I will not cast fire bolt at the bandit",
    ],
)
def test_v1_m33_courtesy_at_an_offer_is_no_strike(text: str) -> None:
    """Finding 3: a bow, a fire to warm by, a slung bow or a refusal answered the offer as FIGHT."""
    assert explore_intent(replay_until(QUESTS, 161), ROOK, text) != OfferStrikeIntent(ROOK)


@pytest.mark.parametrize(
    "text",
    [
        "I shoot the bandit",
        "I take a swing at the bandit",
        "I attack the bandit with my bow",
        "No mercy, I attack the bandit",
        "I loose an arrow at the bandit",
        "I cast fire bolt at the bandit",
    ],
)
def test_v1_m33_real_attack_at_an_offer_still_strikes(text: str) -> None:
    assert explore_intent(replay_until(QUESTS, 161), ROOK, text) == OfferStrikeIntent(ROOK)


async def test_v1_m33_bow_to_the_offer_keeps_it_waiting(tmp_path: Path) -> None:
    played = await play(tmp_path, QUESTS, 162, "I bow to the bandit")
    assert not played.of(EncounterStarted) and not played.of(OfferResolved)
    assert WAITS.format(name="Rook") not in played.notices()
    campaign = played.state.campaign
    assert campaign is not None and campaign.offer is not None
    shot = await play(tmp_path, QUESTS, 162)  # "attacks the bandit with his bow": the fight
    assert [e.attacker_id for e in shot.of(AttackRolled)].count(ROOK) == 1


def test_v1_m33_bow_in_a_fight_is_no_shot() -> None:
    state = replay_until(TYPED, 428)
    assert not isinstance(fight_intent(state, ELOWEN, "I bow to the zombie"), AttackCommand)
    shot = fight_intent(state, ELOWEN, "I put an arrow in the zombie's chest")
    assert isinstance(shot, AttackCommand) and shot.target_id == "zombie-1"


def test_v1_m33_checked_movement_is_no_lead_in() -> None:
    """Finding 5: "I climb the wall and search the room" dropped the climb as a lead-in."""
    for act in ("climb the wall", "jump the ditch", "leap the gap", "vault the fence"):
        assert not is_lead_in(act), act
    for act in ("scramble up the bank", "dash to the door", "charge the gate"):
        assert not is_lead_in(act), act
    for gesture in ("step forward", "nod to bram", "kneel by the grave", "bow to the captain"):
        assert is_lead_in(gesture), gesture
    state = replay_until(QUESTS, 284)
    parts = clause_parts(state, ROOK, "I climb the wall and search the room")
    assert parts == ["climb the wall", "search the room"]


async def test_v1_m33_compound_line_tells_every_part(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Finding 5: the climb goes to the storyteller with the turn; a gesture is told with the
    act it leads into, never ruled on by itself."""
    told: list[str] = []

    async def adjudicated(core: TableCore, entry: Any, **_: Any) -> None:
        told.append(entry.text)

    monkeypatch.setattr(intent_turn, "adjudicated", adjudicated)
    said: list[str | None] = []
    real = telling.narrate

    def narrate(*args: Any, **kwargs: Any) -> narrator.NarrationStream:
        said.append(kwargs.get("player_text"))
        return real(*args, **kwargs)

    monkeypatch.setattr(telling, "narrate", narrate)
    line = "Brienne climbs onto the cart and gives a piton to Bram Velde"
    climb = pick(GIVE_ONE, other="climb onto the cart", first=True)  # the menu chooser's
    played = await play(tmp_path, QUESTS, 284, line, picks=[climb])
    assert _taken(played.events, "piton") == [9]
    assert told == ["climb onto the cart"]
    told.clear()
    gesture = "Brienne steps forward and gives a piton to Bram Velde"
    stepping = pick(GIVE_ONE, colour="steps forward")  # M36.9: the manner only colours the give
    stepped = await play(tmp_path, QUESTS, 284, gesture, picks=[stepping])
    assert _taken(stepped.events, "piton") == [9]
    assert told == [] and "steps forward" in said  # the narrator tells it with the give


def test_v1_m33_typed_round_lines_still_route() -> None:
    """The round-5 lines the strike reading must keep (M32.1a X1, X3)."""
    actor, text = typed(QUESTS, 162)
    assert explore_intent(replay_until(QUESTS, 162), actor, text) == OfferStrikeIntent(actor)
    actor, text = typed(TYPED, 931)
    assert explore_intent(replay_until(TYPED, 931), actor, text) == OfferStrikeIntent(actor)
