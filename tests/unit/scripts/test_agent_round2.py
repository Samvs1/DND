"""M29.7e: the round-2 harness problems H7-H14 (scripts/agent only), offline."""

import asyncio
import time
from pathlib import Path
from typing import Any

import pytest

from scripts.agent import ops, trade
from scripts.agent.commands import UsageError, build_command
from scripts.agent.damage import avg_dice, pick_option
from scripts.agent.hero_view import hero_lines, learned, roll_why, zone_lines
from scripts.agent.link import Link
from scripts.agent.session import Session
from scripts.agent.spells import spell_lines
from scripts.agent.text import digest, look_text, option_lines
from scripts.agent_play import build_parser
from scripts.sim.server import free_port

Msg = dict[str, Any]
ECO: Msg = {"action": True, "bonus_action": True, "attacks_left": 0, "movement_left": 30}
PLAY_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "agent_play.py"


class _QuietLink(Link):
    """A link whose sends do nothing: the test feeds the log by hand."""

    async def send(self, msg: Msg) -> list[Msg]:
        return []


def _link(live: bool = False) -> _QuietLink:
    return _QuietLink(Session(run="r", port=1, live=live), "t")


def _tok(cid: str, side: str) -> Msg:
    base = {"creature_id": cid, "name": cid, "side": side, "hp": 9, "max_hp": 9}
    return {**base, "dead": False, "zone_id": "z1"}


def _combat(active: str | None = "pc-1", zones: list[Msg] | None = None) -> Msg:
    return {
        "round": 1,
        "active_id": active,
        "turn_of": active,
        "zones": zones or [{"id": "z1", "name": "Gate"}],
        "tokens": [_tok("pc-1", "party"), _tok("wolf-1", "hostile")],
        "economy": ECO,
    }


def _state(**kw: Any) -> Msg:
    base: Msg = {"phase": "exploration", "campaign_id": "c-1", "party": []}
    return {**base, **kw}


def test_m29_h7_trade_waits_for_the_late_shop_stock() -> None:
    link = _link()

    async def late() -> None:
        await asyncio.sleep(0.5)
        link.conn.log.append({"type": "shop_stock", "npc_id": "n1", "stock": []})

    async def run() -> Msg | None:
        task = asyncio.create_task(late())
        got = await trade.open_stock(link.session, link, {"name": "Brewer"})
        await task
        return got

    got = asyncio.run(run())
    assert got is not None and got["npc_id"] == "n1"


def test_m29_h8_best_option_weighs_expected_damage() -> None:
    attacks = [
        {"hand": "main_hand", "damage": "1d8+3"},
        {"hand": "ranged", "damage": "1d10+1"},
    ]
    # close combat: the crossbow rolls with disadvantage, 0.40 vs the sword's 0.65 (SRD 5.1)
    close = [
        {"option": "main_hand", "probability": 0.65, "crit_chance": 0.05},
        {"option": "ranged", "probability": 0.40, "crit_chance": 0.02},
    ]
    assert pick_option(close, attacks) == "main_hand"
    # a hit chance edge with a smaller die loses on damage: 0.70 * 3.5 vs 0.60 * 11
    far = [
        {"option": "main_hand", "probability": 0.60, "crit_chance": 0.05},
        {"option": "ranged", "probability": 0.70, "crit_chance": 0.05},
    ]
    heavy = [{"hand": "main_hand", "damage": "2d6+4"}, {"hand": "ranged", "damage": "1d6"}]
    assert pick_option(far, heavy) == "main_hand"
    assert avg_dice("1d8+3") == 7.5 and avg_dice("2d6") == 7.0 and avg_dice("1d4-1") == 1.5


