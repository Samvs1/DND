"""The menu gaps closed in M36.8c, played at a real table in menu mode (`interpreter="menu"`, the
chooser scripted with FakeLLM by_tool, the log replayed equal): a search while foes wait, an
attack on a person through the point-of-no-return card, a downed ally's own potion, the trade
button while an offer waits, and a strike at the master's shown twin.
"""

from pathlib import Path

from aidm.models.campaign_events import OfferResolved
from aidm.models.combat_events import AttackRolled
from aidm.models.encounter_events import EncounterStarted
from aidm.models.events import CheckResolved, HpChanged, InventoryChanged
from aidm.models.protocol_client import CancelHostile, ConfirmHostile
from aidm.models.protocol_server import PendingConfirmationMsg, VoteOpen
from aidm.models.state import GameState
from aidm.models.world_events import NarrationRecorded
from aidm.session.held import STAY_HAND
from tests.session.menu_play import menu_play, pick

TANN = "old-broker-tann"


async def test_v1_m36_menu_search_runs_while_foes_wait(tmp_path: Path) -> None:
    """r5-quests 658: the engine runs the search check although the duergar wait."""
    played = await menu_play(
        tmp_path, "m32-r5-quests", 658, pick(("search:investigation", [], None))
    )
    assert [c.creature_id for c in played.of(CheckResolved)] == ["pc-p6"]
    assert not played.of(OfferResolved) and not played.of(EncounterStarted)


async def test_v1_m36_menu_attack_on_a_person_asks_then_fights(tmp_path: Path) -> None:
    """r1 p6 104 "Brienne draws her longsword and attacks Old Broker Tann without warning": the
    point-of-no-return card first; confirmed, the fight starts and the opening blow is rolled."""
    played = await menu_play(
        tmp_path,
        "p6",
        104,
        pick(("attack:longsword", [TANN], None)),
        then=(ConfirmHostile(),),
    )
    assert [m for m in played.msgs if isinstance(m, PendingConfirmationMsg)]
    assert played.of(EncounterStarted)
    assert [a.attacker_id for a in played.of(AttackRolled)][:1] == ["pc-p2"]


async def test_menu_attack_on_a_person_can_be_called_off(tmp_path: Path) -> None:
    played = await menu_play(
        tmp_path,
        "p6",
        104,
        pick(("attack:longsword", [TANN], None)),
        then=(CancelHostile(),),
    )
    assert not played.of(EncounterStarted)
    assert played.state.world.npcs[TANN].hostile is False
    assert any(STAY_HAND in e.text for e in played.of(NarrationRecorded))


async def test_v1_m36_menu_downed_ally_drinks_his_own_potion(tmp_path: Path) -> None:
    """r1 p2 662 "Elowen kneels by Rook and pours his Potion of Healing between his lips"."""

    def down(state: GameState) -> None:
        state.creatures["pc-p6"].hp = 0

    played = await menu_play(
        tmp_path, "p2", 662, pick(("feed:potion-of-healing", ["pc-p6"], None)), prep=down
    )
    used = [
        (e.creature_id, e.delta)
        for e in played.of(InventoryChanged)
        if e.item == "potion-of-healing"
    ]
    assert used == [("pc-p6", -1)]
    assert [h.creature_id for h in played.of(HpChanged)] == ["pc-p6"]
    assert played.state.creatures["pc-p6"].hp > 0


async def test_v1_m36_menu_trade_button_while_an_offer_waits(tmp_path: Path) -> None:
    """r5-typed 332 "trade with Bramble Pike" (the shop panel's own button sentence)."""
    played = await menu_play(tmp_path, "m32-r5-typed", 332, pick(("shop", ["bramble-pike"], None)))
    assert [m for m in played.msgs if isinstance(m, VoteOpen)]
    assert not played.of(EncounterStarted)


async def test_menu_strike_at_the_masters_twin_starts_the_offer_fight(tmp_path: Path) -> None:
    """r1 p3 415: Ranna shows once; a strike at her answers the offer with the boss record."""
    played = await menu_play(
        tmp_path,
        "p3",
        415,
        pick(("attack:shortbow", ["ranna-the-brine-widow"], None)),
        text="I shoot Ranna",
    )
    assert played.of(OfferResolved) and played.of(EncounterStarted)
    assert not [m for m in played.msgs if isinstance(m, PendingConfirmationMsg)]
