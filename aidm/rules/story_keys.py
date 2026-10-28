"""Story keys: what an engine event changed, for dating story records (M40.4, SPEC 6.4). Pure.

The reducer marks `World.changed[key] = seq` for every key `story_keys(state, event)` returns
(computed on the state BEFORE the event) and for every quest whose `quest_status` differs after
a world or campaign event (`quest_changes`; that also catches a pending ask cleared by a move).
A key is "<kind>:<what>", where <what> is an entity id or "name:<slug>" (the entity's name as a
slug: a creature's name and its name without a trailing counter, "Stirge 2" -> "stirge", an
item's name or catalogue id, a quest's title), so a record that names a creature which has
since left the state is still matched by its name (`aidm.rules.story_records`).
Kinds:
- `status`: the entity is not as it was: a foe or NPC went down (0 HP), died, came back, left
  or was removed; a hero died or came back; a quest changed state or became / stopped being
  the pending ask; an item changed holder (picked up, handed over, used up, bought, sold).
  What the heroes carry is marked "status:carried:<slug>" (a place description is not about
  the heroes' packs, `aidm.rules.story_records`).
  Births are not changes. A hero going down and up again is not a status change.
- deeds, for the write-time claim check (`aidm.rules.story_claims`): `kill` (a foe or NPC down
  or dead), `flight` (withdrew; the party fled a fight or escaped an offer), `handover` (a
  hand-over, a keepsake given or taken, a trade), `payment` (gold changed hands), `pickup`
  (something came into a hero's pack, or left the place it lay), `refusal` (a quest offer
  declined, an item use the engine refused).

Public API: `STATUS`, `CARRIED`, `KILL`, `FLIGHT`, `HANDOVER`, `PAYMENT`, `PICKUP`, `REFUSAL`,
`story_name(name) -> str`, `creature_names(name) -> tuple[str, ...]`,
`story_keys(state, event) -> tuple[str, ...]`, `quest_status(state) -> dict[str, str]`,
`quest_changes(before, after, state) -> list[str]`.
"""

import re
from collections.abc import Iterable

from aidm.models.campaign_events import OfferResolved
from aidm.models.campaign_state import OfferChoice
from aidm.models.combat_events import CreatureRevived
from aidm.models.encounter import EncounterStatus
from aidm.models.encounter_events import CombatantWithdrew, EncounterEnded
from aidm.models.events import (
    AnyEvent,
    CreatureDied,
    CreatureRemoved,
    GoldChanged,
    HpChanged,
    InventoryChanged,
)
from aidm.models.item_events import HandedOver, ItemUseRefused
from aidm.models.quest_events import KeepsakeGiven, KeepsakeTaken, QuestAskDeclined
from aidm.models.state import Creature, GameState
from aidm.models.trade_events import ItemsTraded
from aidm.models.world_events import ItemRemoved, KeepsakeGained

STATUS = "status"
KILL = "kill"
FLIGHT = "flight"
HANDOVER = "handover"
PAYMENT = "payment"
PICKUP = "pickup"
REFUSAL = "refusal"
CARRIED = "carried:"
MIN_NAME = 3
_COUNTER = re.compile(r"\s+[0-9A-Za-z]$")


def story_name(name: str) -> str:
    return "name:" + re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def creature_names(name: str) -> tuple[str, ...]:
    """The name and the name without a trailing counter ("Stirge 2" -> "Stirge")."""
    base = _COUNTER.sub("", name.strip())
    return tuple(n for n in dict.fromkeys((name.strip(), base)) if len(n) >= MIN_NAME)


def _keys(kinds: Iterable[str], whats: Iterable[str]) -> list[str]:
    whats = list(whats)
    return [f"{k}:{w}" for k in kinds for w in whats]


def _being(c: Creature | None) -> list[str]:
    if c is None:
        return []
    return [
        c.id,
        *([c.npc_id] if c.npc_id else []),
        *(story_name(n) for n in creature_names(c.name)),
    ]