def test_m29_h9_display_turn_start_surge_xp_and_first_fight_line() -> None:
    surge = {
        "feature": "action-surge",
        "name": "Action Surge",
        "economy": "extra_action",
        "available": True,
        "uses_left": 1,
        "uses_max": 1,
    }
    sheet: Msg = {"feature_actions": [surge], "features": []}
    lines = option_lines(_combat(), "pc-1", sheet)
    assert any("do feature action-surge" in x for x in lines)
    assert not any("spent or unavailable" in x and "Action Surge" in x for x in lines)
    spent = {**surge, "available": False, "uses_left": 0}
    after = option_lines(_combat(), "pc-1", {"feature_actions": [spent], "features": []})
    assert any("spent or unavailable: Action Surge" in x for x in after)
    text = look_text(_state(combat=_combat()), 5, "pc-1", sheet)
    assert "attacks_left" not in text
    first = look_text(_state(combat=_combat(active=None)), 5, "pc-1", None)
    assert "turn of None" not in first
    xp = digest([{"type": "event", "kind": "xp_gained", "line": "Ana gains 150 XP.", "seq": 3}])
    assert "XP award (milestone or reward): Ana gains 150 XP." in xp


def test_m29_h10_keepsakes_and_equip_commands() -> None:
    sheet: Msg = {"keepsakes": [{"id": "k1", "name": "Brass clapper"}]}
    assert "Brass clapper (keepsake, not for sale)" in trade.keepsake_text(sheet)
    assert trade.keepsake_text({}) == "Keepsakes: none"
    args = build_parser().parse_args(["equip", "longbow", "--as", "Ana"])
    assert (args.command, args.words, args.as_name) == ("equip", ["longbow"], "Ana")
    assert build_parser().parse_args(["unequip", "shield"]).words == ["shield"]


def test_m29_h11_look_shows_light_cover_surfaces_and_the_roll_reason() -> None:
    zones = [
        {"id": "z1", "name": "Gate", "cover": "three_quarters", "high_ground": True},
        {"id": "z2", "name": "Yard", "surfaces": [{"kind": "oil", "rounds_left": 3}]},
    ]
    lines = zone_lines(_combat(zones=zones))
    assert any("Gate: three-quarters cover, high ground" in x for x in lines)
    assert any("Yard: surface oil 3r" in x for x in lines)
    party = [{"id": "pc-1", "name": "Ana", "hp": 5, "max_hp": 9, "light": "Torch"}]
    text = look_text(_state(party=party, combat=_combat(zones=zones)), 1, "pc-1")
    assert "carries a lit Torch" in text and "zone z1 Gate" in text
    dice = {"label": "Attack", "total": 17, "target": 21, "adv": "advantage"}
    dice["adv_why"] = ["high ground"]
    assert "advantage: high ground" in roll_why(dice)
    assert "high ground" in digest([{"type": "dice_roll", "seq": 1, "dice": dice}])


def test_m29_h12_settle_waits_for_the_narration_of_the_acted_turn() -> None:
    link = _link(live=True)
    link.quiet, link.grace = 0.2, 10.0

    async def feed() -> None:
        link.conn.log.append({"type": "event", "seq": 1, "kind": "attack", "line": "hit"})
        await asyncio.sleep(1.2)  # the live model is silent for a while
        link.conn.log.append({"type": "narration_chunk", "id": "n", "text": "It falls."})
        link.conn.log.append({"type": "narration_done", "id": "n"})

    async def run() -> list[Msg]:
        task = asyncio.create_task(feed())
        began = time.monotonic()
        got = await link.settle(0)
        await task
        assert time.monotonic() - began >= 1.1
        return got

    assert any(m["type"] == "narration_done" for m in asyncio.run(run()))


def test_m29_h12_settle_ends_after_a_bounded_quiet_when_no_narration_comes() -> None:
    link = _link()
    link.quiet, link.grace = 0.1, 0.5

    async def run() -> float:
        link.conn.log.append({"type": "event", "seq": 1, "kind": "move", "line": "steps"})
        began = time.monotonic()
        await link.settle(0)
        return time.monotonic() - began

    assert 0.4 <= asyncio.run(run()) < 3.0


