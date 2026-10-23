"""M29.4: the playtest harness fixes H1-H6 (fake storyteller, no network)."""

import asyncio
from pathlib import Path
from typing import Any

import pytest

from scripts.agent import ops, session
from scripts.agent.commands import UsageError, answer_message, build_command
from scripts.agent.session import Session, port_open, set_current_unless_live
from scripts.agent.text import ascii_text, digest, look_text, option_lines
from scripts.agent.trade import match_line, parse_trade
from scripts.sim.server import NO_GRACE_S, SimServer, free_port

Msg = dict[str, Any]
ECO: Msg = {"action": True, "bonus_action": True, "attacks_left": 1, "movement_left": 30}
SECOND_WIND: Msg = {
    "feature": "second-wind",
    "name": "Second Wind",
    "economy": "bonus_action",
    "available": True,
    "uses_left": 1,
    "uses_max": 1,
    "target_kind": "self",
}
CHANNEL: Msg = {**SECOND_WIND, "feature": "turn-undead", "name": "Turn Undead", "economy": "action"}
HEALING_WORD = {
    "level": 1,
    "slots": [{"kind": "standard", "current": 2, "maximum": 2}],
    "spells": [{"index": "healing-word", "prepared": True}],
}


def _combat(eco: Msg) -> Msg:
    me = {"creature_id": "h", "name": "H", "side": "party", "hp": 9, "max_hp": 9, "dead": False}
    rat = {**me, "creature_id": "r", "name": "Rat", "side": "hostile"}
    return {"active_id": "h", "turn_of": "h", "tokens": [me, rat], "economy": eco, "zones": []}


def test_ascii_text_transliterates_curly_quotes_and_dashes() -> None:
    raw = "It’s “quiet” — too quiet… – ok"
    assert ascii_text(raw) == 'It\'s "quiet" - too quiet... - ok'
    assert "?" not in ascii_text(raw)


def test_fighter_options_list_second_wind_and_cleric_lists_features_and_spells() -> None:
    fighter = option_lines(_combat(ECO), "h", {"feature_actions": [SECOND_WIND]})
    assert any(line.startswith("do feature second-wind") for line in fighter)
    cleric_sheet = {
        "feature_actions": [CHANNEL],
        "spellcasting": {"levels": [HEALING_WORD]},
    }
    cleric = option_lines(_combat(ECO), "h", cleric_sheet)
    assert any(line.startswith("do feature turn-undead") for line in cleric)
    assert any(line.startswith("do cast healing-word") for line in cleric)
    cmd = build_command(["feature", "second-wind"], "h", [], {"feature_actions": [SECOND_WIND]})
    assert cmd == {"type": "feature_action", "actor_id": "h", "feature_id": "second-wind"}


def test_rogue_cunning_action_is_a_bonus_option() -> None:
    sheet: Msg = {"features": [{"index": "cunning-action"}]}
    assert any(line.startswith("do bonus dash") for line in option_lines(_combat(ECO), "h", sheet))
    cmd = build_command(["bonus", "hide"], "h", [], sheet)
    assert cmd == {"type": "hide", "actor_id": "h", "bonus_action": True}


def test_spent_action_hides_attack_and_dodge_but_keeps_the_bonus_feature() -> None:
    spent = {**ECO, "action": False, "attacks_left": 0}
    lines = option_lines(_combat(spent), "h", {"feature_actions": [SECOND_WIND]})
    assert not any(x.startswith(("do attack", "do dodge", "do dash")) for x in lines)
    assert any(x.startswith("do feature second-wind") for x in lines) and "do end" in lines
    gone = {**spent, "bonus_action": False}
    text = "\n".join(option_lines(_combat(gone), "h", {"feature_actions": [SECOND_WIND]}))
    assert "do feature" not in text and "Second Wind" in text


