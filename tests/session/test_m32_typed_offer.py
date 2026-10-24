"""M32.1a X3, X4, X5 and X8 (docs/playtests/M31_round5.md): typed lines while an encounter offer
waits, and feats no body could do, on the real round-5 states."""

from pathlib import Path

from aidm.dm.fight_cast_intent import RefusedIntent
from aidm.dm.impossible_intent import ImpossibleIntent
from aidm.dm.intent_router import explore_intent
from aidm.dm.offer_intent import OfferStrikeIntent
from aidm.dm.parley_intent import ParleyIntent
from aidm.models.abilities import Skill
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
from tests.session.table_fixtures import assert_replays, disabled_llm, join, running


def _routed(run: str, seq: int) -> object:
    actor, text = typed(run, seq)
    return explore_intent(replay_until(run, seq), actor, text)


def test_v1_m32_attack_at_a_waiting_offer_is_a_strike() -> None:
    """X3: quests 162-166, typed 348 and 932: an attack or a harmful spell at the offer's foes."""
    assert _routed(QUESTS, 161) == OfferStrikeIntent("pc-p6")  # shouts and lets fly an arrow
    assert _routed(QUESTS, 162) == OfferStrikeIntent("pc-p6")  # attacks the bandit with his bow
    assert _routed(TYPED, 347) == OfferStrikeIntent("pc-p6")  # I cast Burning Hands at the fungus
    assert _routed(TYPED, 931) == OfferStrikeIntent("pc-p6")  # I fling a scorching ray at the gnoll


async def test_v1_m32_attack_at_a_waiting_offer_fights_then_attacks(tmp_path: Path) -> None:
    """X3, quests 162-166: the fight started and the attack never came while the story told
    "Rook's arrow flies true". Now the offer is the fight, and the same line is Rook's attack
    on Rook's turn, rolled against armour."""
    played = await play(tmp_path, QUESTS, 162)
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
    played = await play(tmp_path, TYPED, 931)
    assert [r.choice for r in played.of(OfferResolved)] == [OfferChoice.FIGHT]
    cast = [e for e in played.of(SpellCast) if e.caster_id == "pc-p6"]
    assert [(e.spell_id, e.target_ids) for e in cast] == [("scorching-ray", ("gnoll-1",))]


async def test_v1_m32_peace_line_to_a_master_never_starts_a_fight(tmp_path: Path) -> None:
    """X4, full 903-904: the parley card went to Elowen's seat, the harness confirmed from the
    host's seat ("nothing is waiting") and the offer was then answered as a fight. A confirm
    from another seat changes nothing and names whose card it is; Elowen's own confirm is the
    parley roll, never the fight button."""
    actor, text = typed(FULL, 903)
    async with running(disabled_llm(tmp_path), replay_until(FULL, 903)) as (table, _):
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


def test_v1_m32_surrender_demand_of_the_dead_at_the_offer_rolls_nothing() -> None:
    """X5, typed 420-422: "Drop your weapons and yield!" to a risen zombie rolled Intimidation
    and was told obeyed; now it is the plain line of a fight, no roll."""
    line = "The zombie will not yield: the dead do not surrender."
    assert _routed(TYPED, 419) == RefusedIntent("pc-p2", line)
    state = replay_until(QUESTS, 161)  # a bandit and a wolf can yield: a parley, asked first
    assert explore_intent(state, "pc-p6", "Drop your weapons and yield!") == ParleyIntent(
        "pc-p6", Skill.INTIMIDATION
    )


async def test_v1_m32_surrender_demand_of_the_dead_keeps_the_offer(tmp_path: Path) -> None:
    played = await play(tmp_path, TYPED, 419)
    assert [type(e).__name__ for e in played.events] == ["ActionDeclared"]
    assert played.notices() == ["The zombie will not yield: the dead do not surrender."]
    campaign = played.state.campaign
    assert campaign is not None and campaign.offer is not None


def test_v1_m32_impossible_feat_in_other_words() -> None:
    """X8, typed 640-642: lifting the whole thicket and hurling it rolled Strength."""
    found = _routed(TYPED, 639)
    assert isinstance(found, ImpossibleIntent) and "thicket" in found.reason
    state = replay_until(TYPED, 639)
    for possible in (
        "I climb the sheer wall",
        "I throw a rock into the river",
        "I push the cart off the bridge",
        "I lift the bridge keeper's lantern",
    ):
        assert not isinstance(explore_intent(state, "pc-p2", possible), ImpossibleIntent), possible


async def test_v1_m32_impossible_feat_rolls_no_dice(tmp_path: Path) -> None:
    played = await play(tmp_path, TYPED, 639)
    assert len(played.of(ActionImpossible)) == 1
    assert not played.of(CheckResolved)
    assert "cannot be done" in played.told()
