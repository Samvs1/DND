"""M29.9d: the round-3 harness items (scripts/agent only), offline."""

from typing import Any

from scripts.agent.commands import answer_message
from scripts.agent.ops import _took
from scripts.agent.spells import spell_lines
from scripts.agent.text import look_text, waiting_lines

Msg = dict[str, Any]
ECO: Msg = {"action": True, "bonus_action": True, "attacks_left": 0, "movement_left": 30}


def _tok(cid: str, side: str, zone: str) -> Msg:
    base = {"creature_id": cid, "name": cid, "side": side, "hp": 9, "max_hp": 9, "dead": False}
    return {**base, "zone_id": zone}


def _combat() -> Msg:
    return {
        "round": 1,
        "active_id": "pc-1",
        "zones": [{"id": f"z{n}", "name": f"Zone{n}"} for n in (1, 2, 3)],
        "edges": [{"a": "z1", "b": "z2", "feet": 15}, {"a": "z2", "b": "z3", "feet": 30}],
        "tokens": [_tok("pc-1", "party", "z1"), _tok("wolf-1", "hostile", "z2")],
        "economy": ECO,
    }


def test_m29_r3_harness_sure_parley_in_the_offer_line() -> None:
    offer = {"id": "o1", "foes": ["wolf"], "options": ["fight", "parley"], "sure": ["parley"]}
    line = waiting_lines({"offer": offer})[0]
    assert "(parley sure to hold)" in line
    offer["sure"] = []
    assert "sure" not in waiting_lines({"offer": offer})[0]


def test_m29_r3_harness_resource_cast_spell_is_listed() -> None:
    spell = {"index": "darkness", "level": 2, "prepared": True, "resource": "infernal-legacy"}
    spell |= {"casting_time": "action", "target_kind": "creature"}
    sheet: Msg = {
        "spellcasting": {"levels": [{"level": 2, "slots": [], "spells": [spell]}]},
        "resources": [{"key": "infernal-legacy", "current": 1, "maximum": 1}],
    }
    assert "do cast darkness" in "\n".join(spell_lines(sheet, _combat(), ECO))
    sheet["resources"][0]["current"] = 0
    assert "darkness (no uses left)" in "\n".join(spell_lines(sheet, _combat(), ECO))


def test_m29_r3_harness_answer_finale_id_confirms() -> None:
    finale = {"question": "q?", "chosen": None, "options": [{"id": "a", "title": "A"}]}
    state: Msg = {"finale": finale}
    want = {"type": "choose_finale", "option_id": "a", "confirm": True}
    assert answer_message(state, ["finale", "a"]) == [want]
    assert answer_message(state, ["finale"]) == [want]
    assert answer_message(state, ["a"])[0]["confirm"] is False


def test_m29_r3_harness_cone_marks_zones_in_reach() -> None:
    cone = {"index": "burning-hands", "level": 0, "target_kind": "area", "range_kind": "self"}
    cone |= {"area_feet": 15, "area_shape": "cone", "casting_time": "action"}
    sheet: Msg = {"spellcasting": {"cantrips": [cone], "levels": []}}
    zones = [x for x in spell_lines(sheet, _combat(), ECO) if x.startswith("(zones")][0]
    assert "z1=Zone1 [in reach]" in zones
    assert "z2=Zone2 [in reach]" in zones
    assert "z3=Zone3," not in zones and "Zone3 [in reach]" not in zones


def test_m29_r3_harness_levelup_says_the_defaults() -> None:
    picks = {"subclass": "evocation", "asi": {"int": 2}, "class_choices": {"boon": ["blade"]}}
    text = _took(picks)
    assert "subclass evocation" in text and "int+2" in text and "boon" in text
    assert _took({}) == "none needed"


def test_m29_r3_harness_do_end_still_prints_options() -> None:
    combat = _combat() | {"active_id": "wolf-1"}
    state: Msg = {"phase": "combat", "campaign_id": "c", "party": [], "combat": combat}
    out = look_text(state, 3, "pc-1")
    assert "Options:" in out and "not your turn" in out
