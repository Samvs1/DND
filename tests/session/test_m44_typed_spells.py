"""M44.2 round-9 typed spells (docs/playtests/M43_round9.md BB1, BB4; contract rules B2, B3): an
area spell aims at the zone holding the creature the line names, or the cast's own reach rule
refuses it; a spell or feature a line names is cast by the engine or refused with the reason,
never the storyteller's. Real round-9 lines on fixtures m43-r9-typed and m43-r9-quests (the seq
cited is the line's `action_declared`; its `line_read` is the seq before). FakeLLM picks only."""

from pathlib import Path

from aidm.models.combat_events import SpellCast
from aidm.models.events import DamageTaken, HpChanged
from aidm.models.impossible import ActionImpossible
from tests.ai.chooser_fixtures import state_at
from tests.session.menu_play import MenuPlayed, menu_play
from tests.session.table_fixtures import pick

TYPED, QUESTS = "m43-r9-typed", "m43-r9-quests"
ROOK, ELOWEN, TAMSIN = "pc-p6", "pc-p4", "pc-p8"


def _reasons(played: MenuPlayed) -> list[str]:
    return [e.reason for e in played.of(ActionImpossible)]


def _told(played: MenuPlayed) -> list[object]:
    """The storyteller's rulings on the line (a creative action), the chooser's pick aside."""
    return [r for r in played.fake.requests if r.tools and r.tool_choice != "choose_actions"]


async def _cone_at(tmp_path: Path, seq: int, entry: str, zone: str) -> MenuPlayed:
    return await menu_play(tmp_path, TYPED, seq, pick((entry, [zone], None)))


async def test_v1_m44_burning_hands_at_the_wolf_never_lands_on_the_party(tmp_path: Path) -> None:
    """r9-typed 160/161 "Rook casts Burning Hands at the wolf" read `cast:burning-hands>scrub`
    (the party's zone; the wolf in `boulders`) and burned Brienne, Elowen and Tamsin (165-176)."""
    before = state_at(TYPED, 161)
    enc = before.encounter
    assert enc is not None and enc.combatant("wolf-1").zone_id == "boulders"
    played = await _cone_at(tmp_path, 161, "cast:burning-hands", "scrub")
    assert _reasons(played) == ["The 15-ft cone does not reach Tumbled Stones, 25 ft away."]
    assert not played.of(SpellCast) and not played.of(DamageTaken)
    assert played.state.creatures[ROOK].resources == before.creatures[ROOK].resources


async def test_v1_m44_burning_hands_at_bandit_a_is_out_of_reach(tmp_path: Path) -> None:
    """r9-typed 434/435 "Rook casts Burning Hands at Bandit A" read `>near_bank` (Bandit A in
    the alley)."""
    played = await _cone_at(tmp_path, 435, "cast:burning-hands", "near_bank")
    assert _reasons(played) == ["The 15-ft cone does not reach Narrow Alley, 25 ft away."]
    assert not played.of(SpellCast) and not played.of(DamageTaken)


async def test_v1_m44_thunderwave_at_the_acolyte_is_out_of_reach(tmp_path: Path) -> None:
    """r9-typed 678/679 "Rook casts Thunderwave at the acolyte" read `>near_bank` (the acolyte
    in the square, 50 ft) and hit Brienne."""
    played = await _cone_at(tmp_path, 679, "cast:thunderwave", "near_bank")
    assert _reasons(played) == ["The 15-ft cube cannot reach Market Green from here."]
    assert not played.of(SpellCast) and not played.of(DamageTaken)


async def test_v1_m44_burning_hands_at_the_croc_in_the_party_zone_is_cast(tmp_path: Path) -> None:
    """r9-typed 1104/1105 "Rook casts Burning Hands at the crocodile": the croc and the heroes
    share `stilt_hut`, the zone picked holds the creature named, so the cast is unchanged (allies
    in the area are the spell's own, SRD; BB7 accepted)."""
    played = await _cone_at(tmp_path, 1105, "cast:burning-hands", "stilt_hut")
    (cast,) = played.of(SpellCast)
    assert cast.target_zone == "stilt_hut" and not _reasons(played)
    assert "crocodile-1" in {d.creature_id for d in played.of(DamageTaken)}


async def test_v1_m44_healing_word_out_of_a_fight_wakes_tamsin(tmp_path: Path) -> None:
    """r9-quests 284/285 "Elowen kneels by Tamsin and casts healing word on her so she can wake
    up" (Tamsin at 0 HP, out of a fight) was typed from Brienne's seat, who has no Healing Word
    (BB5, accepted as a player's slip). From Elowen's seat the same line is the engine's cast
    (manual "Healing outside a fight"): the slot is spent and Tamsin heals."""
    before = state_at(QUESTS, 285)
    assert before.creatures[TAMSIN].hp == 0
    played = await menu_play(
        tmp_path, QUESTS, 285, pick(("cast:healing-word", [TAMSIN], None)), actor=ELOWEN
    )
    (cast,) = played.of(SpellCast)
    assert cast.spell_id == "healing-word" and cast.target_ids == (TAMSIN,)
    assert played.state.creatures[TAMSIN].hp > 0
    slot = played.state.creatures[ELOWEN].resources["spell-slot-1"]
    assert slot.current == before.creatures[ELOWEN].resources["spell-slot-1"].current - 1
    assert not _told(played)


async def test_v1_m44_preserve_life_is_refused_never_told_as_healing(tmp_path: Path) -> None:
    """r9-typed 728/729 "Tamsin uses Channel Divinity Preserve Life to heal Rook and Elowen" (in
    a fight) read `other` and was told as healing: no HP moved and the use was never spent. The
    feature is on the sheet but the table cannot use it yet (manual asterisk), so it is refused
    with that reason."""
    line = "Tamsin uses Channel Divinity Preserve Life to heal Rook and Elowen"
    before = state_at(TYPED, 729)
    for choice in (pick(other=line), pick(("feature:preserve-life", [ROOK, ELOWEN], None))):
        played = await menu_play(tmp_path, TYPED, 729, choice)
        assert _reasons(played) == ["Preserve Life: the table cannot use it yet."]
        assert not played.of(HpChanged) and not _told(played)
        assert played.state.creatures[TAMSIN].resources == before.creatures[TAMSIN].resources


async def test_v1_m44_bless_with_no_slot_out_of_a_fight_is_refused(tmp_path: Path) -> None:
    """r9-typed 231/232 "Tamsin casts Bless on the party" with no 1st-level slot read `other`,
    and the storyteller invented a failed prayer. Refused with the no-slot reason, as the fight
    casts at 644 and 741 are."""
    played = await menu_play(tmp_path, TYPED, 232, pick(other="Tamsin casts Bless on the party"))
    assert _reasons(played) == ["Bless: Tamsin has no 1st-level slot left."]
    assert not played.of(SpellCast) and not _told(played)
