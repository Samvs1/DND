"""Turn what the playtester typed into protocol messages (pure, no network).

`do` words become a combat command for the acting hero; targets are the numbers `look` prints
for foes (or a creature id). `attack` leaves `option` unset: the link asks the server for the
hit chances and takes the best one, like a player pressing the strike button.

Public API: `UsageError`, `build_command`, `answer_message`, `target_of`.
"""

from typing import Any

from scripts.agent.spells import find_spell, needs_creature, needs_zone
from scripts.agent.text import PARLEY_WORDS, out_of_fight, waiting_lines

Msg = dict[str, Any]

SIMPLE = {
    "dodge": "dodge",
    "dash": "dash",
    "disengage": "disengage",
    "hide": "hide",
    "flee": "flee",
    "end": "end_turn",
    "end_turn": "end_turn",
}
YES = {"yes", "y", "accept", "ready", "true", "ok"}
NO = {"no", "n", "decline", "not-ready", "false"}


class UsageError(Exception):
    """A mistyped command: the message says how to fix it (shown to the tester)."""


def target_of(word: str, foes: list[Msg], tokens: list[Msg] | None = None) -> str:
    """A foe number from `look` (1-based), a creature id or a creature's name."""
    if word.isdigit():
        number = int(word)
        if not 1 <= number <= len(foes):
            raise UsageError(f"there is no foe number {number} (foes: 1..{len(foes)})")
        foe = foes[number - 1]
        gone = out_of_fight(foe)
        if gone is not None:
            raise UsageError(f"foe {number} ({foe['name']}) is {gone}: not a target")
        return str(foe["creature_id"])
    for token in tokens or []:
        if word.lower() in (str(token["creature_id"]).lower(), str(token["name"]).lower()):
            return str(token["creature_id"])
    return word


def build_command(
    words: list[str],
    hero_id: str,
    foes: list[Msg],
    sheet: Msg | None,
    combat: Msg | None = None,
) -> Msg:
    if not words:
        raise UsageError("do what? try: do attack 1 | do dodge | do end | do cast <spell> [foe#]")
    verb, rest = words[0].lower(), words[1:]
    base: Msg = {"actor_id": hero_id}
    if verb in SIMPLE:
        return {"type": SIMPLE[verb], **base}
    if verb == "attack":
        if not rest:
            raise UsageError("do attack <foe#>")
        return {"type": "attack", **base, "target_id": target_of(rest[0], foes), "option": ""}
    if verb == "move":
        if not rest:
            raise UsageError("move <zone id>")
        return {"type": "move", **base, "zone_id": rest[0]}
    if verb == "help":
        if not rest:
            raise UsageError("do help <ally creature id>")
        return {"type": "help", **base, "target_id": rest[0]}
    if verb == "cast":
        return _cast(rest, base, foes, sheet, combat or {})
    if verb == "use":
        return _use(rest, base, foes, sheet)
    if verb == "feature":
        return _feature(rest, base, foes, sheet)
    if verb == "bonus":
        if not rest or rest[0] not in ("dash", "disengage", "hide"):
            raise UsageError("do bonus dash|disengage|hide (Cunning Action)")
        return {"type": rest[0], **base, "bonus_action": True}
    raise UsageError(
        f"unknown action {verb!r}: attack, cast, use, feature, bonus, dodge, dash, disengage, "
        "hide, flee, end"
    )


def _zone_of(word: str, combat: Msg) -> str:
    zones = combat.get("zones", [])
    for z in zones:
        if word.lower() in (str(z["id"]).lower(), str(z["name"]).lower()):
            return str(z["id"])
    names = ", ".join(f"{z['id']}={z['name']}" for z in zones)
    raise UsageError(f"there is no zone {word!r} (zones: {names or 'none'})")


def _cast(rest: list[str], base: Msg, foes: list[Msg], sheet: Msg | None, combat: Msg) -> Msg:
    if not rest:
        raise UsageError("do cast <spell id> [foe#|ally|zone]")
    cmd: Msg = {"type": "cast", **base, "spell_id": rest[0], "target_ids": []}
    spell = find_spell(sheet, rest[0])
    tokens = combat.get("tokens", [])
    if spell is not None and needs_zone(spell):
        if len(rest) < 2:
            raise UsageError(f"{rest[0]} needs a zone: do cast {rest[0]} <zone id|name>")
        return {**cmd, "target_ids": [], "target_zone": _zone_of(rest[1], combat)}
    if spell is not None and not needs_creature(spell):
        return cmd
    if len(rest) > 1:
        cmd["target_ids"] = [target_of(w, foes, tokens) for w in rest[1:]]
    return cmd


