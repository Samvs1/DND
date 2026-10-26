"""M31.2b (docs/playtests/M31_round4.md line 76): coins typed to an NPC or a hero move through the
engine, or the line is refused with the real purse; the storyteller never tells coins that did
not move. Played on the real round 4 state (fixture m31-r4-typed) with the storyteller off."""

from pathlib import Path

from aidm.models.events import GoldChanged
from aidm.models.impossible import ActionImpossible
from aidm.models.item_events import HandedOver
from tests.session.m32_play import play
from tests.session.playtest_saves import replay_until
from tests.session.table_fixtures import pick

R4 = "m31-r4-typed"
MERRE = "merre-wenslow"


async def test_v1_m31_overpay_refused_with_the_real_purse(tmp_path: Path) -> None:
    """Typed 44: "I slap 50 gold down on the table for Merre Wenslow" with 15 gold carried was
    told as coins on the table (no intent read it). It is a payment now, refused plainly.
    M41.1 (round 7 Z4): the refusal is told in the story as an impossible attempt with the
    rules' reason (the storyteller is down here: the template line), nothing moves."""
    played = await play(tmp_path, R4, 44, picks=[pick(("pay", [MERRE], 50))])
    assert [e.reason for e in played.of(ActionImpossible)] == ["Rook has only 15 gold."]
    assert not played.of(GoldChanged) and not played.of(HandedOver)
    assert "Rook has only 15 gold" in played.told()


async def test_v1_m31_affordable_coins_on_the_table_move(tmp_path: Path) -> None:
    """The honest version: 10 of Rook's 15 gold set down for Merre really leave his purse."""
    before = replay_until(R4, 44).world.npcs[MERRE].paid
    text = "I slap 10 gold down on the table for Merre Wenslow"
    played = await play(tmp_path, R4, 44, text, picks=[pick(("pay", [MERRE], 10))])
    rook = played.state.creatures["pc-p6"]
    assert rook.pc is not None and rook.pc.gold == 5
    assert played.state.world.npcs[MERRE].paid == before + 10
    assert [(e.to_id, e.gold) for e in played.of(HandedOver)] == [(MERRE, 10)]


async def test_v1_m31_toss_a_hero_gold_for_her_trouble(tmp_path: Path) -> None:
    """Typed 1304: "I toss Brienne 10 gold for her trouble" was refused as "does not carry that"
    while Tamsin carried 100 gold (owner rule: never refuse the possible). The coins move."""
    played = await play(tmp_path, R4, 1304, picks=[pick(("pay", ["pc-p2"], 10))])
    tamsin, brienne = played.state.creatures["pc-p8"], played.state.creatures["pc-p2"]
    assert tamsin.pc is not None and brienne.pc is not None
    assert (tamsin.pc.gold, brienne.pc.gold) == (90, 122)
    assert [(e.to_id, e.gold) for e in played.of(HandedOver)] == [("pc-p2", 10)]
