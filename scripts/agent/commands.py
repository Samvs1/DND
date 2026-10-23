"""Turn what the playtester typed into protocol messages (pure, no network).

`do` words become a combat command for the acting hero; targets are the numbers `look` prints
for foes (or a creature id). `attack` leaves `option` unset: the link asks the server for the
hit chances and takes the best one, like a player pressing the strike button.

Public API: `UsageError`, `build_command`, `answer_message`, `target_of`.
"""

from typing import Any

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


def target_of(word: str, foes: list[Msg]) -> str:
    """A foe number from `look` (1-based) or a creature id."""
    if word.isdigit():
        number = int(word)
        if not 1 <= number <= len(foes):
            raise UsageError(f"there is no foe number {number} (foes: 1..{len(foes)})")
        return str(foes[number - 1]["creature_id"])
    return word


def build_command(words: list[str], hero_id: str, foes: list[Msg], sheet: Msg | None) -> Msg:
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
        if not rest:
            raise UsageError("do cast <spell id> [foe#]")
        targets = [target_of(rest[1], foes)] if len(rest) > 1 else []
        return {"type": "cast", **base, "spell_id": rest[0], "target_ids": targets}
    if verb == "use":
        return _use(rest, base, foes, sheet)
    raise UsageError(
        f"unknown action {verb!r}: attack, cast, use, dodge, dash, disengage, hide, flee, end"
    )


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


def answer_message(state: Msg, words: list[str]) -> list[Msg]:
    """The message(s) that answer whatever waits in `state` (offer, quest offer, finale, vote).

    A confirm of a hostile act is `answer confirm` / `answer cancel`; a level-up is not here.
    """
    if not words:
        raise UsageError("answer <choice>: see what waits in `look`")
    choice = words[0].lower()
    if choice in ("confirm", "cancel"):
        return [{"type": "confirm_hostile" if choice == "confirm" else "cancel_hostile"}]
    if state.get("offer"):
        options = [str(o) for o in state["offer"].get("options", [])]
        if choice not in options:
            raise UsageError(f"answer one of: {', '.join(options)}")
        msg: Msg = {"type": "answer_offer", "choice": choice}
        if len(words) > 1:
            msg["skill"] = words[1].lower()
        return [msg]
    if state.get("quest_offer"):
        return [_yes_no("answer_quest_offer", choice, quest_id=state["quest_offer"]["quest_id"])]
    if state.get("finale") and state["finale"].get("chosen") is None:
        confirm = len(words) > 1 and words[1].lower() == "confirm"
        return [{"type": "choose_finale", "option_id": words[0], "confirm": confirm}]
    if state.get("vote"):
        return [_yes_no("vote", choice, vote_id=state["vote"]["vote_id"])]
    raise UsageError("nothing is waiting for an answer")


def _yes_no(kind: str, choice: str, **fields: str) -> Msg:
    if choice not in YES | NO:
        raise UsageError("answer yes or no")
    key = "ready" if kind == "vote" else "accept"
    return {"type": kind, **fields, key: choice in YES}
