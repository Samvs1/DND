"""M29.5a: the playtest harness shows every waiting card, parley skills, area spells, allies."""

import asyncio
from pathlib import Path
from typing import Any

import pytest

from scripts.agent import ops
from scripts.agent.commands import UsageError, answer_message, build_command
from scripts.agent.text import digest, look_text, option_lines

Msg = dict[str, Any]
ECO: Msg = {"action": True, "bonus_action": True, "attacks_left": 1, "movement_left": 30}
SLOTS = [{"kind": "standard", "current": 1, "maximum": 2}]
NO_SLOTS = [{"kind": "standard", "current": 0, "maximum": 1}]


def _tok(cid: str, name: str, side: str) -> Msg:
    base = {"creature_id": cid, "name": name, "side": side, "hp": 9, "max_hp": 9}
    return {**base, "dead": False, "zone_id": "z1"}


def _combat(eco: Msg = ECO) -> Msg:
    return {
        "round": 1,
        "active_id": "pc-1",
        "turn_of": "pc-1",
        "zones": [{"id": "z1", "name": "Gate"}, {"id": "z2", "name": "Yard"}],
        "tokens": [
            _tok("pc-1", "Merrin", "party"),
            _tok("pc-2", "Tomas", "party"),
            _tok("wolf-1", "Wolf", "hostile"),
        ],
        "economy": eco,
    }


def _spell(index: str, kind: str, **kw: Any) -> Msg:
    return {"index": index, "prepared": True, "target_kind": kind, **kw}


SHEET: Msg = {
    "spellcasting": {
        "cantrips": [_spell("fire-bolt", "creature")],
        "levels": [
            {
                "level": 1,
                "slots": SLOTS,
                "spells": [_spell("cure-wounds", "creature"), _spell("sleep", "area")],
            },
            {"level": 3, "slots": NO_SLOTS, "spells": [_spell("fireball", "area")]},
        ],
    }
}


def _state(**extra: Any) -> Msg:
    base: Msg = {"campaign_id": "c-1", "phase": "play", "party": [], "scene": None}
    return {**base, **extra}


def test_travel_confirm_is_shown_and_answerable() -> None:
    prompt = "Leaving the Gate behind: confirm to travel."
    text = look_text(_state(), 5, "pc-1", pending=prompt)
    assert "CONFIRM: " + prompt in text and "answer confirm | cancel" in text
    assert "CONFIRM" in digest([{"type": "pending_confirmation", "prompt": prompt}])
    assert answer_message(_state(), ["confirm"], prompt) == [{"type": "confirm_hostile"}]
    assert answer_message(_state(), ["cancel"], prompt) == [{"type": "cancel_hostile"}]


def test_vote_is_shown_and_a_wrong_answer_says_what_waits() -> None:
    vote = {
        "vote_id": "v1",
        "kind": "rest",
        "detail": "long",
        "proposer_id": "pc-1",
        "voters": ["pc-1", "pc-2"],
        "ready": ["pc-1"],
        "declined": [],
    }
    tomas = {"id": "pc-2", "name": "Tomas", "hp": 9, "max_hp": 9}
    state = _state(vote=vote, party=[tomas])
    text = look_text(state, 5, "pc-1")
    assert "VOTE v1 (rest long)" in text and "waiting: Tomas" in text
    with pytest.raises(UsageError, match="Waiting now: CONFIRM: Go on"):
        answer_message(_state(), ["yes"], "Go on?")
    with pytest.raises(UsageError, match="nothing is waiting"):
        answer_message(_state(), ["yes"])


def test_parley_lists_the_engine_skills_and_refuses_others() -> None:
    offer = {"id": "o1", "foes": ["Wolf"], "difficulty": "easy", "options": ["fight", "parley"]}
    text = look_text(_state(offer=offer), 1, "pc-1")
    assert "answer parley [persuasion|intimidation]" in text
    got = answer_message(_state(offer=offer), ["parley", "intimidation"])
    assert got == [{"type": "answer_offer", "choice": "parley", "skill": "intimidation"}]
    with pytest.raises(UsageError, match="persuasion or intimidation"):
        answer_message(_state(offer=offer), ["parley", "deception"])
    with pytest.raises(UsageError, match="only parley takes a skill"):
        answer_message(_state(offer=offer), ["fight", "persuasion"])


