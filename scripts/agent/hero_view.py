"""What `look` shows beyond the basics (M29.7e H11, H14): zone cover, light, surfaces, the last
roll's advantage reasons, each hero's slots, spells, camp supplies and what a level-up taught.

Pure functions over the public state and sheet dicts (only what the server sends a client).

Public API: `zone_lines`, `roll_why`, `hero_lines`, `learned`, `supplies_line`.
"""

from typing import Any

Msg = dict[str, Any]
_COVER = {"half": "half cover", "three_quarters": "three-quarters cover", "full": "full cover"}


def _zone_bits(z: Msg) -> list[str]:
    bits: list[str] = []
    cover = _COVER.get(str(z.get("cover", "none")))
    if cover:
        bits.append(cover)
    if z.get("high_ground"):
        bits.append("high ground")
    if z.get("rough"):
        bits.append("rough ground")
    if z.get("dark") and not z.get("lit", True):
        bits.append("dark")
    elif z.get("lit_by"):
        bits.append("lit by " + ", ".join(z["lit_by"]))
    for s in z.get("surfaces", []):
        left = f" {s['rounds_left']}r" if s.get("rounds_left") else ""
        bits.append(f"surface {s['kind']}{left}")
    return bits


def zone_lines(combat: Msg | None) -> list[str]:
    """One line per zone with cover, high ground, light and surfaces (oil, ball bearings...)."""
    out: list[str] = []
    for z in (combat or {}).get("zones", []):
        bits = _zone_bits(z)
        if bits:
            out.append(f"  zone {z['id']} {z['name']}: " + ", ".join(bits))
    return ["Zone features:", *out] if out else []


def roll_why(dice: Msg | None) -> str:
    """The last roll with its advantage or disadvantage and the reasons (`adv_why`)."""
    if not dice:
        return ""
    adv = str(dice.get("adv", "normal"))
    why = ", ".join(dice.get("adv_why", []))
    tail = f" ({adv}: {why})" if why else (f" ({adv})" if adv != "normal" else "")
    target = f" vs {dice['target']}" if dice.get("target") is not None else ""
    return f"Last roll: {dice.get('label', '')} {dice.get('total')}{target}{tail}"


def supplies_line(state: Msg) -> str:
    return f"Camp supplies: {state.get('camp_supplies', 0)}"


def _slots(sheet: Msg) -> str:
    casting = sheet.get("spellcasting") or {}
    parts = [
        f"L{g['level']} " + "+".join(f"{s['current']}/{s['maximum']}" for s in g["slots"])
        for g in casting.get("levels", [])
        if g.get("slots")
    ]
    return ", ".join(parts)


def _spell_names(sheet: Msg) -> list[str]:
    casting = sheet.get("spellcasting") or {}
    names = [f"{s['index']} (cantrip)" for s in casting.get("cantrips", [])]
    for g in casting.get("levels", []):
        for s in g.get("spells", []):
            if s.get("prepared") or s.get("always_prepared"):
                names.append(f"{s['index']} (L{g['level']})")
    return names


def hero_lines(sheet: Msg, in_fight: bool) -> list[str]:
    """Slots, the spell list (out of a fight; the fight's Options list them) and resources."""
    out = [f"  {sheet['name']}: L{sheet['level']} {sheet['class_index']}"]
    slots = _slots(sheet)
    if slots:
        out[0] += f" | slots {slots}"
    if not in_fight and (names := _spell_names(sheet)):
        out.append("    spells: " + ", ".join(names))
    res = [f"{r['key']} {r['current']}/{r['maximum']}" for r in sheet.get("resources", [])]
    if res:
        out.append("    resources: " + ", ".join(res))
    return out


def _gained(before: list[str], after: list[str]) -> list[str]:
    return [x for x in after if x not in before]


def learned(before: Msg | None, after: Msg | None) -> str:
    """What a level-up taught: the features and spells the sheet has now and did not have."""
    if not before or not after:
        return ""
    feats = _gained([f["name"] for f in before["features"]], [f["name"] for f in after["features"]])
    spells = _gained(_spell_names(before), _spell_names(after))
    bits = [f"now level {after['level']}", f"hp {before['max_hp']} -> {after['max_hp']}"]
    if feats:
        bits.append("features: " + ", ".join(feats))
    if spells:
        bits.append("spells: " + ", ".join(spells))
    return "Level-up taught: " + "; ".join(bits)
