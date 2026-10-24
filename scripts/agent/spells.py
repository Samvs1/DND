"""The spells a hero can cast right now, as the playtester sees them (pure, no network).

The sheet's `spellcasting` block lists cantrips apart from the levelled spells; the hotbar of
the real client shows both, so the harness does too. A spell needs a zone when its
`target_kind` is `area` (unless it is centred on the caster with no aimed shape) or `point`;
an aimed self cone or line (`area_shape`/`area_feet`, M29.7d) takes the zone it is aimed at,
the caster's own or a neighbour within its length; the `(zones: ...)` list marks the
ones in reach (edge feet from the combat message, summed along the shortest path).
Creature spells take foes or allies.

Public API: `find_spell`, `spell_lines`, `needs_zone`, `needs_creature`.
"""

from typing import Any

Msg = dict[str, Any]


def _ready(sheet: Msg | None) -> list[Msg]:
    casting = (sheet or {}).get("spellcasting") or {}
    out = [{**sp, "level": 0} for sp in casting.get("cantrips", [])]
    for group in casting.get("levels", []):
        for sp in group.get("spells", []):
            if sp.get("prepared") or sp.get("always_prepared") or group["level"] == 0:
                out.append({**sp, "level": group["level"]})
    return out


def find_spell(sheet: Msg | None, index: str) -> Msg | None:
    return next((sp for sp in _ready(sheet) if sp["index"] == index), None)


def needs_zone(spell: Msg) -> bool:
    kind = spell.get("target_kind", "creature")
    if kind == "point":
        return True
    return kind == "area" and (spell.get("range_kind") != "self" or bool(spell.get("area_feet")))


def needs_creature(spell: Msg) -> bool:
    return spell.get("target_kind", "creature") in ("creature", "creatures")


def _slots_left(sheet: Msg | None, level: int) -> int:
    casting = (sheet or {}).get("spellcasting") or {}
    return sum(
        s["current"]
        for g in casting.get("levels", [])
        if g["level"] >= level
        for s in g.get("slots", [])
    )


def _resource_left(sheet: Msg | None, key: str) -> int:
    """Uses left of the feature resource a spell is cast from (`SpellLine.resource`)."""
    return sum(r["current"] for r in (sheet or {}).get("resources", []) if r["key"] == key)


def _blocked(spell: Msg, sheet: Msg | None, eco: Msg) -> str:
    """Why the spell cannot be cast now ("" when it can)."""
    time = spell.get("casting_time", "action")
    if time == "action" and not eco.get("action"):
        return "no action left"
    if time == "bonus_action" and not eco.get("bonus_action"):
        return "no bonus action left"
    if spell["level"] > 0 and _slots_left(sheet, spell["level"]) <= 0:
        if spell.get("resource"):
            return "" if _resource_left(sheet, spell["resource"]) > 0 else "no uses left"
        return "no slot left"
    return ""


def _aim(spell: Msg) -> str:
    if needs_zone(spell) and spell.get("area_feet") and spell.get("range_kind") == "self":
        shape = spell.get("area_shape") or "area"
        return f" <zone id|name> ({spell['area_feet']}-ft {shape} from your zone)"
    if needs_zone(spell):
        return " <zone id|name>"
    if needs_creature(spell):
        return " <foe#|ally id|ally name>"
    return ""


def _reach(combat: Msg, feet: int) -> set[str]:
    """Zones within `feet` of the caster's zone by summed edge lengths (the combat message's
    `edges`); with no edges, only the caster's own zone. Dijkstra over a handful of zones."""
    me = next((t for t in combat["tokens"] if t["creature_id"] == combat.get("active_id")), None)
    if me is None:
        return set()
    dist = {me["zone_id"]: 0}
    todo = [me["zone_id"]]
    while todo:
        here = todo.pop()
        for e in combat.get("edges", []):
            for a, b in ((e["a"], e["b"]), (e["b"], e["a"])):
                step = dist[here] + e.get("feet", 30)
                if a == here and step <= feet and step < dist.get(b, feet + 1):
                    dist[b] = step
                    todo.append(b)
    return set(dist)


def _cone_reach(shown: list[Msg], combat: Msg) -> set[str]:
    """Zones an aimed self cone or line can reach (the longest shown one); empty if none."""
    feet = [
        sp["area_feet"]
        for sp in shown
        if sp.get("area_feet") and sp.get("range_kind") == "self" and needs_zone(sp)
    ]
    return _reach(combat, max(feet)) if feet else set()


def spell_lines(sheet: Msg | None, combat: Msg, eco: Msg) -> list[str]:
    """`do cast ...` lines for the spells castable now, the blocked ones in one note, then
    the ally ids and zone names the targets are taken from."""
    lines: list[str] = []
    blocked: list[str] = []
    shown: list[Msg] = []
    for sp in _ready(sheet):
        why = _blocked(sp, sheet, eco)
        if why:
            blocked.append(f"{sp['index']} ({why})")
            continue
        shown.append(sp)
        tier = "cantrip" if sp["level"] == 0 else f"level {sp['level']}"
        lines.append(f"do cast {sp['index']}{_aim(sp)}   ({tier})")
    if blocked:
        lines.append("(cannot cast now: " + ", ".join(blocked) + ")")
    if any(needs_creature(sp) for sp in shown):
        allies = [t for t in combat["tokens"] if t["side"] == "party" and not t["dead"]]
        lines.append(
            "(allies: " + ", ".join(f"{t['creature_id']}={t['name']}" for t in allies) + ")"
        )
    if any(needs_zone(sp) for sp in shown):
        reach = _cone_reach(shown, combat)
        zones = ", ".join(
            f"{z['id']}={z['name']}" + (" [in reach]" if z["id"] in reach else "")
            for z in combat.get("zones", [])
        )
        lines.append(f"(zones: {zones})")
    return lines
