"""Typed paying of an NPC (M29.9a T17: "Brienne pays Rutter the Gap for a crossing" was told as
paid with no coin moving, and "Brienne hands Rutter the Gap 1 gold piece" was refused as a thing
not carried). A deterministic precheck like `aidm.dm.give_intent`.

`pay_intent(state, actor_id, clean)` reads the precheck's normalised sentence (the hero's own
name with a third-person verb reads the same; the first clause is the payment and the rest, if
any, is another act told with it, `PayIntent.rest`):
- "pay <who> [<money>] [for ...]", "pay <money> to <who> [for ...]";
- "<give|hand|toss|slip|offer|pass> <who> <money> [for ...]", "<verb> <money> to <who> ...",
  "count out <money> for <who>";
- `money` is "[n|a|an|one..ten|some] <gold|silver|copper|gp|sp|cp|coin|coins> [pieces|coins]";
  silver and copper round up to whole gold as the shop does (`rules.paying.gold_for`), a coin
  of no metal is gold, and no amount is 1. "Pay Rutter for a crossing" with no money pays what
  an open `pay` step asks of that NPC, else 1 gold (DECISIONS M29.9a);
- `who` is a known NPC (`give_intent.named_npc`, a present one first); naming a hero is the
  hero hand-over (`aidm.dm.hand_intent`), not this.
None when no NPC is named. The rules decide (`aidm.rules.paying.pay_events`).

Public API: `PayIntent(actor_id, npc_id, gold, rest)`, `pay_intent(state, actor_id, clean)`.
"""

import re
from dataclasses import dataclass

from aidm.dm.give_intent import named_npc
from aidm.dm.sentence import split_clause
from aidm.models.quests import StepKind
from aidm.models.state import CreatureKind, GameState
from aidm.models.world import QuestState
from aidm.rules.paying import gold_for

_AMOUNT = r"(?P<n>\d+|an?|one|two|three|four|five|six|seven|eight|nine|ten|some|a few)"
_MONEY = (
    rf"(?:{_AMOUNT} )?(?P<coin>gold|silver|copper|gp|sp|cp|coins?)"
    r"(?: (?:gold |silver |copper )?(?:pieces?|coins?))?"
)
_FOR = r"(?: for .+)?"
_VERBS = r"(?:give|hand|toss|slip|offer|pass|pay)"
_FORMS = (
    re.compile(rf"pay (?P<who>[a-z' -]+?)(?: {_MONEY})?{_FOR}"),
    re.compile(rf"{_VERBS} {_MONEY} to (?P<who>[a-z' -]+?){_FOR}"),
    re.compile(rf"{_VERBS} (?P<who>[a-z' -]+?) {_MONEY}{_FOR}"),
    re.compile(rf"count out {_MONEY} (?:for|to) (?P<who>[a-z' -]+?)"),
)
_NUMBERS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6}
_NUMBERS |= {"seven": 7, "eight": 8, "nine": 9, "ten": 10, "some": 1, "a few": 3}
_METAL = {"silver": "silver", "sp": "silver", "copper": "copper", "cp": "copper"}


@dataclass(frozen=True)
class PayIntent:
    actor_id: str
    npc_id: str
    gold: int
    rest: str | None = None


def _asked(state: GameState, npc_id: str) -> int:
    """What an open `pay` step still asks of this NPC (0 when none does)."""
    npc = state.world.npcs[npc_id]
    due = [
        s.gold - npc.paid
        for q in state.world.quests.values()
        if q.state is QuestState.ACTIVE
        for s in q.steps[q.steps_done : q.steps_done + 1]
        if s.kind is StepKind.PAY and s.npc == npc_id and s.gold > npc.paid
    ]
    return due[0] if due else 0


def _is_hero(state: GameState, who: str) -> bool:
    said = who.strip().removeprefix("the ")
    return any(
        c.kind is CreatureKind.PC and said in (c.name.lower(), c.name.lower().split()[0])
        for c in state.creatures.values()
    )


def _read(state: GameState, actor_id: str, text: str) -> PayIntent | None:
    for form in _FORMS:
        match = form.fullmatch(text)
        if match is None or _is_hero(state, match["who"]):
            continue
        npc_id = named_npc(state, match["who"], anywhere=True)
        if npc_id is None:
            continue
        coin = match["coin"]
        if coin is None:
            return PayIntent(actor_id, npc_id, _asked(state, npc_id) or 1)
        raw = match["n"]
        amount = int(raw) if raw is not None and raw.isdigit() else _NUMBERS.get(raw or "", 1)
        return PayIntent(actor_id, npc_id, gold_for(amount, _METAL.get(coin, "gold")))
    return None


def pay_intent(state: GameState, actor_id: str, clean: str) -> PayIntent | None:
    if actor_id not in state.creatures:
        return None
    split = split_clause(clean)
    if split is not None:
        head, rest = split
        found = _read(state, actor_id, head)
        if found is not None:
            return PayIntent(found.actor_id, found.npc_id, found.gold, rest)
    return _read(state, actor_id, clean)