def test_m29_h13_the_ending_narration_is_printed() -> None:
    text = look_text(_state(complete=True, epilogue="The beacon burns on."), 9, "pc-1")
    assert "THE CAMPAIGN IS COMPLETE." in text and "Ending: The beacon burns on." in text
    assert "The beacon burns on." in digest([{"type": "epilogue", "text": "The beacon burns on."}])


def test_m29_h14_slots_spells_level_up_prices_and_the_cap() -> None:
    sheet: Msg = {
        "name": "Ana",
        "level": 3,
        "class_index": "wizard",
        "max_hp": 18,
        "features": [{"name": "Arcane Recovery"}],
        "resources": [],
        "spellcasting": {
            "cantrips": [{"index": "fire-bolt"}],
            "levels": [
                {
                    "level": 1,
                    "slots": [{"current": 2, "maximum": 4}],
                    "spells": [{"index": "shield", "prepared": True}],
                }
            ],
        },
    }
    out = hero_lines(sheet, in_fight=False)
    assert "slots L1 2/4" in out[0] and "fire-bolt (cantrip)" in out[1]
    assert len(hero_lines(sheet, in_fight=True)) == 1
    later: Msg = {**sheet, "level": 4, "max_hp": 24}
    later["features"] = [{"name": "Arcane Recovery"}, {"name": "Ability Score Improvement"}]
    note = learned(sheet, later)
    assert "now level 4" in note and "features: Ability Score Improvement" in note
    line = {"item_id": "camp-ration", "name": "Ration", "price_gp": 1, "bulk": "2 for 1 gp"}
    shown = trade.stock_text({"npc_id": "n1", "npc_name": "Brewer", "stock": [line]}, 15)
    assert "Ration 2 for 1 gp" in shown and f"At most {trade.trade_cap()} of an item" in shown
    assert "by design" in PLAY_SCRIPT.read_text(encoding="utf-8")


def test_m29_h14_look_lists_heroes_and_supplies_with_the_fake_storyteller(tmp_path: Path) -> None:
    port = free_port()

    async def play() -> tuple[str, str]:
        await ops.cmd_new(tmp_path, "r2", "solo", 3, False, port)
        look = await ops.cmd_look(tmp_path, "r2", None)
        bad = await ops.cmd_equip(tmp_path, "r2", None, ["no-such-thing"], True)
        return look, bad

    try:
        look, bad = asyncio.run(play())
    finally:
        ops.cmd_stop(tmp_path, "r2")
    assert "Camp supplies:" in look and "Heroes:" in look
    assert "matches 0 items" in bad


def _cone_sheet() -> Msg:
    cone = {"index": "burning-hands", "prepared": True, "target_kind": "area"}
    cone |= {"range_kind": "self", "area_shape": "cone", "area_feet": 15}
    aura = {"index": "aura", "prepared": True, "target_kind": "area", "range_kind": "self"}
    level = {"level": 1, "slots": [{"current": 2}], "spells": [cone, aura]}
    return {"spellcasting": {"cantrips": [], "levels": [level]}}


def test_m29_r26_harness_aims_a_self_cone_at_a_zone() -> None:
    zones = [{"id": "z1", "name": "Gate"}, {"id": "z2", "name": "Yard"}]
    combat: Msg = {"zones": zones, "tokens": []}
    sheet = _cone_sheet()
    cmd = build_command(["cast", "burning-hands", "Yard"], "pc-1", [], sheet, combat)
    assert cmd["target_zone"] == "z2" and cmd["target_ids"] == []
    with pytest.raises(UsageError, match="needs a zone"):
        build_command(["cast", "burning-hands"], "pc-1", [], sheet, combat)
    assert "target_zone" not in build_command(["cast", "aura"], "pc-1", [], sheet, combat)
    text = "\n".join(spell_lines(sheet, combat, ECO))
    assert "do cast burning-hands <zone id|name> (15-ft cone from your zone)" in text
    assert "do cast aura   (level 1)" in text and "(zones: z1=Gate, z2=Yard)" in text
