"""What each foe in a fight can do, as text the guard can search (M31.2b, items 908).

Round 3 told an ice mephit "splitting into three icy shards that skitter away and reform on the
far side of the chamber" (r3-items 908): an ability no mephit has, told with no attack verb, so
the blow checks never saw it. `feat_texts(fighters, events)` freezes, per foe whose stat block
the SRD catalogue holds, one lowercase text of everything that foe may be told doing: the names
and descriptions of its SRD special traits, actions, reactions and legendary actions, its
movement modes ("fly", "swim", "burrow", "hover"), its features and resources (a master's trait),
its conditions, and this turn's events by or on it (a monster action, a spell, a feature, a
condition applied). The guard (`aidm.dm.guard_foes`) looks for a `foe_feats` row's `support`
stems in it (data/bg3/guard_lexicon.json); a foe with no stat block has no text and is never
judged (fail open).

Public API: `feat_texts(fighters, events) -> dict[str, str]`.
"""

from collections.abc import Sequence

from aidm.data.srd import srd
from aidm.data.srd_monsters import SrdMonster
from aidm.models import events as ev
from aidm.models.combat_events import FeatureUsed, MonsterActionUsed, SpellCast
from aidm.models.state import Creature


def _block_text(block: SrdMonster) -> list[str]:
    parts: list[str] = []
    for entry in (
        *block.special_abilities,
        *block.actions,
        *block.reactions,
        *block.legendary_actions,
    ):
        parts += [entry.name, entry.desc]
    speed = block.speed
    modes = {"fly": speed.fly, "swim": speed.swim, "climb": speed.climb, "burrow": speed.burrow}
    parts += [mode for mode, value in modes.items() if value]
    if speed.hover:
        parts.append("hover")
    return parts


def _event_text(cid: str, events: Sequence[ev.AnyEvent]) -> list[str]:
    parts: list[str] = []
    for e in events:
        if isinstance(e, MonsterActionUsed) and e.creature_id == cid:
            parts += [e.action, e.name]
        elif isinstance(e, FeatureUsed) and e.creature_id == cid:
            parts += [e.feature, e.name]
        elif isinstance(e, SpellCast) and e.caster_id == cid:
            parts.append(e.spell_id)
        elif isinstance(e, ev.ConditionApplied) and e.creature_id == cid:
            parts.append(e.condition.name)
    return parts


def feat_texts(fighters: Sequence[Creature], events: Sequence[ev.AnyEvent]) -> dict[str, str]:
    out: dict[str, str] = {}
    for creature in fighters:
        if creature.pc is not None or creature.monster_index is None:
            continue
        block = srd().monsters.find(creature.monster_index)
        if block is None:
            continue
        parts = [
            *_block_text(block),
            *creature.traits,
            *creature.resources,
            *(c.name for c in creature.conditions),
            *_event_text(creature.id, events),
        ]
        out[creature.id] = " ".join(parts).replace("-", " ").replace("_", " ").casefold()
    return out