def test_area_spell_takes_a_zone_by_id_or_name() -> None:
    combat = _combat()
    cmd = build_command(["cast", "sleep", "yard"], "pc-1", [], SHEET, combat)
    assert cmd["target_zone"] == "z2" and cmd["target_ids"] == []
    with pytest.raises(UsageError, match="needs a zone"):
        build_command(["cast", "sleep"], "pc-1", [], SHEET, combat)
    with pytest.raises(UsageError, match="no zone 'nowhere'"):
        build_command(["cast", "sleep", "nowhere"], "pc-1", [], SHEET, combat)
    text = "\n".join(option_lines(combat, "pc-1", SHEET))
    assert "do cast sleep <zone id|name>" in text and "(zones: z1=Gate, z2=Yard)" in text


def test_ally_heal_by_name_and_id_and_cantrips_are_offered() -> None:
    combat = _combat()
    by_name = build_command(["cast", "cure-wounds", "Tomas"], "pc-1", [], SHEET, combat)
    assert by_name["target_ids"] == ["pc-2"]
    by_id = build_command(["cast", "cure-wounds", "pc-2"], "pc-1", [], SHEET, combat)
    assert by_id["target_ids"] == ["pc-2"]
    text = "\n".join(option_lines(combat, "pc-1", SHEET))
    assert "do cast fire-bolt <foe#|ally id|ally name>   (cantrip)" in text
    assert "(allies: pc-1=Merrin, pc-2=Tomas)" in text


def test_spells_without_slot_or_action_are_hidden_with_the_reason() -> None:
    text = "\n".join(option_lines(_combat(), "pc-1", SHEET))
    assert "do cast fireball" not in text and "fireball (no slot left)" in text
    spent = {**ECO, "action": False, "attacks_left": 0}
    text = "\n".join(option_lines(_combat(spent), "pc-1", SHEET))
    assert "do cast fire-bolt" not in text and "fire-bolt (no action left)" in text


def test_fled_hero_is_marked_as_left_the_fight() -> None:
    combat = _combat()
    combat["tokens"][1]["withdrawn"] = True
    text = look_text(_state(combat=combat), 1, "pc-1")
    assert "Tomas (party) 9/9hp (left the fight)" in text


class _Conn:
    log: list[Msg] = []
    player_id = "p1"


class _FakeLink:
    def __init__(self, said: list[Msg], state: Msg) -> None:
        self.said = said
        self.state = state
        self.conn = _Conn()

    async def send(self, msg: Msg) -> list[Msg]:
        return self.said

    async def command(self, cmd: Msg) -> list[Msg]:
        return self.said

    async def close(self) -> None:
        return None


class _Wired:
    def __init__(self) -> None:
        self.notes: list[str] = []
        self.held = 0


def _wire(monkeypatch: pytest.MonkeyPatch, link: _FakeLink) -> _Wired:
    player = {"name": "Merrin", "hero_id": "pc-1"}
    got = _Wired()
    session = type("S", (), {"players": [player, {"name": "Tomas", "hero_id": "pc-2"}]})()

    async def actor(_session: Any, _name: Any) -> tuple[_FakeLink, Msg]:
        return link, player

    async def report(_link: Any, _who: Msg, said: list[Msg], note: str = "") -> str:
        got.notes.append(note)
        return digest(said)

    async def hold(_session: Any, _acting: Msg) -> list[Any]:
        got.held += 1
        return []

    monkeypatch.setattr(ops, "_session", lambda _root, _run: session)
    monkeypatch.setattr(ops, "_actor", actor)
    monkeypatch.setattr(ops, "_report", report)
    monkeypatch.setattr(ops, "_hold_seats", hold)
    return got


def test_refused_move_prints_the_refusal_not_a_move(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    error = {"type": "error", "code": "refused", "text": "Too far."}
    link = _FakeLink([error], _state(combat=_combat()))
    got = _wire(monkeypatch, link)
    out = asyncio.run(ops.cmd_move(tmp_path, None, None, "z9"))
    assert got.notes == [""] and "ERROR refused: Too far." in out
    link.said = []
    asyncio.run(ops.cmd_move(tmp_path, None, None, "z2"))
    assert got.notes[-1] == "Merrin moves: z2"


def test_retry_holds_the_other_seats_so_heroes_are_not_auto_played(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    state = _state(phase="defeated", defeat="x", checkpoint="gate")
    got = _wire(monkeypatch, _FakeLink([], state))
    asyncio.run(ops.cmd_answer(tmp_path, None, None, ["retry"]))
    assert got.held == 1
