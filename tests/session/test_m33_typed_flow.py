"""M33.1 (docs/reviews/M33_ultrareview.md findings 1, 2, 3, 5): typed actions read as the player
meant them, on the real round-5 states: a plain-word cantrip never hijacks a weapon line, a
counted give of a stack gives the count, a courtesy at an offer is no strike, and no part of a
compound line is dropped."""

from pathlib import Path
from typing import Any

import pytest

from aidm.dm import narrator
from aidm.dm.fake_llm import FakeStep
from aidm.models.campaign_events import OfferResolved
from aidm.models.combat_events import AttackRolled
from aidm.models.encounter_events import EncounterStarted
from aidm.models.events import InventoryChanged
from aidm.models.state import GameState
from aidm.session import intent_turn, telling
from aidm.session.hand_over import ONLY
from aidm.session.offer_strike import WAITS
from aidm.session.table_core import TableCore
from tests.session.m32_play import QUESTS, TYPED, play
from tests.session.playtest_saves import replay_until
from tests.session.table_fixtures import Step, pick

TAMSIN, ELOWEN, ROOK = "pc-p8", "pc-p4", "pc-p6"


def _fight_with_light() -> GameState:
    state = replay_until(TYPED, 428)  # the zombie fight; Tamsin carries a light crossbow
    pc = state.creatures[TAMSIN].pc
    assert pc is not None
    pc.cantrips = [*pc.cantrips, "light"]
    return state


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


async def test_v1_m33_bow_to_the_offer_keeps_it_waiting(tmp_path: Path) -> None:
    bow = pick(other="I bow to the bandit")  # the menu chooser's: no entry, a gesture (M36.10b)
    played = await play(tmp_path, QUESTS, 162, "I bow to the bandit", picks=[bow])
    assert not played.of(EncounterStarted) and not played.of(OfferResolved)
    assert WAITS.format(name="Rook") not in played.notices()
    campaign = played.state.campaign
    assert campaign is not None and campaign.offer is not None
    shoot = pick(("attack:shortbow", ["foe:bandit"], None))  # "attacks the bandit with his bow"
    shot = await play(tmp_path, QUESTS, 162, picks=[shoot])  # the fight
    assert [e.attacker_id for e in shot.of(AttackRolled)].count(ROOK) == 1


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
