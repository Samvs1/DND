"""Combat decisions of the bots: pick ONE safe command from the public combat view.

Pure helpers over the `combat_state` / snapshot dicts plus the `hit_chances` the server sent.
Roles: the fighter closes in and attacks (charges); the caster uses its first cantrip, falling
back to a weapon; the rogue attacks and dodges when hurt while another hero still stands (the
last hero standing fights on instead of dodging until the foes win). Anything refused falls
back toward `end_turn`, so a turn always ends.

Public API: `Plan`, `choose_command`, `foes_of`, `token_of`, `MAX_STEPS`.
"""

import random
from dataclasses import dataclass, field
from typing import Any

from scripts.sim.client import Msg

MAX_STEPS = 8


@dataclass
class Plan:
    """What a bot knows about its own hero when it picks a command."""

    role: str  # fighter | caster | rogue
    hero_id: str
    rng: random.Random
    cantrip: str | None = None
    refused: set[str] = field(default_factory=set[str])
    # M27.10 gear: used once per fight, refused in this fight, kit chances (an ally lay dying).
    fight_used: set[str] = field(default_factory=set[str])
    fight_refused: set[str] = field(default_factory=set[str])
    kit_chances: int = 0


def token_of(combat: Msg, creature_id: str) -> Msg | None:
    return next((t for t in combat["tokens"] if t["creature_id"] == creature_id), None)


def foes_of(combat: Msg, hero_id: str) -> list[Msg]:
    me = token_of(combat, hero_id)
    side = me["side"] if me else "party"
    return [
        t
        for t in combat["tokens"]
        if t["side"] not in (side, "neutral") and not t["dead"] and not t.get("withdrawn")
    ]


def pick_target(plan: Plan, combat: Msg, foes: list[Msg]) -> Msg:
    me = token_of(combat, plan.hero_id)
    zone = me["zone_id"] if me else ""
    near = [f for f in foes if f["zone_id"] == zone] or foes
    if plan.role == "fighter":
        return min(near, key=lambda f: (f["hp"], f["creature_id"]))
    return plan.rng.choice(near)


def _best_in_range(chances: list[Msg]) -> Msg | None:
    usable = [c for c in chances if c.get("in_range", True)]
    return max(usable, key=lambda c: c["probability"]) if usable else None


def _wounded(combat: Msg, plan: Plan) -> bool:
    me = token_of(combat, plan.hero_id)
    return me is not None and me["hp"] * 2 < me["max_hp"]


def _ally_standing(combat: Msg, plan: Plan) -> bool:
    me = token_of(combat, plan.hero_id)
    side = me["side"] if me else "party"
    return any(
        t["side"] == side and t["creature_id"] != plan.hero_id and t["hp"] > 0 and not t["dead"]
        for t in combat["tokens"]
    )


def _cmd(kind: str, plan: Plan, **fields: Any) -> Msg:
    return {"type": kind, "actor_id": plan.hero_id, **fields}


def choose_command(plan: Plan, combat: Msg, chances: list[Msg], target: Msg) -> Msg:
    """The next command for a hero that can still act (see the module docstring)."""
    eco = combat["economy"] or {}
    if not (eco.get("action") or eco.get("attacks_left", 0) > 0):
        return _cmd("end_turn", plan)
    hurt = _wounded(combat, plan) and _ally_standing(combat, plan)
    if plan.role == "rogue" and hurt and "dodge" not in plan.refused:
        plan.refused.add("dodge")  # dodge at most once per turn
        return _cmd("dodge", plan)
    if plan.role == "caster" and plan.cantrip and "cast" not in plan.refused:
        return _cmd("cast", plan, spell_id=plan.cantrip, target_ids=[target["creature_id"]])
    best = _best_in_range(chances)
    if best is not None and "attack" not in plan.refused:
        return _cmd("attack", plan, target_id=target["creature_id"], option=best["option"])
    if eco.get("movement_left", 0) > 0 and "move" not in plan.refused:
        return _cmd("move", plan, zone_id=target["zone_id"])
    if "dash" not in plan.refused:
        return _cmd("dash", plan)
    return _cmd("end_turn", plan)
