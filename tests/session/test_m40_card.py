"""M40.1 round 7 Z1 (docs/playtests/M39_round7.md): a typed answer to the confirm card waiting for
its player answers the card. r7b-typed 382 "...let us talk" held the parley card; 383 "Yes, go
ahead, I mean it" was a new action the chooser read with no trace of the card, and it picked the
offer's Fight (384). At 603 "Yes, I confirm, let the parley happen" named the parley itself, so
the chooser picked the parley entry again (a fresh card) and the button answered it (604).
Fixture m40-r7-typed; FakeLLM picks only, never the network."""

import json
from pathlib import Path

from aidm.models.campaign_events import OfferResolved
from aidm.models.campaign_state import OfferChoice
from aidm.models.events import AnyEvent
from aidm.models.protocol_client import ConfirmHostile, SubmitAction
from aidm.models.protocol_server import PendingConfirmationMsg
from aidm.models.world_events import ActionDeclared
from aidm.rules.menu_card import CARD_NO, CARD_YES
from aidm.session.held import NOTHING_WAITS, PARLEY_STAY
from tests.ai.chooser_fixtures import chooser_client, state_at
from tests.session.m32_play import typed
from tests.session.menu_play import menu_play
from tests.session.table_fixtures import join, pick, running

R7 = "m40-r7-typed"
TALK, YES = 382, 383  # Brienne's parley line, then her typed yes
ORLOK, CONFIRM = 602, 603
PARLEY = pick(("offer:parley:persuasion", [], None))
CARD_YES_PICK = pick((CARD_YES, [], None))


def _said(seq: int) -> SubmitAction:
    return SubmitAction(text=typed(R7, seq)[1])


def _after_line(events: list[AnyEvent]) -> list[AnyEvent]:
    """The events after the last declared line (the act the line played)."""
    last = max(i for i, e in enumerate(events) if isinstance(e, ActionDeclared))
    return events[last + 1 :]


def _resolved(events: list[AnyEvent]) -> list[tuple[OfferChoice, bool | None]]:
    return [(e.choice, e.success) for e in events if isinstance(e, OfferResolved)]


async def test_v1_m40_typed_yes_at_the_parley_card_rolls_the_parley(tmp_path: Path) -> None:
    played = await menu_play(tmp_path, R7, TALK, PARLEY, CARD_YES_PICK, then=(_said(YES),))
    assert any(isinstance(m, PendingConfirmationMsg) for m in played.msgs)  # 382 held the card
    resolved = _resolved(played.events)
    assert len(resolved) == 1 and resolved[0][0] is OfferChoice.PARLEY
    assert resolved[0][1] is not None  # one roll answered it
    assert played.choose_calls() == 2


async def test_v1_m40_typed_yes_plays_exactly_what_the_button_plays(tmp_path: Path) -> None:
    typed_yes = await menu_play(tmp_path / "a", R7, TALK, PARLEY, CARD_YES_PICK, then=(_said(YES),))
    button = await menu_play(tmp_path / "b", R7, TALK, PARLEY, then=(ConfirmHostile(),))

    def dumped(events: list[AnyEvent]) -> list[str]:
        """Each event as data; ids made from the log position (`enc-<seq>`) differ by the one
        declared line, so they are left out."""
        out: list[str] = []
        for event in events:
            data = event.model_dump(mode="json")
            if isinstance(data.get("encounter"), dict):
                data["encounter"].pop("id", None)
            out.append(json.dumps(data, sort_keys=True))
        return out

    assert dumped(_after_line(typed_yes.events)) == dumped(_after_line(button.events))
    assert _resolved(typed_yes.events)


async def test_v1_m40_typed_no_keeps_the_offer_waiting(tmp_path: Path) -> None:
    no = pick((CARD_NO, [], None))
    played = await menu_play(
        tmp_path, R7, TALK, PARLEY, no, then=(SubmitAction(text="No, wait"), ConfirmHostile())
    )
    assert not _resolved(played.events)
    assert played.state.campaign is not None and played.state.campaign.offer is not None
    assert PARLEY_STAY in played.notices()
    assert NOTHING_WAITS in played.notices()  # the card was answered: nothing waits now


async def test_v1_m40_another_pick_counts_as_no(tmp_path: Path) -> None:
    look = pick(("look", [], None))
    played = await menu_play(tmp_path, R7, TALK, PARLEY, look, then=(_said(YES), ConfirmHostile()))
    assert not _resolved(played.events)  # neither the fight nor the parley
    assert NOTHING_WAITS in played.notices()  # the new action answered the card No


async def test_v1_m40_typed_yes_at_orloks_card(tmp_path: Path) -> None:
    played = await menu_play(tmp_path, R7, ORLOK, PARLEY, CARD_YES_PICK, then=(_said(CONFIRM),))
    assert _resolved(played.events) == [(OfferChoice.PARLEY, True)]  # sure to hold: no roll


async def test_v1_m40_a_card_for_another_seat_is_not_in_that_menu(tmp_path: Path) -> None:
    state = state_at(R7, TALK).model_copy(deep=True)
    other = pick(("look", [], None))
    llm, fake = chooser_client(tmp_path, {"choose_actions": [PARLEY, other, CARD_YES_PICK]})
    async with running(llm, state) as (table, _):
        brienne = await join(table, "Ann", "pc-p2")
        elowen = await join(table, "Bo", "pc-p4")
        brienne.send(_said(TALK))
        await table.settle()
        elowen.send(_said(YES))
        await table.settle()
        assert table.pending is not None and table.pending.player_id == brienne.player_id
        brienne.send(_said(YES))
        await table.settle()
        assert table.pending is None
    asked = [json.dumps(r.tools) for r in fake.requests if r.tool_choice == "choose_actions"]
    assert len(asked) == 3
    assert CARD_YES not in asked[0] and CARD_YES not in asked[1]  # Elowen's menu: no card
    assert CARD_YES in asked[2]  # Brienne's own menu carries it
    assert _resolved([e.event for e in table.log])[-1][0] is OfferChoice.PARLEY
