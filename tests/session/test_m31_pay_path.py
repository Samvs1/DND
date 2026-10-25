"""M31.2b (docs/playtests/M31_round4.md line 76): coins typed to an NPC or a hero move through the
engine, or the line is refused with the real purse; the storyteller never tells coins that did
not move. Played on the real round 4 state (fixture m31-r4-typed) with the storyteller off."""

from pathlib import Path

from aidm.dm.precheck import precheck
from aidm.models.events import GoldChanged
from aidm.models.item_events import HandedOver
from aidm.models.protocol_server import NarrationChunkMsg
from aidm.rules.acts import HeroHandIntent, PayIntent
from tests.session.m32_play import play
from tests.session.playtest_saves import replay_until

R4 = "m31-r4-typed"
MERRE = "merre-wenslow"


async def test_v1_m31_overpay_refused_with_the_real_purse(tmp_path: Path) -> None:
    """Typed 44: "I slap 50 gold down on the table for Merre Wenslow" with 15 gold carried was
    told as coins on the table (no intent read it). It is a payment now, refused plainly."""
    state = replay_until(R4, 44)
    intent = precheck(state, "pc-p6", "I slap 50 gold down on the table for Merre Wenslow")
    assert intent == PayIntent("pc-p6", MERRE, 50)
    played = await play(tmp_path, R4, 44)
    assert "Rook has only 15 gold." in played.notices()
    assert not played.of(GoldChanged) and not played.of(HandedOver)
    assert not any(isinstance(m, NarrationChunkMsg) for m in played.msgs)


async def test_v1_m31_affordable_coins_on_the_table_move(tmp_path: Path) -> None:
    """The honest version: 10 of Rook's 15 gold set down for Merre really leave his purse."""
    before = replay_until(R4, 44).world.npcs[MERRE].paid
    played = await play(tmp_path, R4, 44, "I slap 10 gold down on the table for Merre Wenslow")
    rook = played.state.creatures["pc-p6"]
    assert rook.pc is not None and rook.pc.gold == 5
    assert played.state.world.npcs[MERRE].paid == before + 10
    assert [(e.to_id, e.gold) for e in played.of(HandedOver)] == [(MERRE, 10)]


async def test_v1_m31_toss_a_hero_gold_for_her_trouble(tmp_path: Path) -> None:
    """Typed 1304: "I toss Brienne 10 gold for her trouble" was refused as "does not carry that"
    while Tamsin carried 100 gold (owner rule: never refuse the possible). The coins move."""
    played = await play(tmp_path, R4, 1304)
    tamsin, brienne = played.state.creatures["pc-p8"], played.state.creatures["pc-p2"]
    assert tamsin.pc is not None and brienne.pc is not None
    assert (tamsin.pc.gold, brienne.pc.gold) == (90, 122)
    assert [(e.to_id, e.gold) for e in played.of(HandedOver)] == [("pc-p2", 10)]


def test_v1_m31_coins_to_a_hero_are_a_hand_over() -> None:
    """One rule for coins to anyone: pay, set down or press coin for a hero is the hero
    hand-over of that gold; a line with no coin named is no hand-over."""
    state = replay_until(R4, 44)
    for text in ("I pay Brienne 10 gold", "I slap 10 gold down for Brienne"):
        assert precheck(state, "pc-p6", text) == HeroHandIntent("pc-p6", "pc-p2", None, gold=10)
    assert precheck(state, "pc-p6", "I press 5 gold into Merre's hand") == PayIntent(
        "pc-p6", MERRE, 5
    )
    assert precheck(state, "pc-p6", "I leave 5 gold for the poor") is None
