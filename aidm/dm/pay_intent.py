"""Typed paying of an NPC (M29.9a T17: "Brienne pays Rutter the Gap for a crossing" was told as
paid with no coin moving, and "Brienne hands Rutter the Gap 1 gold piece" was refused as a thing
not carried). A deterministic precheck like `aidm.dm.give_intent`.

The `pay` phrase row (data/bg3/intent_phrases.json) reads the sentence (the hero's own name with
a third-person verb reads the same; the first clause is the payment and the rest, if any, is
another act told with it, `PayIntent.rest`; then the whole sentence):
- "pay <who> [<money>] [for ...]", "pay <money> to <who> [for ...]";
- "<give|hand|toss|slip|offer|pass> <who> <money> [for ...]", "<verb> <money> to <who> ...",
  "count out <money> for <who>";
- `money` is "[n|a|an|one..ten|some] <gold|silver|copper|gp|sp|cp|coin|coins> [pieces|coins]";
  silver and copper round up to whole gold as the shop does (`rules.paying.gold_for`), a coin
  of no metal is gold, and no amount is 1. "Pay Rutter for a crossing" with no money pays what
  an open `pay` step asks of that NPC, else 1 gold (DECISIONS M29.9a);
- `who` is a known NPC (`give_intent.named_npc`, a present one first); naming a hero is the
  hero hand-over (`aidm.dm.hand_intent`), not this.
None when no NPC is named (the next form is tried). The rules decide
(`aidm.rules.paying.pay_events`).

Public API: `PayIntent(actor_id, npc_id, gold, rest)`, `RESOLVERS` (`pay`).
"""

from dataclasses import dataclass

from aidm.dm.give_intent import named_npc
from aidm.dm.intent_match import Found, Resolver
from aidm.models.quests import StepKind
from aidm.models.state import CreatureKind, GameState
from aidm.models.world import QuestState
from aidm.rules.paying import gold_for

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


def pay(found: Found) -> PayIntent | None:
    state, actor_id, who = found.state, found.actor_id, found.group("who") or ""
    if actor_id not in state.creatures or _is_hero(state, who):
        return None
    npc_id = named_npc(state, who, anywhere=True)
    if npc_id is None:
        return None
    coin = found.group("coin")
    if coin is None:
        return PayIntent(actor_id, npc_id, _asked(state, npc_id) or 1, found.rest)
    raw = found.group("n")
    amount = int(raw) if raw is not None and raw.isdigit() else _NUMBERS.get(raw or "", 1)
    return PayIntent(actor_id, npc_id, gold_for(amount, _METAL.get(coin, "gold")), found.rest)


RESOLVERS: dict[str, Resolver] = {"pay": pay}
