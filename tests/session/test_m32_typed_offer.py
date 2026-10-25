"""M32.1a X3, X4, X5 and X8 (docs/playtests/M31_round5.md): typed lines while an encounter offer
waits, and feats no body could do, on the real round-5 states."""

from pathlib import Path

from aidm.dm.fake_llm import fake_tool_call
from aidm.models.campaign_events import OfferResolved
from aidm.models.campaign_state import OfferChoice
from aidm.models.combat_events import AttackRolled, SpellCast
from aidm.models.encounter_events import EncounterStarted
from aidm.models.events import CheckResolved
from aidm.models.impossible import ActionImpossible
from aidm.models.protocol_client import ConfirmHostile, SubmitAction
from aidm.models.protocol_server import ErrorMsg, PendingConfirmationMsg
from aidm.session.held import NOT_YOURS, PARLEY_ASK
from aidm.session.offer_strike import WAITS
from tests.session.m32_play import FULL, QUESTS, TYPED, play, typed
from tests.session.playtest_saves import replay_until
from tests.session.table_fixtures import assert_replays, join, menu_down, pick, running


async def test_v1_m32_attack_at_a_waiting_offer_fights_then_attacks(tmp_path: Path) -> None:
    """X3, quests 162-166: the fight started and the attack never came while the story told
    "Rook's arrow flies true". Now the offer is the fight, and the same line is Rook's attack
    on Rook's turn, rolled against armour."""
    shoot = pick(("attack:shortbow", ["foe:bandit"], None))  # the menu chooser's (M36.10b)
    played = await play(tmp_path, QUESTS, 162, picks=[shoot])
    resolved = played.of(OfferResolved)
    assert [r.choice for r in resolved] == [OfferChoice.FIGHT]
    assert played.of(EncounterStarted)
    rolled = [e for e in played.of(AttackRolled) if e.attacker_id == "pc-p6"]
    assert [(e.attack, e.target_id) for e in rolled] == [("Shortbow", "bandit-1")]
    assert WAITS.format(name="Rook") in played.notices()
    start = played.events.index(played.of(EncounterStarted)[0])
    assert played.events.index(rolled[0]) > start  # the attack comes in the fight, by turns


async def test_v1_m32_spell_at_a_waiting_offer_is_cast_in_the_fight(tmp_path: Path) -> None:
    """X3, typed 932-936: "I fling a scorching ray at the gnoll" only started the fight."""
    ray = pick(("cast:scorching-ray", ["foe:gnoll"], None))  # the menu chooser's (M36.10b)
    played = await play(tmp_path, TYPED, 931, picks=[ray])
    assert [r.choice for r in played.of(OfferResolved)] == [OfferChoice.FIGHT]
    cast = [e for e in played.of(SpellCast) if e.caster_id == "pc-p6"]
    assert [(e.spell_id, e.target_ids) for e in cast] == [("scorching-ray", ("gnoll-1",))]


async def test_v1_m32_peace_line_to_a_master_never_starts_a_fight(tmp_path: Path) -> None:
    """X4, full 903-904: the parley card went to Elowen's seat, the harness confirmed from the
    host's seat ("nothing is waiting") and the offer was then answered as a fight. A confirm
    from another seat changes nothing and names whose card it is; Elowen's own confirm is the
    parley roll, never the fight button."""
    actor, text = typed(FULL, 903)
    parley = menu_down(tmp_path, pick(("offer:parley:persuasion", [], None)))  # M36.10b
    async with running(parley, replay_until(FULL, 903)) as (table, _):
        host = await join(table, "Sam", "pc-p2")
        elowen = await join(table, "Ann", actor)
        start = table.state.event_count
        elowen.send(SubmitAction(text=text))
        await table.settle()
        assert [m.prompt for m in elowen.drain() if isinstance(m, PendingConfirmationMsg)] == [
            PARLEY_ASK
        ]
        host.drain()
        host.send(ConfirmHostile())
        await table.settle()
        refused = [m.text for m in host.drain() if isinstance(m, ErrorMsg)]
        assert refused == [NOT_YOURS.format(name="Elowen")]
        assert table.state.campaign is not None and table.state.campaign.offer is not None
        assert table.state.encounter is None or table.state.encounter.status.value != "active"
        elowen.send(ConfirmHostile())
        await table.settle()
        assert_replays(table)
        events = [e.event for e in table.log if e.seq >= start]
    assert [e.choice for e in events if isinstance(e, OfferResolved)] == [OfferChoice.PARLEY]
    checks = [e for e in events if isinstance(e, CheckResolved)]
    assert [(c.reason, c.result.skill) for c in checks] == [("parley", "persuasion")]


async def test_v1_m32_surrender_demand_of_the_dead_keeps_the_offer(tmp_path: Path) -> None:
    demand = pick(("surrender", [], None))  # the menu chooser's (M36.10b)
    played = await play(tmp_path, TYPED, 419, picks=[demand])
    assert [type(e).__name__ for e in played.events] == ["ActionDeclared"]
    assert played.notices() == ["The zombie will not yield: the dead do not surrender."]
    campaign = played.state.campaign
    assert campaign is not None and campaign.offer is not None


async def test_v1_m32_impossible_feat_rolls_no_dice(tmp_path: Path) -> None:
    """M36.10b: no menu entry does it, so the storyteller rules on it (`other`); its check says
    no one could, and the engine rolls nothing."""
    actor, feat = typed(TYPED, 639)
    why = "no one can lift a whole thicket"
    check = {"actor": actor, "ability_or_skill": "athletics", "dc_tier": "nearly_impossible"}
    ruled = fake_tool_call("request_check", {**check, "reason": feat[:200], "impossible": why})
    played = await play(tmp_path, TYPED, 639, picks=[pick(other=feat)], script=[ruled])
    assert len(played.of(ActionImpossible)) == 1
    assert not played.of(CheckResolved)
    assert "cannot be done" in played.told()
