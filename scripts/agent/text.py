"""Plain-text views for the playtester: the short `look`, the footer and the message digest.

Pure functions over the public snapshot dicts (`PublicState`) and the messages a command
collected, so they are unit-testable without a server.

Public API: `footer`, `look_text`, `digest`, `foe_list`, `out_of_fight`, `option_lines`,
`level_up_names`, `no_fight_text`, `ascii_text`.
"""

from typing import Any

from aidm.rules.leveling import MAX_LEVEL, level_for_xp
from aidm.rules.offer_answer import PARLEY_SKILLS
from scripts.agent.hero_view import roll_why, zone_lines
from scripts.agent.spells import spell_lines

Msg = dict[str, Any]
PARLEY_WORDS = tuple(str(skill.value) for skill in PARLEY_SKILLS)


_ASCII = {
    "‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-",
    "…": "...", " ": " ",
}  # fmt: skip


def ascii_text(text: str) -> str:
    """Curly quotes and dashes become ASCII for the console (stored events stay untouched)."""
    text = "".join(_ASCII.get(ch, ch) for ch in text)
    return text.encode("ascii", "replace").decode("ascii")


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
    if c.get("light"):
        bits.append(f"(carries a lit {c['light']})")
    return " ".join(bits)


def foe_list(combat: Msg | None, hero_id: str) -> list[Msg]:
    """Every enemy token of the fight, dead and fled ones too, in the server's stable token
    order: foe N stays foe N for the whole fight (M29.5b G23: numbers shifted after a death)."""
    if not combat:
        return []
    me = next((t for t in combat["tokens"] if t["creature_id"] == hero_id), None)
    side = me["side"] if me else "party"
    return [t for t in combat["tokens"] if t["side"] not in (side, "neutral")]


def out_of_fight(token: Msg) -> str | None:
    """Why a foe can no longer be targeted (dead, fled), else None."""
    if token.get("dead"):
        return "dead"
    return "fled" if token.get("withdrawn") else None


def _feature_lines(sheet: Msg | None, eco: Msg) -> tuple[list[str], list[str]]:
    """Class and race feature actions the hotbar offers (`do feature <id>`), and the spent ones."""
    ready: list[str] = []
    spent: list[str] = []
    for f in (sheet or {}).get("feature_actions", []):
        slot = "bonus_action" if f["economy"] == "bonus_action" else "action"
        left = f"{f['uses_left']}/{f['uses_max']} left" if f.get("uses_max") is not None else ""
        label = ", ".join(x for x in (f["economy"].replace("_", " "), left) if x)
        if f["economy"] == "extra_action":
            usable = f["available"]  # M29.7e H9: shown until spent; it works once the action is
            if usable and eco.get("action"):
                label += ", works once your action is used"
        else:
            usable = f["available"] and bool(eco.get(slot))
        if usable:
            aim = "" if f.get("target_kind", "self") == "self" else " [foe#|ally id|zone]"
            ready.append(f"do feature {f['feature']}{aim}   ({f['name']}: {label})")
        else:
            spent.append(f["name"])
    return ready, spent


def _bonus_lines(sheet: Msg | None, eco: Msg) -> list[str]:
    feats = {f.get("index") for f in (sheet or {}).get("features", [])}
    if "cunning-action" not in feats or not eco.get("bonus_action"):
        return []
    return [f"do bonus {v}   (Cunning Action, bonus action)" for v in ("dash", "disengage", "hide")]


def _weapon_lines(sheet: Msg | None) -> list[str]:
    """Z20: the weapons `do attack <foe#> [weapon]` can name (default: the best fit)."""
    atk = (sheet or {}).get("attacks", [])
    if not atk:
        return []
    names = ", ".join(f"{a.get('hand') or a.get('item')}={a.get('name')}" for a in atk)
    return [f"(weapons for do attack <foe#> <weapon>: {names}; default = best fit)"]


def _potion_lines(sheet: Msg | None) -> list[str]:
    """Z19: usable pack items, like the web hotbar's potion buttons (a bonus action)."""
    items = [i for i in (sheet or {}).get("inventory", []) if i.get("category") == "potion"]
    return [
        f"do use {i['item']} [foe#]   ({i.get('name', i['item'])} x{i.get('qty', 1)}, bonus action)"
        for i in items
    ]


