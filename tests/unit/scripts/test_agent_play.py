"""M29.3: the agent playtest harness (scripts/agent_play.py), fake storyteller, no real network."""

import asyncio
from pathlib import Path
from typing import Any

import pytest

from scripts.agent import ops
from scripts.agent.commands import UsageError, answer_message, build_command, target_of
from scripts.agent.session import Session, alive, current_run, port_open
from scripts.agent.text import digest, footer, look_text, option_lines
from scripts.agent_play import build_parser
from scripts.sim.client import Conn
from scripts.sim.server import free_port

Msg = dict[str, Any]


def _foe(index: int, hp: int, zone: str) -> Msg:
    return {
        "creature_id": f"rat-{index}",
        "name": "Rat",
        "side": "hostile",
        "hp": hp,
        "max_hp": 7,
        "zone_id": zone,
        "dead": False,
    }


FOES = [_foe(1, 7, "z1"), _foe(2, 3, "z2")]
TORCH = {
    "use_id": "torch-light",
    "item": "torch",
    "name": "Torch",
    "label": "Light",
    "cost": "bonus",
}
SHEET: Msg = {"gear_uses": [TORCH]}
HERO: Msg = {
    "id": "pc-p1",
    "name": "Brienne",
    "hp": 9,
    "max_hp": 12,
    "ac": 18,
    "level": 1,
    "class_index": "fighter",
    "gold": 15,
    "conditions": ["poisoned"],
}
SCENE: Msg = {
    "name": "Quay",
    "description": "Fog.",
    "npcs": [{"name": "Tobin"}],
    "features": [],
    "items": [],
    "shopkeepers": [],
    "exits": [{"name": "Boathouse", "locked": False, "visited": False}],
}


def _state(**extra: Any) -> Msg:
    base: Msg = {
        "campaign_id": "c-test-0001",
        "phase": "play",
        "region_tier": 1,
        "campaign_title": "The Test",
        "scene": SCENE,
        "party": [HERO],
    }
    return {**base, **extra}


def _combat() -> Msg:
    me = {**_foe(0, 9, "z1"), "creature_id": "pc-p1", "name": "Brienne", "side": "party"}
    return {
        "round": 1,
        "active_id": "pc-p1",
        "turn_of": "pc-p1",
        "zones": [{"id": "z1", "name": "Gate"}],
        "tokens": [me, *FOES],
        "economy": {"action": True, "bonus_action": True, "attacks_left": 1, "movement_left": 30},
    }


def test_target_of_numbers_and_ids() -> None:
    assert target_of("2", FOES) == "rat-2"
    assert target_of("rat-1", FOES) == "rat-1"
    with pytest.raises(UsageError):
        target_of("3", FOES)


def test_build_command_attack_end_cast_and_use() -> None:
    assert build_command(["attack", "1"], "h", FOES, None)["target_id"] == "rat-1"
    assert build_command(["end"], "h", FOES, None) == {"type": "end_turn", "actor_id": "h"}
    cast = build_command(["cast", "bless", "2"], "h", FOES, None)
    assert cast["spell_id"] == "bless" and cast["target_ids"] == ["rat-2"]
    use = build_command(["use", "torch-light"], "h", FOES, SHEET)
    assert use["item"] == "torch" and use["use_id"] == "torch-light"


@pytest.mark.parametrize("words", [[], ["attack"], ["use", "nope"], ["juggle"], ["cast"]])
def test_build_command_usage_errors(words: list[str]) -> None:
    with pytest.raises(UsageError):
        build_command(words, "h", FOES, SHEET)


def test_answer_message_each_kind_of_question() -> None:
    offer = _state(offer={"id": "o1", "options": ["fight", "parley"]})
    assert answer_message(offer, ["parley", "persuasion"]) == [
        {"type": "answer_offer", "choice": "parley", "skill": "persuasion"}
    ]
    with pytest.raises(UsageError):
        answer_message(offer, ["yes"])
    quest = answer_message(_state(quest_offer={"quest_id": "q1"}), ["no"])
    assert quest[0] == {"type": "answer_quest_offer", "quest_id": "q1", "accept": False}
    vote = answer_message(_state(vote={"vote_id": "v1"}), ["yes"])
    assert vote[0] == {"type": "vote", "vote_id": "v1", "ready": True}
    finale = _state(finale={"chosen": None, "question": "?", "options": []})
    assert answer_message(finale, ["light"])[0]["option_id"] == "light"
    assert answer_message(_state(), ["confirm"]) == [{"type": "confirm_hostile"}]
    with pytest.raises(UsageError):
        answer_message(_state(), ["yes"])


def test_footer_and_look_text_carry_save_id_and_event_number() -> None:
    assert footer("c-1", 42) == "[save c-1 | event 42]"
    text = look_text(_state(), 17, "pc-p1")
    assert text.splitlines()[-1] == "[save c-test-0001 | event 17]"
    assert "Place: Quay" in text and "People: Tobin" in text
    assert "Brienne 9/12hp ac18 L1 fighter 15gp [poisoned]" in text
    assert "Exits: Boathouse" in text


