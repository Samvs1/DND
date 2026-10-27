"""M43.2 contract rule B3 (docs/next/M43_CONTRACT.md): the act aims at what the line named, or
refuses; no stand-in target. Round 8 AA1 = round 2 R26: aimed cones were fixed for the button in
round 3 (M29.7d: the cast is aimed at the chosen zone, `rules.spell_targets.area_zones`), but a
typed area spell named at a foe out of reach was cast at the caster's own zone and burned the
party. The typed path now sends the cast at the zone the named foe stands in, and the same rule
the button meets answers it. Fixture m42-r8-typed; FakeLLM picks only."""

from pathlib import Path

from aidm.models.combat_events import SpellCast
from aidm.models.events import DamageTaken
from aidm.models.impossible import ActionImpossible
from aidm.models.state import GameState
from tests.ai.chooser_fixtures import state_at
from tests.session.menu_play import menu_play
from tests.session.table_fixtures import pick

R8 = "m42-r8-typed"
ROOK = "pc-p6"


async def test_v1_m43_burning_hands_at_a_foe_out_of_reach_is_refused(tmp_path: Path) -> None:
    """round 8 AA1: r8-typed 213 "Rook casts burning hands on Bandit B" (Rook in the sunken hall,
    Bandit B in the courtyard) hit Elowen and Tamsin, the bandit untouched."""
    enc = state_at(R8, 213).encounter
    assert enc is not None and enc.combatant("bandit-2").zone_id == "courtyard"
    played = await menu_play(tmp_path, R8, 213, pick(("cast:burning-hands", ["bandit-2"], None)))
    why = "The 15-ft cone does not reach Cracked Courtyard, 25 ft away."
    assert [e.reason for e in played.of(ActionImpossible)] == [why]
    assert not played.of(SpellCast) and not played.of(DamageTaken)
    assert played.state.creatures[ROOK].resources == state_at(R8, 213).creatures[ROOK].resources
    assert played.choose_calls() == 1  # no repair round that offered the hero's own zone


async def test_v1_m43_burning_hands_on_the_rats_never_lands_on_the_party(tmp_path: Path) -> None:
    """round 8 AA1, second case: r8-typed 463 "Rook casts burning hands on the giant rats"."""
    played = await menu_play(tmp_path, R8, 463, pick(("cast:burning-hands", ["giant-rat-1"], None)))
    assert [e.reason for e in played.of(ActionImpossible)] == [
        "The 15-ft cone does not reach Cattail Bed, 25 ft away."
    ]
    assert not played.of(DamageTaken)


async def test_v1_m43_an_area_spell_at_a_foe_in_reach_holds_the_foe(tmp_path: Path) -> None:
    """The same line with the bandit moved next to Rook: the cone is cast at the zone that holds
    the named foe (never the caster's own zone in its place)."""

    def near(state: GameState) -> None:
        enc = state.encounter
        assert enc is not None
        rook = enc.combatants[ROOK]
        enc.combatants["bandit-2"] = enc.combatants["bandit-2"].model_copy(
            update={"zone_id": rook.zone_id}
        )

    played = await menu_play(
        tmp_path, R8, 213, pick(("cast:burning-hands", ["bandit-2"], None)), prep=near
    )
    (cast,) = played.of(SpellCast)
    enc = played.state.encounter
    assert enc is not None and cast.target_zone == enc.combatant(ROOK).zone_id
    assert "bandit-2" in {d.creature_id for d in played.of(DamageTaken)}
