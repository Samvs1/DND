"""M41.5: playtest harness Z18 (run pointer), Z19 (potions), Z20 (attack weapon). No network."""

import asyncio
from pathlib import Path
from typing import Any

import pytest

from scripts.agent import ops, session
from scripts.agent.commands import UsageError, build_command
from scripts.agent.session import Session, run_footer
from scripts.agent.text import option_lines

Msg = dict[str, Any]
SHEET: Msg = {
    "attacks": [
        {"hand": "main_hand", "item": "longsword", "name": "Longsword", "damage": "1d8+3"},
        {"hand": "ranged", "item": "light-crossbow", "name": "Light Crossbow", "damage": "1d8"},
    ],
    "inventory": [
        {"item": "potion-of-healing", "name": "Potion of Healing", "qty": 2, "category": "potion"},
        {"item": "rope", "name": "Rope", "qty": 1, "category": "gear"},
    ],
    "gear_uses": [],
}
FOES: list[Msg] = [{"creature_id": "rat-1", "name": "Rat", "hp": 3, "max_hp": 3, "dead": False}]
ECO: Msg = {"action": True, "bonus_action": True, "attacks_left": 1, "movement_left": 30}


def test_z20_attack_names_a_weapon_or_leaves_it_to_the_best_fit() -> None:
    plain = build_command(["attack", "1"], "h", FOES, SHEET)
    assert plain["option"] == ""
    named = build_command(["attack", "1", "Longsword"], "h", FOES, SHEET)
    assert named["option"] == "main_hand"
    assert build_command(["attack", "1", "ranged"], "h", FOES, SHEET)["option"] == "ranged"
    with pytest.raises(UsageError):
        build_command(["attack", "1", "club"], "h", FOES, SHEET)


def test_z19_use_takes_a_potion_like_the_hotbar() -> None:
    cmd = build_command(["use", "potion-of-healing"], "h", FOES, SHEET)
    assert cmd == {"type": "use_item", "actor_id": "h", "item": "potion-of-healing"}
    with pytest.raises(UsageError):
        build_command(["use", "rope"], "h", FOES, SHEET)


def test_z19_z20_options_list_potions_and_weapons() -> None:
    me = {"creature_id": "h", "name": "H", "side": "party", "hp": 9, "max_hp": 9, "dead": False}
    rat = {**me, "creature_id": "rat-1", "name": "Rat", "side": "hostile"}
    combat = {"active_id": "h", "tokens": [me, rat], "economy": ECO, "zones": []}
    text = "\n".join(option_lines(combat, "h", SHEET))
    assert "do use potion-of-healing" in text
    assert "main_hand=Longsword" in text and "ranged=Light Crossbow" in text
    assert "rope" not in text


def _live_run(root: Path, name: str, monkeypatch: pytest.MonkeyPatch) -> None:
    Session(run=name, port=8999, pid=1).save(root)
    session.set_current(root, name)
    monkeypatch.setattr(session, "port_open", lambda _p: True)


def test_z18_new_refuses_to_take_over_a_live_default_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _live_run(tmp_path, "mine", monkeypatch)
    with pytest.raises(SystemExit, match="is live and is the default"):
        asyncio.run(ops.cmd_new(tmp_path, None, "classic", 1, False, 8101))
    assert session.live_current(tmp_path) == "mine"


def test_z18_every_output_names_its_run(tmp_path: Path) -> None:
    session.set_current(tmp_path, "alpha")
    assert run_footer(tmp_path, None, "anything") == "[run alpha]"
    assert run_footer(tmp_path, "beta", "anything") == "[run beta]"
    assert run_footer(tmp_path, None, "New run gamma: classic (fake), port 1.") == "[run gamma]"
    assert run_footer(tmp_path / "none", None, "x") == ""
