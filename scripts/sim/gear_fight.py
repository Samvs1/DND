"""Gear in a fight for the bots (M27.10): pick ONE gear command from the public views, or None.

Pure helpers over the `combat_state`, the public party and the hero's own `gear_uses` (from its
sheet). In priority order, each use at most once per fight once refused:
- a healer's kit: an ally lies dying -> use the kit on them (same zone), else move there;
- light: standing in a dark unlit zone with no light of my own -> light it (bonus action), or
  anywhere when a torch thrown this turn would set oil in a touching zone alight;
- ignite: carrying a lit torch and oil lies in a touching zone where a foe stands -> throw the
  torch into it (the oil burns);
- alchemist's fire: thrown at the target when it is in reach;
- oil: once per fight, thrown into a touching zone where a foe stands, else into the target's
  zone (and only while no oil lies anywhere yet).
Everything else is left to `scripts.sim.combat.choose_command`.

Public API: `gear_command(plan, combat, party, gear, target)`, `gear_key(cmd)`, `COMBAT_ITEM_USES`,
`KIT_USE`.
"""

from scripts.sim.client import Msg
from scripts.sim.combat import Plan, foes_of, token_of

KIT_USE = "healers-kit-stabilize"
COMBAT_ITEM_USES = frozenset(
    {"oil-flask-throw", "alchemists-fire-throw", "torch-throw", "torch-hit", "acid-vial-throw"}
)


def gear_key(cmd: Msg) -> str:
    """What a refusal blocks: one gear use, else the command type (the walk to an ally)."""
    if cmd["type"] == "use_item":
        return f"gear:{cmd.get('use_id') or cmd['item']}"
    return str(cmd["type"])


def _use(plan: Plan, use: Msg, **fields: str) -> Msg:
    return {
        "type": "use_item",
        "actor_id": plan.hero_id,
        "item": use["item"],
        "use_id": use["use_id"],
        **fields,
    }


def _touching(combat: Msg, zone: str) -> set[str]:
    edges = combat.get("edges") or []
    return {e["b"] for e in edges if e["a"] == zone} | {e["a"] for e in edges if e["b"] == zone}


def _zone(combat: Msg, zone_id: str) -> Msg:
    return next((z for z in combat.get("zones", []) if z["id"] == zone_id), {})


def _has_oil(zone: Msg) -> bool:
    return any(s["kind"] == "oil" for s in zone.get("surfaces", []))


def _foe_zones(combat: Msg, plan: Plan) -> set[str]:
    return {f["zone_id"] for f in foes_of(combat, plan.hero_id)}


def _kit(plan: Plan, combat: Msg, party: list[Msg], uses: dict[str, Msg], me: Msg) -> Msg | None:
    use = uses.get(KIT_USE)
    down = [
        p
        for p in party
        if p["id"] != plan.hero_id and p.get("dying") and not p.get("stable") and not p["dead"]
    ]
    ally = token_of(combat, down[0]["id"]) if down and use is not None else None
    if use is None or ally is None:
        return None
    plan.kit_chances += 1
    eco = combat["economy"] or {}
    if ally["zone_id"] == me["zone_id"]:
        return _use(plan, use, target_id=ally["creature_id"]) if eco.get("action") else None
    if eco.get("movement_left", 0) > 0:
        return {"type": "move", "actor_id": plan.hero_id, "zone_id": ally["zone_id"]}
    return None


def _oily_foe_zones(combat: Msg, plan: Plan, me: Msg) -> list[str]:
    near = _touching(combat, me["zone_id"]) & _foe_zones(combat, plan)
    return sorted(z for z in near if _has_oil(_zone(combat, z)))


def _light(plan: Plan, combat: Msg, mine: Msg, uses: dict[str, Msg], me: Msg) -> Msg | None:
    """Light up in a dark unlit zone, or anywhere a torch would set touching oil alight."""
    eco = combat["economy"] or {}
    zone = _zone(combat, me["zone_id"])
    dark = bool(zone.get("dark")) and not zone.get("lit", True)
    if mine.get("light") or not eco.get("bonus_action"):
        return None
    if dark:
        use = next((u for u in uses.values() if u.get("effect") == "light_place"), None)
    else:
        ready = "torch-light" in uses and eco.get("action") and _oily_foe_zones(combat, plan, me)
        use = uses.get("torch-light") if ready else None
    return _use(plan, use) if use is not None else None


def _ignite(plan: Plan, combat: Msg, mine: Msg, uses: dict[str, Msg], me: Msg) -> Msg | None:
    use = uses.get("torch-throw")
    if use is None or mine.get("light") != "Torch":
        return None
    oily = _oily_foe_zones(combat, plan, me)
    return _use(plan, use, target_zone=oily[0]) if oily else None


def _thrown(plan: Plan, combat: Msg, uses: dict[str, Msg], me: Msg, target: Msg) -> Msg | None:
    fire = uses.get("alchemists-fire-throw")
    reach = {me["zone_id"], *_touching(combat, me["zone_id"])}
    if fire is not None and target["zone_id"] in reach:
        return _use(plan, fire, target_id=target["creature_id"])
    oil = uses.get("oil-flask-throw")
    if oil is None or "oil" in plan.fight_used:
        return None
    if any(_has_oil(z) for z in combat.get("zones", [])):
        return None
    near = sorted(_touching(combat, me["zone_id"]) & _foe_zones(combat, plan))
    plan.fight_used.add("oil")
    return _use(plan, oil, target_zone=near[0] if near else target["zone_id"])


def gear_command(
    plan: Plan, combat: Msg, party: list[Msg], gear: list[Msg], target: Msg
) -> Msg | None:
    """The gear command to send now (see the module docstring), or None."""
    me = token_of(combat, plan.hero_id)
    mine = next((p for p in party if p["id"] == plan.hero_id), None)
    if me is None or mine is None:
        return None
    uses = {g["use_id"]: g for g in gear}
    picks = (
        _kit(plan, combat, party, uses, me),
        _light(plan, combat, mine, uses, me),
        _ignite(plan, combat, mine, uses, me) if (combat["economy"] or {}).get("action") else None,
    )
    for cmd in picks:
        if cmd is not None and gear_key(cmd) not in plan.refused | plan.fight_refused:
            return cmd
    if not (combat["economy"] or {}).get("action"):
        return None
    cmd = _thrown(plan, combat, uses, me, target)
    blocked = cmd is not None and gear_key(cmd) in plan.refused | plan.fight_refused
    return None if blocked else cmd
