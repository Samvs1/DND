"""The gear bots' decisions and assertions (M27.10): pure helpers over the public views."""

import json
import random
from pathlib import Path

from aidm.models.item_events import ItemUseRefused
from aidm.models.state import GameState
from scripts.sim.checks import hero_up
from scripts.sim.client import Msg
from scripts.sim.combat import Plan
from scripts.sim.gear import refusal_runs, tail_uses
from scripts.sim.gear_fight import KIT_USE, gear_command, gear_key
from tests.unit.rules.item_fixtures import DOCKS, at, hero

TORCH = {"item": "torch", "use_id": "torch-light", "effect": "light_place", "target": "none"}
THROW = {"item": "torch", "use_id": "torch-throw", "effect": "ignite", "target": "zone"}
OIL = {"item": "oil-flask", "use_id": "oil-flask-throw", "effect": "surface", "target": "zone"}
KIT = {"item": "healers-kit", "use_id": KIT_USE, "effect": "stabilize", "target": "ally"}


def _combat(*, dark: bool = False, oil_in: str = "", ally_zone: str = "a") -> Msg:
    zones = [
        {
            "id": z,
            "dark": dark,
            "lit": not dark,
            "surfaces": [{"kind": "oil"}] if z == oil_in else [],
        }
        for z in "ab"
    ]
    tokens = [
        {
            "creature_id": "pc-1",
            "side": "party",
            "zone_id": "a",
            "hp": 9,
            "max_hp": 9,
            "dead": False,
        },
        {
            "creature_id": "pc-2",
            "side": "party",
            "zone_id": ally_zone,
            "hp": 0,
            "max_hp": 9,
            "dead": False,
        },
        {
            "creature_id": "gob",
            "side": "hostile",
            "zone_id": "b",
            "hp": 7,
            "max_hp": 7,
            "dead": False,
        },
    ]
    economy = {"action": True, "bonus_action": True, "movement_left": 30}
    edges = [{"a": "a", "b": "b", "feet": 15}]
    return {"zones": zones, "edges": edges, "tokens": tokens, "economy": economy}


def _party(*, light: str = "", dying: bool = False) -> list[Msg]:
    me = {"id": "pc-1", "light": light, "dying": False, "stable": False, "dead": False}
    ally = {"id": "pc-2", "light": "", "dying": dying, "stable": False, "dead": False}
    return [me, ally]


def _plan() -> Plan:
    return Plan(role="fighter", hero_id="pc-1", rng=random.Random(1))


def _target(combat: Msg) -> Msg:
    return combat["tokens"][2]


def test_gear_command_lights_a_torch_in_a_dark_zone() -> None:
    combat = _combat(dark=True)
    cmd = gear_command(_plan(), combat, _party(), [TORCH], _target(combat))
    assert cmd is not None and cmd["use_id"] == "torch-light" and cmd["item"] == "torch"
    lit = gear_command(_plan(), combat, _party(light="Torch"), [TORCH], _target(combat))
    assert lit is None  # one light per hero


def test_gear_command_throws_oil_then_the_lit_torch_into_it() -> None:
    combat = _combat()
    oil = gear_command(_plan(), combat, _party(), [OIL], _target(combat))
    assert oil is not None and oil["target_zone"] == "b"  # the touching zone where the foe is
    oily = _combat(oil_in="b")
    plan = _plan()
    light = gear_command(plan, oily, _party(), [TORCH], _target(oily))
    assert light is not None and light["use_id"] == "torch-light"  # light up to set it alight
    throw = gear_command(plan, oily, _party(light="Torch"), [THROW], _target(oily))
    assert throw is not None and throw["use_id"] == "torch-throw" and throw["target_zone"] == "b"


def test_gear_command_uses_the_kit_on_a_dying_ally() -> None:
    combat = _combat()
    plan = _plan()
    cmd = gear_command(plan, combat, _party(dying=True), [KIT], _target(combat))
    assert cmd is not None and cmd["use_id"] == KIT_USE and cmd["target_id"] == "pc-2"
    far = _combat(ally_zone="b")
    walk = gear_command(plan, far, _party(dying=True), [KIT], _target(far))
    assert walk == {"type": "move", "actor_id": "pc-1", "zone_id": "b"}
    assert plan.kit_chances == 2


def test_gear_command_never_repeats_a_refused_use() -> None:
    combat = _combat(dark=True)
    plan = _plan()
    cmd = gear_command(plan, combat, _party(), [TORCH], _target(combat))
    assert cmd is not None
    plan.fight_refused.add(gear_key(cmd))
    assert gear_command(plan, combat, _party(), [TORCH], _target(combat)) is None


def test_refusal_runs_flag_the_same_refusal_over_and_over() -> None:
    same = ItemUseRefused(creature_id="pc-1", item="torch", message="The place is lit.")
    other = ItemUseRefused(creature_id="pc-1", item="rope", message="Nothing to tie.")
    assert refusal_runs([same, same, other, same, same]) == []
    assert len(refusal_runs([same, same, same])) == 1


def test_m27_sim_unconscious_hero_cannot_propose() -> None:
    state: GameState = at(DOCKS, hero("pc-1"))
    assert hero_up(state, "pc-1")
    state.creatures["pc-1"].hp = 0  # unconscious, not dead: its bot cannot act
    assert not hero_up(state, "pc-1")
    assert not hero_up(state, "pc-unknown")


def test_m29_kit_used_in_a_retried_wipe_still_counts(tmp_path: Path) -> None:
    # M29.6: a retry cuts the wiped fight from the live log into events.<n>.defeat; the gear
    # check must still see the healer's kit used there (seed 3 failed after the tuning).
    used = {"type": "item_used", "creature_id": "pc-1", "item": "healers-kit", "use_id": "kit"}
    rows = [{"seq": 40, "event": used}, {"seq": 41, "event": {"type": "turn_ended"}}]
    text = "\n".join(json.dumps(r) for r in rows)
    (tmp_path / "events.1.defeat").write_text(text, encoding="utf-8")
    assert tail_uses(tmp_path, "kit") == 1
    assert tail_uses(tmp_path, "torch-light") == 0
    assert tail_uses(tmp_path / "missing", "kit") == 0