def _feature(rest: list[str], base: Msg, foes: list[Msg], sheet: Msg | None) -> Msg:
    feats = {f["feature"]: f for f in (sheet or {}).get("feature_actions", [])}
    near = [k for k in feats if rest and k.startswith(rest[0] + "-")]
    if rest and rest[0] not in feats and len(near) == 1:
        rest = [near[0], *rest[1:]]  # M32.1d: a short id (`action-surge`) names the one full id
    if not rest or rest[0] not in feats:
        raise UsageError(f"do feature <id> [target] (yours: {', '.join(sorted(feats)) or 'none'})")
    kind = feats[rest[0]].get("target_kind", "self")
    cmd: Msg = {"type": "feature_action", **base, "feature_id": rest[0]}
    if len(rest) > 1 and kind in ("area", "point"):
        cmd["target_zone"] = rest[1]
    elif len(rest) > 1 and kind != "self":
        cmd["target_ids"] = [target_of(rest[1], foes)]
    return cmd


def _use(rest: list[str], base: Msg, foes: list[Msg], sheet: Msg | None) -> Msg:
    if not rest:
        raise UsageError("do use <use id> [foe#]")
    uses = {u["use_id"]: u for u in (sheet or {}).get("gear_uses", [])}
    use = uses.get(rest[0])
    if use is None:
        raise UsageError(
            f"you have no use {rest[0]!r} (yours: {', '.join(sorted(uses)) or 'none'})"
        )
    cmd: Msg = {"type": "use_item", **base, "item": use["item"], "use_id": use["use_id"]}
    if len(rest) > 1:
        cmd["target_id"] = target_of(rest[1], foes)
    return cmd


def _parley_skill(choice: str, skill: str) -> str:
    if choice != "parley":
        raise UsageError(f"only parley takes a skill: answer parley [{'|'.join(PARLEY_WORDS)}]")
    if skill not in PARLEY_WORDS:
        raise UsageError(f"parley uses {' or '.join(PARLEY_WORDS)}, not {skill!r}")
    return skill


def answer_message(state: Msg, words: list[str], pending: str | None = None) -> list[Msg]:
    """The message(s) that answer whatever waits in `state` (offer, quest offer, finale, vote).

    A confirm of a hostile act is `answer confirm` / `answer cancel`; a level-up is not here.
    """
    if not words:
        raise UsageError(
            f"answer <choice>. Waiting now: {'; '.join(waiting_lines(state, pending)) or 'nothing'}"
        )
    choice = words[0].lower()
    if state.get("defeat") or state.get("phase") == "defeated":
        return [_defeat(state, choice, words)]
    if choice in ("confirm", "cancel"):
        return [{"type": "confirm_hostile" if choice == "confirm" else "cancel_hostile"}]
    if state.get("offer"):
        options = [str(o) for o in state["offer"].get("options", [])]
        if choice not in options:
            raise UsageError(f"answer one of: {', '.join(options)}")
        msg: Msg = {"type": "answer_offer", "choice": choice}
        if len(words) > 1:
            msg["skill"] = _parley_skill(choice, words[1].lower())
        return [msg]
    if state.get("quest_offer"):
        return [_yes_no("answer_quest_offer", choice, quest_id=state["quest_offer"]["quest_id"])]
    if state.get("finale") and state["finale"].get("chosen") is None:
        return [_finale(state["finale"], words)]
    if state.get("vote"):
        return [_yes_no("vote", choice, vote_id=state["vote"]["vote_id"])]
    waiting = waiting_lines(state, pending)
    if not waiting:
        raise UsageError("nothing is waiting for an answer")
    raise UsageError(f"that answer fits no waiting card. Waiting now: {'; '.join(waiting)}")


def _finale(finale: Msg, words: list[str]) -> Msg:
    """`answer <id> [confirm]` or `answer finale [<id>]` (the kind word means confirm; with one
    option the id may be left out)."""
    named = words[0].lower() == "finale"
    rest = words[1:] if named else words
    ids = [str(o["id"]) for o in finale.get("options", [])]
    option = rest[0] if rest else (ids[0] if len(ids) == 1 else "")
    if not option:
        raise UsageError(f"answer finale <id>. Options: {', '.join(ids)}")
    confirm = named or (len(rest) > 1 and rest[1].lower() == "confirm")
    return {"type": "choose_finale", "option_id": option, "confirm": confirm}


def _defeat(state: Msg, choice: str, words: list[str]) -> Msg:
    """The defeat screen's three choices: retry, load <save id> (default: this save), new."""
    if choice == "retry":
        return {"type": "defeat_retry"}
    if choice == "new":
        return {"type": "defeat_new"}
    if choice == "load":
        return {
            "type": "defeat_load",
            "campaign_id": words[1] if len(words) > 1 else state["campaign_id"],
        }
    raise UsageError("the party has fallen: answer retry | load <save id> | new")


def _yes_no(kind: str, choice: str, **fields: str) -> Msg:
    if choice not in YES | NO:
        raise UsageError("answer yes or no")
    key = "ready" if kind == "vote" else "accept"
    return {"type": kind, **fields, key: choice in YES}
