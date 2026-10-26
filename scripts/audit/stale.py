"""Staleness heuristic for the narration audit (M40.3). A measurement, not game logic.

A story record (fact, scene summary, `Narrated:` line, place description) is STALE when it was
made at some seq and a LATER engine event changed the status of an entity the record names.
Births are not changes and only entities that existed when the record was made
(or joined within BIRTH_SLACK seqs after it) count.
Heroes count only when dead. Status changes are found by diffing `statuses(state)` after
every replayed event:
  creature  alive / down / dead / gone   (key: creature id)
  quest     quest state plus whether it is the pending ask   (key: quest id)
  item      who holds it: a place id, or the heroes carrying it   (key: item name, lowercase)
A record names an entity when the entity id is in its `entity_ids`, or when the entity's NAME
(or its name without a trailing counter such as "Stirge 2", plus a plural "s") appears in the
text as a whole word. Records with no entity ids (descriptions, narration lines) rely on names
only. A record with offer words (accept, refuse, request, promise) also names the quests its
giver NPC gives. The first time a record text is seen fixes its seq; the same text later keeps it.
"""

import re
from collections.abc import Iterable

from aidm.models.state import GameState

Status = dict[str, str]
BIRTH_SLACK = 30  # a record can be written just before its creatures join the state


def statuses(state: GameState) -> Status:
    out: Status = {}
    for cid, c in state.creatures.items():
        # heroes flicker down and up all fight: only their death counts
        out[cid] = "dead" if c.dead else "alive" if c.pc is not None else _foe(c.hp)
    ask = state.world.quest_ask
    for qid, q in state.world.quests.items():
        out[qid] = q.state.value + ("/asked" if ask is not None and ask.quest_id == qid else "")
    if ask is not None and ask.quest_id not in state.world.quests:
        out[ask.quest_id] = "asked"
    for item in state.world.items.values():
        out["item:" + item.name.lower()] = item.node_id or "carried"
    for c in state.creatures.values():
        if c.pc is not None:
            for inv in c.pc.inventory:
                out.setdefault("item:" + inv.item.replace("-", " ").lower(), "carried:" + c.id)
    return out


def _foe(hp: int) -> str:
    return "down" if hp <= 0 else "alive"


def changed(before: Status, after: Status) -> list[str]:
    """Keys that existed before and now differ or vanished (a birth is not a change)."""
    return [k for k, v in before.items() if after.get(k, "gone") != v]


def _aliases(name: str) -> list[str]:
    base = re.sub(r"\s+[0-9A-Za-z]$", "", name.strip())
    return [a for a in {name, base} if len(a) >= 3]


def alias_table(state: GameState) -> dict[str, list[str]]:
    """alias (lowercase) -> status keys it can mean."""
    pairs: list[tuple[str, str]] = []
    pairs += [(c.name, cid) for cid, c in state.creatures.items()]
    pairs += [(q.title, qid) for qid, q in state.world.quests.items()]
    pairs += [(i.name, "item:" + i.name.lower()) for i in state.world.items.values()]
    table: dict[str, list[str]] = {}
    for name, key in pairs:
        for alias in _aliases(name):
            table.setdefault(alias.lower(), []).append(key)
    return table


OFFER_WORDS = re.compile(r"accept|refus|request|promis|offer|\bask", re.IGNORECASE)


def giver_table(state: GameState) -> dict[str, list[str]]:
    """npc id and lowercase npc name -> the quests that npc gives."""
    out: dict[str, list[str]] = {}
    for qid, q in state.world.quests.items():
        npc = state.world.npcs.get(q.giver_npc_id or "")
        if npc is not None:
            out.setdefault(npc.id, []).append(qid)
            out.setdefault(npc.name.lower(), []).append(qid)
    return out


def entities_named(
    text: str, ids: Iterable[str], table: dict[str, list[str]], givers: dict[str, list[str]]
) -> set[str]:
    named = set(ids)
    low = text.lower()
    if OFFER_WORDS.search(low):  # an offer record names the quest its giver gives
        for key, quests in givers.items():
            if key in named or key in low:
                named.update(quests)
    for alias, keys in table.items():
        if re.search(r"\b" + re.escape(alias) + r"s?\b", low):
            named.update(keys)
    return named


def is_stale(
    named: set[str], made: int, now: int, log: list[tuple[int, str]], born: dict[str, int]
) -> bool:
    """A change after `made` to a named entity that already existed when the record was made."""
    return any(
        made < seq <= now and key in named and born.get(key, 0) <= made + BIRTH_SLACK
        for seq, key in log
    )