def option_lines(combat: Msg | None, hero_id: str, sheet: Msg | None) -> list[str]:
    """The exact `do` / `move` commands a hero can type right now in a fight."""
    if not combat or combat.get("active_id") != hero_id:
        return []
    eco = combat.get("economy") or {}
    can_act = bool(eco.get("action")) or eco.get("attacks_left", 0) > 0
    lines: list[str] = []
    if can_act:
        for n, foe in enumerate(foe_list(combat, hero_id), 1):
            if out_of_fight(foe) is None:
                lines.append(f"do attack {n}   ({foe['name']} {foe['hp']}/{foe['max_hp']})")
    if eco.get("action"):
        lines += ["do dodge", "do dash", "do disengage"]
    else:
        lines.append("(action spent: no attack, dodge, dash or disengage left)")
    features, spent = _feature_lines(sheet, eco)
    lines += features + _bonus_lines(sheet, eco)
    if spent:
        lines.append("(spent or unavailable: " + ", ".join(spent) + ")")
    lines.append("do end")
    lines += _weapon_lines(sheet) + _potion_lines(sheet)
    for use in (sheet or {}).get("gear_uses", []):
        label = f"{use['name']}: {use['label']}, {use['cost']}"
        lines.append(f"do use {use['use_id']} [foe#]   ({label})")
    lines += spell_lines(sheet, combat, eco)
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
    who = f"turn of {turn}" if turn else "no turn started yet"
    out = [f"FIGHT round {combat['round']}; {who}"]
    number = {t["creature_id"]: n for n, t in enumerate(foe_list(combat, hero_id), 1)}
    for t in combat["tokens"]:
        state = "dead" if t["dead"] else f"{t['hp']}/{t['max_hp']}hp"
        foe = t["creature_id"] in number
        if t.get("withdrawn") and not t["dead"]:
            state += " (fled: not a target)" if foe else " (left the fight)"
        where = f"{zones.get(t['zone_id'], '?')} [{t['zone_id']}]"
        tag = f"foe {number[t['creature_id']]}: " if foe else ""
        out.append(f"  {tag}{t['creature_id']} {t['name']} ({t['side']}) {state} in {where}")
    eco = combat.get("economy") or {}
    if combat.get("active_id") == hero_id and eco:
        more = eco.get("attacks_left") or 0
        extra = f" more_attacks={more}" if more > 0 else ""
        out.append(
            f"Your turn: action={eco.get('action')} bonus={eco.get('bonus_action')}"
            f"{extra} move={eco.get('movement_left')}ft"
        )
    return out


def _who(ids: list[str], names: dict[str, str]) -> str:
    return ", ".join(names.get(i, i) for i in ids) or "nobody"


def _vote_line(v: Msg, names: dict[str, str]) -> str:
    ready, declined = list(v.get("ready", [])), list(v.get("declined", []))
    waiting = [i for i in v.get("voters", []) if i not in ready + declined]
    head = f"VOTE {v['vote_id']} ({v['kind']} {v.get('detail', '')})"
    return (
        f"{head}; yes: {_who(ready, names)}; no: {_who(declined, names)}; "
        f"waiting: {_who(waiting, names)}. answer yes|no "
        "(without --as every other hero votes the same)"
    )


def waiting_lines(state: Msg, pending: str | None = None) -> list[str]:
    """Everything that waits for an answer, with the exact `answer` words that resolve it."""
    out: list[str] = []
    names = {c["id"]: c["name"] for c in state.get("party", [])}
    if pending:
        out.append(f"CONFIRM: {pending} answer confirm | cancel")
    if state.get("offer"):
        o = state["offer"]
        foes = ", ".join(o.get("foes", [])) or o.get("boss_name") or "?"
        choices = [str(c) for c in o["options"]]
        extra = f" [{'|'.join(PARLEY_WORDS)}]" if "parley" in choices else ""
        sure = [str(c) for c in o.get("sure", [])]
        hold = f" ({', '.join(sure)} sure to hold)" if sure else ""
        out.append(
            f"OFFER {o['id']}: {foes} ({o.get('difficulty')}). answer {'|'.join(choices)}{hold}"
        )
        if extra:
            out.append(f"  parley takes a skill the engine accepts: answer parley{extra}")
    if state.get("quest_offer"):
        q = state["quest_offer"]
        out.append(f"QUEST OFFER {q['quest_id']} from {q['giver']}: {q['title']}. answer yes|no")
    if state.get("vote"):
        out.append(_vote_line(state["vote"], names))
    if state.get("finale") and state["finale"].get("chosen") is None:
        f = state["finale"]
        opts = " | ".join(f"{o['id']}={o['title']}" for o in f.get("options", []))
        out.append(f"FINALE: {f['question']} answer <id> [confirm]: {opts}")
    if state.get("defeat") or state.get("phase") == "defeated":
        retry = ["retry"] if state.get("checkpoint") else []
        out.append("DEFEAT: answer " + " | ".join(retry + ["load <save id>", "new"]))
    return out


