"""M43.2 contract rules B1 and B2 at the table (docs/next/M43_CONTRACT.md): a typed line that names
a game thing (a known spell, a weapon, an item, a gold amount, a place) never goes to the
storyteller as a creative action; it is a menu entry, or a refusal with the reason logged as an
`action_impossible`. Real round-8 lines on fixture m42-r8-typed (the r8-typed save, seq < 620);
FakeLLM picks only, never the network."""

from pathlib import Path

from aidm.models.combat_events import SpellCast
from aidm.models.events import CheckResolved, DiceRolled
from aidm.models.impossible import ActionImpossible
from scripts.contractlib.line_rules import LineOutcomes
from tests.ai.chooser_fixtures import state_at
from tests.session.menu_play import MenuPlayed, menu_play
from tests.session.table_fixtures import pick

R8 = "m42-r8-typed"
ROOK, ELOWEN = "pc-p6", "pc-p4"
NO_SLOT = "Magic Missile: Rook has no 1st-level slot left."


def _reasons(played: MenuPlayed) -> list[str]:
    return [e.reason for e in played.of(ActionImpossible)]


def _no_creative(played: MenuPlayed) -> None:
    told = [r for r in played.fake.requests if r.tools and r.tool_choice != "choose_actions"]
    assert not told  # the storyteller made no ruling on the line
    assert not [d for d in played.of(DiceRolled) if d.label == "Creative action"]


def _b1_findings(run: str, seq: int, played: MenuPlayed) -> list[str]:
    """The contract's own B1 check over the played events."""
    check, state = LineOutcomes(), state_at(run, seq)
    found = [f for n, e in enumerate(played.events) for f in check.see(seq + n, state, e)]
    return [f.reason for f in [*found, *check.end(state)]]


async def test_v1_m43_a_spell_with_no_slot_is_refused_never_told_as_a_kill(tmp_path: Path) -> None:
    """round 8 AA3: r8-typed 261 "Rook casts magic missile at Bandit B" with no slot left went to
    the storyteller, who told the bandit killed. The model picks the not-offered spell."""
    played = await menu_play(tmp_path, R8, 261, pick(("cast:magic-missile", ["bandit-2"], None)))
    assert _reasons(played) == [NO_SLOT]
    assert not played.of(SpellCast)
    _no_creative(played)
    assert not _b1_findings(R8, 261, played)


async def test_v1_m43_the_no_slot_spell_as_other_is_refused_too(tmp_path: Path) -> None:
    """round 8 AA3, the model's other reading of the same line."""
    line = "Rook casts magic missile at Bandit B"
    played = await menu_play(tmp_path, R8, 261, pick(other=line))
    assert _reasons(played) == [NO_SLOT]
    _no_creative(played)


async def test_v1_m43_a_named_spell_read_as_other_is_cast_never_a_creative_action(
    tmp_path: Path,
) -> None:
    """round 8 AA4: r8-typed 549 "Rook casts thunderwave at giant rat A in the Cattail Bed" ran
    as a free "Creative action" (CON DC 15, Rook's DC is 12, no slot spent). Read as `other` it
    is the Thunderwave entry aimed at what the line names, answered by the rules."""
    line = "Rook casts thunderwave at giant rat A in the Cattail Bed"
    played = await menu_play(tmp_path, R8, 549, pick(other=line))
    _no_creative(played)
    assert _reasons(played) == ["The 15-ft cube does not reach Cattail Bed, 25 ft away."]
    assert not played.of(SpellCast) and not played.of(CheckResolved)
    assert played.state.creatures[ROOK].resources == state_at(R8, 549).creatures[ROOK].resources


async def test_v1_m43_more_gold_than_the_hero_has_is_refused_with_the_reason(
    tmp_path: Path,
) -> None:
    """round 8 AA6: r8-typed 52 "I pay the peddler 100 gold for a healing potion" (Elowen 20 gp)
    was told "the coin stays in her hand" with no reason."""
    gold = state_at(R8, 52).creatures[ELOWEN].pc
    assert gold is not None and gold.gold < 100
    played = await menu_play(tmp_path, R8, 52, pick(other="pay the peddler 100 gold"))
    assert _reasons(played) == [f"100 gold: Elowen has only {gold.gold} gold."]
    _no_creative(played)
    assert not _b1_findings(R8, 52, played)


async def test_a_stunt_that_names_no_game_thing_stays_the_storytellers(tmp_path: Path) -> None:
    """B1's fourth outcome: a line that names no game thing is the storyteller's."""
    played = await menu_play(
        tmp_path, R8, 55, pick(other="hum a tune"), text="Elowen hums a tune while she waits"
    )
    assert not played.of(ActionImpossible)
    assert [r for r in played.fake.requests if r.tool_choice != "choose_actions"]
