"""Plain-text views for the playtester: the short `look`, the footer and the message digest.

Pure functions over the public snapshot dicts (`PublicState`) and the messages a command
collected, so they are unit-testable without a server.

Public API: `footer`, `look_text`, `digest`, `foe_list`, `option_lines`.
"""

from typing import Any

Msg = dict[str, Any]


def footer(campaign_id: str, seq: int) -> str:
    return f"[save {campaign_id} | event {seq}]"


def _hp(c: Msg) -> str:
    bits = [f"{c['name']} {c['hp']}/{c['max_hp']}hp ac{c.get('ac', '?')}"]
    if c.get("level"):
        bits.append(f"L{c['level']} {c.get('class_index') or ''}".rstrip())
    if c.get("gold") is not None:
        bits.append(f"{c['gold']}gp")
    if c.get("dead"):
        bits.append("DEAD")
    elif c.get("dying"):
        bits.append("DYING")
    if c.get("conditions"):
        bits.append("[" + ",".join(c["conditions"]) + "]")
    return " ".join(bits)


def foe_list(combat: Msg | None, hero_id: str) -> list[Msg]:
    """The living enemy tokens in a stable order (the numbers `do attack 1` refers to)."""
    if not combat:
        return []
    me = next((t for t in combat["tokens"] if t["creature_id"] == hero_id), None)
    side = me["side"] if me else "party"
    return [
        t
        for t in combat["tokens"]
        if t["side"] not in (side, "neutral") and not t["dead"] and not t.get("withdrawn")
    ]


def _spell_lines(sheet: Msg | None) -> list[str]:
    out: list[str] = []
    casting = (sheet or {}).get("spellcasting") or {}
    for group in casting.get("levels", []):
        for sp in group.get("spells", []):
            ready = sp.get("prepared") or sp.get("always_prepared") or group["level"] == 0
            if ready:
                out.append(f"do cast {sp['index']} [foe#]   (level {group['level']})")
    return out


def option_lines(combat: Msg | None, hero_id: str, sheet: Msg | None) -> list[str]:
    """The exact `do` / `move` commands a hero can type right now in a fight."""
    if not combat or combat.get("active_id") != hero_id:
        return []
    eco = combat.get("economy") or {}
    lines: list[str] = []
    for n, foe in enumerate(foe_list(combat, hero_id), 1):
        hp = f"{foe['hp']}/{foe['max_hp']}"
        lines.append(f"do attack {n}   ({foe['name']} {hp})")
    lines += ["do dodge", "do dash", "do disengage", "do end"]
    for use in (sheet or {}).get("gear_uses", []):
        label = f"{use['name']}: {use['label']}, {use['cost']}"
        lines.append(f"do use {use['use_id']} [foe#]   ({label})")
    lines += _spell_lines(sheet)
    if eco.get("movement_left", 0) > 0:
        lines.append(f"move <zone>   ({eco['movement_left']}ft left)")
    return lines


def _scene(scene: Msg) -> list[str]:
    out = [f"Place: {scene['name']}" + (" (dark)" if scene.get("dark") else "")]
    if scene.get("description"):
        out.append(f"  {scene['description'][:220]}")
    if scene.get("npcs"):
        out.append("People: " + ", ".join(n["name"] for n in scene["npcs"]))
    if scene.get("features"):
        out.append("Things: " + ", ".join(f["name"] for f in scene["features"]))
    if scene.get("items"):
        out.append("On the ground: " + ", ".join(scene["items"]))
    if scene.get("shopkeepers"):
        out.append("Shops: " + ", ".join(scene["shopkeepers"]))
    exits = [
        e["name"]
        + (" (locked)" if e.get("locked") else "")
        + (" (seen)" if e.get("visited") else "")
        for e in scene.get("exits", [])
    ]
    out.append("Exits: " + (", ".join(exits) or "none"))
    return out