def _life(state: GameState, event: AnyEvent) -> list[str]:
    match event:
        case HpChanged(creature_id=cid, new_hp=new_hp):
            c = state.creatures.get(cid)
            if c is None or c.pc is not None or (c.hp > 0) == (new_hp > 0):
                return []
            return _keys((STATUS, KILL) if new_hp <= 0 else (STATUS,), _being(c))
        case CreatureDied(creature_id=cid):
            return _keys((STATUS, KILL), _being(state.creatures.get(cid)))
        case CreatureRevived(creature_id=cid):
            return _keys((STATUS,), _being(state.creatures.get(cid)))
        case CombatantWithdrew(creature_id=cid):
            return _keys((STATUS, FLIGHT), _being(state.creatures.get(cid)))
        case CreatureRemoved(creature_id=cid):
            c = state.creatures.get(cid)
            if c is None or (c.pc is not None and not c.dead):
                return []
            gone = c.pc is None and not c.dead and c.hp > 0
            return _keys((STATUS, FLIGHT) if gone else (STATUS,), _being(c))
        case _:
            return []


def _party_fled(state: GameState, event: AnyEvent) -> list[str]:
    fled = (isinstance(event, EncounterEnded) and event.status is EncounterStatus.FLED) or (
        isinstance(event, OfferResolved)
        and event.choice is OfferChoice.ESCAPE
        and event.success is not False
    )
    if not fled:
        return []
    return _keys((FLIGHT,), (c.id for c in state.creatures.values() if c.pc is not None))


def _item(item: str) -> list[str]:
    return [item, story_name(item)]


def _goods(state: GameState, event: AnyEvent) -> list[str]:
    match event:
        case InventoryChanged(creature_id=cid, item=item, delta=delta):
            got = _keys((PICKUP,), [cid, *_item(item)]) if delta > 0 else []
            return [f"{STATUS}:{CARRIED}{story_name(item).removeprefix('name:')}", *got]
        case GoldChanged(creature_id=cid):
            return _keys((PAYMENT,), [cid])
        case HandedOver(creature_id=giver, to_id=taker, item=item, gold=gold):
            things = _item(item) if item else []
            paid = _keys((PAYMENT,), (giver, taker)) if gold > 0 else []
            return [*_keys((HANDOVER,), (giver, taker, *things)), *paid]
        case ItemsTraded(npc_id=npc, creature_id=cid, item=item):
            return _keys((HANDOVER, PAYMENT), (npc, cid, *_item(item)))
        case ItemRemoved(item_id=item_id):
            found = state.world.items.get(item_id)
            names = [story_name(found.name)] if found is not None else []
            return _keys((STATUS, PICKUP), (item_id, *names))
        case KeepsakeGained(creature_id=cid, keepsake=k):
            return _keys((STATUS, PICKUP), (cid, k.id, story_name(k.name)))
        case _:
            return _keepsake_moves(state, event)


def _keepsake_moves(state: GameState, event: AnyEvent) -> list[str]:
    match event:
        case KeepsakeGiven(creature_id=cid, keepsake_id=kid, npc_id=npc):
            return _keys((STATUS, HANDOVER), (cid, npc, kid))
        case KeepsakeTaken(creature_id=cid, keepsake_id=kid, npc_id=npc):
            return _keys((STATUS, HANDOVER), (cid, npc, kid))
        case QuestAskDeclined(quest_id=qid):
            quest = state.world.quests.get(qid)
            giver = [quest.giver_npc_id] if quest is not None and quest.giver_npc_id else []
            return _keys((REFUSAL,), (qid, *giver))
        case ItemUseRefused(creature_id=cid, item=item):
            return _keys((REFUSAL,), (cid, *_item(item)))
        case _:
            return []


def story_keys(state: GameState, event: AnyEvent) -> tuple[str, ...]:
    """The story keys `event` changes, read on the state before it is applied."""
    found = [*_life(state, event), *_party_fled(state, event), *_goods(state, event)]
    return tuple(dict.fromkeys(k for k in found if not k.endswith(":name:")))


def quest_status(state: GameState) -> dict[str, str]:
    """Quest id -> its state, plus "/asked" while it is the pending ask."""
    ask = state.world.quest_ask
    asked = ask.quest_id if ask is not None else None
    out = {
        qid: q.state.value + ("/asked" if qid == asked else "")
        for qid, q in state.world.quests.items()
    }
    if asked is not None and asked not in out:
        out[asked] = "asked"
    return out


def quest_changes(before: dict[str, str], after: dict[str, str], state: GameState) -> list[str]:
    """Status keys of the quests that existed before and now differ (a new quest is a birth)."""
    out: list[str] = []
    for qid, was in before.items():
        if after.get(qid, "gone") == was:
            continue
        quest = state.world.quests.get(qid)
        out += _keys((STATUS,), [qid, *([story_name(quest.title)] if quest is not None else [])])
    return out
