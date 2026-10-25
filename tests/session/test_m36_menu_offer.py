"""Typed lines at a waiting encounter offer read by the menu chooser (M36.6, SPEC 6.2; round 6
Y9, Y10): the offer card's answers, a held parley, and a strike chosen at the offer that starts
the fight and is aimed at the spawned foes on the hero's turn (`resume_strike`), at a real table
with the chooser scripted (FakeLLM by_tool) and the log replayed equal.
"""

from pathlib import Path

from aidm.models.campaign_events import OfferResolved
from aidm.models.combat_events import SpellCast
from aidm.models.encounter_events import EncounterStarted
from aidm.models.protocol_server import PendingConfirmationMsg
from aidm.models.state import GameState
from aidm.models.world_events import ActionDeclared
from aidm.session.held import PARLEY_ASK
from aidm.session.offer_strike import WAITS
from tests.session.menu_play import TYPED, menu_play, pick


def _sturdy(state: GameState) -> None:
    """Rook survives until his turn (the replayed dice may down him first; the lapse of a held
    line is M33.1's own test)."""
    rook = state.creatures["pc-p6"]
    rook.max_hp = rook.hp = 200


async def test_menu_offer_fight_answer_starts_the_fight(tmp_path: Path) -> None:
    played = await menu_play(
        tmp_path, TYPED, 750, pick(("offer:fight", [], None), ("look", [], None)), text="Fight!"
    )
    assert played.of(OfferResolved) and played.of(EncounterStarted)
    assert played.choose_calls() == 1


async def test_menu_offer_parley_and_surrender_demand_ask_first(tmp_path: Path) -> None:
    talk = await menu_play(tmp_path, TYPED, 750, pick(("offer:parley:persuasion", [], None)))
    assert [m.prompt for m in talk.msgs if isinstance(m, PendingConfirmationMsg)] == [PARLEY_ASK]
    assert not talk.of(OfferResolved)
    demand = await menu_play(tmp_path, TYPED, 750, pick(("surrender", [], None)), text="Yield!")
    assert [m.prompt for m in demand.msgs if isinstance(m, PendingConfirmationMsg)] == [PARLEY_ASK]


async def test_v1_y9_menu_sleep_at_the_waiting_kobolds_is_cast_on_the_turn(tmp_path: Path) -> None:
    """typed 378 "I cast Sleep on the kobolds behind the spur": the fight starts, no slot spent
    at the scene, and on Rook's turn Sleep is cast at the kobolds' zone (the chosen step)."""
    played = await menu_play(
        tmp_path, TYPED, 378, pick(("cast:sleep", ["foe:kobold"], None)), prep=_sturdy
    )
    assert played.of(EncounterStarted)
    assert any(WAITS.split(".")[0] in n for n in played.notices())
    casts = [c for c in played.of(SpellCast) if c.caster_id == "pc-p6"]
    assert [c.spell_id for c in casts] == ["sleep"]
    started = next(i for i, e in enumerate(played.events) if isinstance(e, EncounterStarted))
    cast_at = next(i for i, e in enumerate(played.events) if isinstance(e, SpellCast))
    assert started < cast_at
    assert played.choose_calls() == 1  # the held step is played with no second model call
    assert len(played.of(ActionDeclared)) == 2  # at the offer, then as the step plays


async def test_menu_offer_strike_fire_bolt_resumes_on_a_spawned_kobold(tmp_path: Path) -> None:
    played = await menu_play(
        tmp_path,
        TYPED,
        378,
        pick(("cast:fire-bolt", ["foe:kobold"], None)),
        text="I fire bolt the kobolds",
        prep=_sturdy,
    )
    casts = [c for c in played.of(SpellCast) if c.caster_id == "pc-p6"]
    assert len(casts) == 1 and casts[0].spell_id == "fire-bolt"
    assert casts[0].target_ids and casts[0].target_ids[0].startswith("kobold-")


async def test_menu_offer_strike_lapses_when_the_turn_passes(tmp_path: Path) -> None:
    """M33.1 kept: Rook is downed before his turn, so the held step is said to lapse, unplayed."""

    def frail(state: GameState) -> None:
        state.creatures["pc-p6"].hp = 1

    played = await menu_play(
        tmp_path, TYPED, 378, pick(("cast:sleep", ["foe:kobold"], None)), prep=frail
    )
    assert any("will not be played" in n for n in played.notices())
    assert not [c for c in played.of(SpellCast) if c.caster_id == "pc-p6"]