def test_look_text_in_a_fight_lists_options_for_the_active_hero() -> None:
    combat = _combat()
    lines = option_lines(combat, "pc-p1", SHEET)
    assert lines[0].startswith("do attack 1") and "do end" in lines
    assert any(line.startswith("do use torch-light") for line in lines)
    assert any(line.startswith("move <zone>") for line in lines)
    assert option_lines(combat, "someone-else", SHEET) == []
    text = look_text(_state(combat=combat), 5, "pc-p1", SHEET)
    assert "FIGHT round 1" in text and "Gate [z1]" in text


def test_digest_joins_narration_and_flags_errors() -> None:
    roll = {"label": "Stealth", "total": 14, "target": 12, "success": True}
    msgs: list[Msg] = [
        {"type": "narration_chunk", "text": "Fog rolls"},
        {"type": "narration_chunk", "text": "in."},
        {"type": "narration_done"},
        {"type": "dice_roll", "dice": roll},
        {"type": "error", "code": "refused", "text": "No.", "refusal": "no_action"},
    ]
    out = digest(msgs)
    assert "DM: Fog rolls in." in out
    assert "Roll: Stealth 14 vs 12 success=True" in out
    assert "ERROR refused: No. (no_action)" in out


def test_parse_party_shapes_and_class_lists() -> None:
    assert ops.parse_party("solo") == ["fighter"]
    assert ops.parse_party("fighter,cleric") == ["fighter", "cleric"]
    with pytest.raises(SystemExit):
        ops.parse_party("fighter,dragon")
    with pytest.raises(SystemExit):
        ops.parse_party("fighter,cleric,wizard,rogue,ranger")


def test_parser_takes_run_and_as_before_or_after_the_command() -> None:
    parser = build_parser()
    after = parser.parse_args(["act", "hello", "there", "--run", "r1", "--as", "Elowen"])
    before = parser.parse_args(["--run", "r1", "--as", "Elowen", "act", "hello", "there"])
    assert (after.run, after.as_name, after.text) == ("r1", "Elowen", ["hello", "there"])
    assert (before.run, before.as_name) == ("r1", "Elowen")
    new = parser.parse_args(["new", "--live", "--port", "8123"])
    assert new.live is True and new.port == 8123 and new.run is None


def test_session_roundtrip_and_current_run(tmp_path: Path) -> None:
    session = Session(run="r1", port=8199, shape="solo")
    session.players.append({"name": "Brienne", "token": "t", "hero_id": "pc-p1"})
    session.save(tmp_path)
    assert Session.load(tmp_path, "r1") == session
    with pytest.raises(SystemExit):
        current_run(tmp_path, None)
    (tmp_path / "CURRENT").write_text("r1", encoding="utf-8")
    assert current_run(tmp_path, None) == "r1"
    assert current_run(tmp_path, "other") == "other"
    with pytest.raises(SystemExit):
        Session.load(tmp_path, "../evil")


def test_server_start_reuse_and_stop_with_the_fake_storyteller(tmp_path: Path) -> None:
    port = free_port()

    async def play() -> list[str]:
        first = await ops.cmd_new(tmp_path, "t1", "solo", 3, False, port)
        look = await ops.cmd_look(tmp_path, None, None)  # reuses the running server
        acted = await ops.cmd_act(tmp_path, "t1", None, "I look around the room")
        return [first, look, acted]

    try:
        first, look, acted = asyncio.run(play())
        assert port_open(port)
        assert alive(Session.load(tmp_path, "t1"))
        assert "[save c-" in first and "| event " in first
        assert "Brienne acts: I look around the room" in acted
        save_id = first.splitlines()[-1].split("|")[0]
        assert look.splitlines()[-1].split("|")[0] == save_id
        assert acted.splitlines()[-1].startswith(save_id)
    finally:
        stopped = ops.cmd_stop(tmp_path, "t1")
    assert "server stopped" in stopped
    assert not port_open(port)
    with pytest.raises(SystemExit):
        asyncio.run(ops.cmd_look(tmp_path, "t1", None))


def test_m31_digest_shows_what_now_lines_and_foe_turn_is_busy() -> None:
    out = digest([{"type": "what_now_answer", "lines": ["Find the key", "Ask Wren"]}])
    assert "What now? (open steps):" in out and "  - Find the key" in out
    link = ops.Link.__new__(ops.Link)
    foe = {"creature_id": "rat-1", "side": "hostile", "dead": False}
    hero = {"creature_id": "pc-p2", "side": "party", "dead": False}
    link.conn = Conn("tester", "ws://localhost:1")
    link.conn.state = {"combat": {"active_id": "rat-1", "tokens": [foe, hero]}}
    assert link._busy() is True
    link.conn.state = {"combat": {"active_id": "pc-p2", "tokens": [foe, hero]}}
    assert link._busy() is False