def test_look_says_when_a_hero_can_level_up_and_digest_reports_the_message() -> None:
    state: Msg = {"campaign_id": "c", "phase": "play", "party": []}
    assert "LEVEL UP available" in look_text(state, 1, "pc-p1", None, True)
    assert "LEVEL UP" not in look_text(state, 1, "pc-p1", None, False)
    got = digest([{"type": "level_up_available", "creature_id": "pc-p1", "level": 2}])
    assert "LEVEL UP available for pc-p1 (level 2)" in got


def test_defeat_look_lists_choices_and_answers_work() -> None:
    state: Msg = {
        "campaign_id": "c-1",
        "phase": "defeated",
        "defeat": "Darkness.",
        "checkpoint": "the gate",
        "party": [],
    }
    text = look_text(state, 3, "pc-p1")
    assert "answer retry | load <save id> | new" in text
    assert answer_message(state, ["retry"]) == [{"type": "defeat_retry"}]
    assert answer_message(state, ["new"]) == [{"type": "defeat_new"}]
    assert answer_message(state, ["load"]) == [{"type": "defeat_load", "campaign_id": "c-1"}]
    assert answer_message(state, ["load", "c-9"])[0]["campaign_id"] == "c-9"
    with pytest.raises(UsageError):
        answer_message(state, ["yes"])


def test_trade_parsing_and_item_matching() -> None:
    assert parse_trade(["list"]) == ("list", "", 1)
    assert parse_trade(["buy", "healing", "potion", "3"]) == ("buy", "healing potion", 3)
    with pytest.raises(UsageError):
        parse_trade(["buy"])
    lines = [
        {"item_id": "healing-potion", "name": "Potion of Healing"},
        {"item_id": "rope", "name": "Rope"},
    ]
    assert match_line(lines, "rope", "item_id", "name")["item_id"] == "rope"
    assert match_line(lines, "healing potion", "item_id", "name")["item_id"] == "healing-potion"
    with pytest.raises(UsageError):
        match_line(lines, "sword", "item_id", "name")


def test_parallel_runs_keep_their_own_pointer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    Session(run="a", port=1).save(tmp_path)
    (tmp_path / "CURRENT").write_text("a", encoding="utf-8")
    monkeypatch.setattr(session, "alive", lambda s: s.run == "a")
    assert set_current_unless_live(tmp_path, "b") is False
    assert (tmp_path / "CURRENT").read_text(encoding="utf-8") == "a"
    monkeypatch.setattr(session, "alive", lambda s: False)
    assert set_current_unless_live(tmp_path, "b") is True
    assert (tmp_path / "CURRENT").read_text(encoding="utf-8") == "b"


def test_harness_server_has_no_turn_timer_and_a_day_of_grace(tmp_path: Path) -> None:
    async def run() -> tuple[float | None, float]:
        srv = SimServer(1, tmp_path / "saves", port=free_port(), no_timers=True)
        await srv.start()
        try:
            return srv.table.turn_seconds, srv.table.config.grace_seconds
        finally:
            await srv.stop()

    turn, grace = asyncio.run(run())
    assert turn is None and grace == NO_GRACE_S


def test_fresh_view_trade_and_second_run_with_the_fake_storyteller(tmp_path: Path) -> None:
    port = free_port()

    async def play() -> list[str]:
        out = [await ops.cmd_new(tmp_path, "t1", "solo", 3, False, port)]
        out.append(await ops.cmd_act(tmp_path, "t1", None, "I walk to the market"))
        out.append(await ops.cmd_trade(tmp_path, "t1", None, ["list"]))
        out.append(await ops.cmd_trade(tmp_path, "t1", None, ["buy", "camp-ration"]))
        out.append(await ops.cmd_trade(tmp_path, "t1", None, ["sell", "crowbar"]))
        return out

    try:
        first, acted, listed, bought, sold = asyncio.run(play())
    finally:
        ops.cmd_stop(tmp_path, "t1")
    assert not port_open(port)
    assert "[save c-" in first and "[save c-" in acted
    assert "Shop of" in listed and "camp-ration" in listed and "15gp" in listed
    assert "Brienne 12/12hp ac18 L1 fighter 14gp" in bought  # 15gp - the 1gp camp ration
    assert "ERROR" not in sold and "fighter 14gp" not in sold