def _waiting(state: Msg, pending: str | None = None) -> list[str]:
    out = [x for x in waiting_lines(state, pending) if not x.startswith("DEFEAT")]
    for q in state.get("quests", []):
        if q.get("state") == "active":
            out.append(f"Quest: {q['title']}: {q.get('objective', '')}")
    return out


def no_fight_text(state: Msg) -> str:
    """Why `do` has nothing to act on (M29.5b G12: after a defeat it said "use act")."""
    if state.get("defeat"):
        retry = "retry | " if state.get("checkpoint") else ""
        return (
            f"The fight is over: the party has fallen. Choose: answer {retry}load <save id> | new"
        )
    return "There is no fight (any fight is over): use act."


def level_up_names(state: Msg, hero_id: str | None = None) -> list[str]:
    """Every standing hero whose XP reached the next level (M29.5b G24: the view flagged only the
    hero whose seat asked; M29.7c R25: a downed hero cannot level up, so it is not offered);
    `hero_id` is one the server already said can level up."""
    out: list[str] = []
    for c in state.get("party", []):
        level, xp = c.get("level"), c.get("xp")
        due = isinstance(level, int) and isinstance(xp, int) and level < MAX_LEVEL
        hp = c.get("hp")  # M29.7c R25: a downed hero cannot level up (the rule), so no offer
        standing = not c.get("dead") and (not isinstance(hp, int) or hp > 0)
        if c["id"] == hero_id or (due and standing and level_for_xp(xp) > level):
            out.append(c["name"])
    known = {c["id"] for c in state.get("party", [])}
    return [hero_id] + out if hero_id is not None and hero_id not in known else out


def look_text(
    state: Msg,
    seq: int,
    hero_id: str,
    sheet: Msg | None = None,
    level_up: bool = False,
    pending: str | None = None,
    extra: list[str] | None = None,
) -> str:
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
        lines += zone_lines(combat)
    lines += _waiting(state, pending)
    if state.get("resolving"):
        lines.append(f"The table is busy with: {state['resolving']['text'][:80]}")
    if state.get("complete") or state.get("epilogue"):
        lines.append("THE CAMPAIGN IS COMPLETE.")
        if state.get("epilogue"):
            lines.append("Ending: " + str(state["epilogue"]).strip())
    if state.get("defeat"):
        lines.append("DEFEAT: " + str(state["defeat"])[:160])
        choices = ["load <save id>", "new"]
        lines.append(
            "Choose: answer " + " | ".join((["retry"] if state.get("checkpoint") else []) + choices)
        )
    ready = level_up_names(state, hero_id if level_up else None)
    if ready:
        lines.append(f"LEVEL UP available for {', '.join(ready)}: run `levelup --as <name>`.")
    lines += extra or []
    options = option_lines(combat, hero_id, sheet)
    if options:
        lines.append("Options:")
        lines += [f"  {o}" for o in options]
    elif combat and combat.get("active_id") not in (None, hero_id):
        names = {t["creature_id"]: t["name"] for t in combat.get("tokens", [])}
        who = names.get(combat["active_id"], combat["active_id"])
        lines += ["Options:", f"  (not your turn: {who} acts; run with --as {who})"]
    else:
        lines.append('What now? act "<text>" | move <place> | answer <choice>')
    lines.append(footer(state["campaign_id"], seq))
    return "\n".join(lines)


def _roll_line(m: Msg) -> str:
    d = m.get("dice") or m
    return roll_why(d).replace("Last roll:", "Roll:") + (
        "" if d.get("target") is None else f" success={d.get('success')}"
    )


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
        elif kind == "pending_confirmation":
            out.append(f"CONFIRM: {m['prompt']} answer confirm | cancel")
        elif kind == "notice":
            out.append(f"Notice: {m['text']}")
        elif kind == "error":
            extra = f" ({m['refusal']})" if m.get("refusal") else ""
            out.append(f"ERROR {m['code']}: {m['text']}{extra}")
        elif kind == "event" and m.get("line"):
            tag = "XP award (milestone or reward): " if m.get("kind") == "xp_gained" else ""
            out.append(f"* {tag}{m['line']}")
        elif kind == "level_up_available":
            out.append(f"LEVEL UP available for {m['creature_id']} (level {m['level']}): levelup")
        elif kind == "what_now_answer":
            out.append("What now? (open steps):\n" + "\n".join(f"  - {x}" for x in m["lines"]))
        elif kind == "epilogue":
            out.append("EPILOGUE reached: " + str(m.get("text", "")).strip())
    if chunks:
        out.append("DM: " + " ".join(chunks).strip()[:700])
    return "\n".join(out)