def _combat(combat: Msg, hero_id: str) -> list[str]:
    zones = {z["id"]: z["name"] for z in combat.get("zones", [])}
    turn = combat.get("turn_of") or combat.get("active_id")
    out = [f"FIGHT round {combat['round']}; turn of {turn}"]
    for t in combat["tokens"]:
        state = "dead" if t["dead"] else f"{t['hp']}/{t['max_hp']}hp"
        where = f"{zones.get(t['zone_id'], '?')} [{t['zone_id']}]"
        out.append(f"  {t['creature_id']} {t['name']} ({t['side']}) {state} in {where}")
    eco = combat.get("economy") or {}
    if combat.get("active_id") == hero_id and eco:
        out.append(
            f"Your turn: action={eco.get('action')} bonus={eco.get('bonus_action')} "
            f"attacks_left={eco.get('attacks_left')} move={eco.get('movement_left')}ft"
        )
    return out


def _waiting(state: Msg) -> list[str]:
    out: list[str] = []
    if state.get("offer"):
        o = state["offer"]
        foes = ", ".join(o.get("foes", [])) or "?"
        choices = "|".join(o["options"])
        out.append(f"OFFER {o['id']}: {foes} ({o.get('difficulty')}). answer {choices}")
    if state.get("quest_offer"):
        q = state["quest_offer"]
        out.append(f"QUEST OFFER {q['quest_id']} from {q['giver']}: {q['title']}. answer yes|no")
    if state.get("vote"):
        v = state["vote"]
        out.append(f"VOTE {v['vote_id']} ({v['kind']} {v.get('detail', '')}). answer yes|no")
    if state.get("finale") and state["finale"].get("chosen") is None:
        f = state["finale"]
        opts = " | ".join(f"{o['id']}={o['title']}" for o in f.get("options", []))
        out.append(f"FINALE: {f['question']} answer <id>: {opts}")
    for q in state.get("quests", []):
        if q.get("state") == "active":
            out.append(f"Quest: {q['title']}: {q.get('objective', '')}")
    return out


def look_text(state: Msg, seq: int, hero_id: str, sheet: Msg | None = None) -> str:
    """The whole short view: place, party, fight, what waits for an answer, options, footer."""
    title = state.get("campaign_title") or "campaign"
    lines = [f"== {title} | phase {state['phase']} | tier {state.get('region_tier', 1)} =="]
    if state.get("scene"):
        lines += _scene(state["scene"])
    lines.append("Party:")
    lines += [f"  {c['id']}: {_hp(c)}" for c in state.get("party", [])]
    combat = state.get("combat")
    if combat:
        lines += _combat(combat, hero_id)
    lines += _waiting(state)
    if state.get("resolving"):
        lines.append(f"The table is busy with: {state['resolving']['text'][:80]}")
    if state.get("complete") or state.get("epilogue"):
        lines.append("THE CAMPAIGN IS COMPLETE.")
    if state.get("defeat"):
        lines.append("DEFEAT: " + str(state["defeat"])[:160])
    options = option_lines(combat, hero_id, sheet)
    if options:
        lines.append("Options:")
        lines += [f"  {o}" for o in options]
    else:
        lines.append('What now? act "<text>" | move <place> | answer <choice>')
    lines.append(footer(state["campaign_id"], seq))
    return "\n".join(lines)


def _roll_line(m: Msg) -> str:
    d = m.get("dice") or m
    label, total = d.get("label", ""), d.get("total")
    if d.get("target") is None:
        return f"Roll: {label} {total}"
    return f"Roll: {label} {total} vs {d['target']} success={d.get('success')}"


def digest(messages: list[Msg]) -> str:
    """What happened since a command: narration, rolls, notices, errors (short, no raw JSON)."""
    out: list[str] = []
    chunks: list[str] = []
    for m in messages:
        kind = m["type"]
        if kind == "narration_chunk":
            chunks.append(m["text"])
        elif kind == "narration_done" and chunks:
            out.append("DM: " + " ".join(chunks).strip()[:700])
            chunks = []
        elif kind == "dice_roll":
            out.append(_roll_line(m))
        elif kind == "notice":
            out.append(f"Notice: {m['text']}")
        elif kind == "error":
            extra = f" ({m['refusal']})" if m.get("refusal") else ""
            out.append(f"ERROR {m['code']}: {m['text']}{extra}")
        elif kind == "event" and m.get("line"):
            out.append(f"* {m['line']}")
        elif kind == "epilogue":
            out.append("EPILOGUE reached.")
    if chunks:
        out.append("DM: " + " ".join(chunks).strip()[:700])
    return "\n".join(out)
