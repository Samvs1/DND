"""Stable keys for a monster's catalog options and its resources (M3.8).

Shared by the stat block builder (`rules.monster_stats`, which creates the resources) and the
action catalog (`rules.monster_catalog`, which names the resource an option spends), so the two
can never disagree. Pure string and data helpers; no dice.

- Option keys are `ability_slug(name)`: lower case, runs of other characters become "-", and a
  legendary cost suffix "(Costs 2 Actions)" is dropped ("Wing Attack (Costs 2 Actions)" ->
  "wing-attack"). A special ability's slug is also its trait id (`Creature.traits`).
- Usage resources (`usage_resource(key, usage)`): "recharge on roll" -> `recharge-<key>`
  (1 use, refilled at the start of the monster's turn on a d6 >= min_value, `turn_recharge`;
  rests refill it too), "per day" -> `per-day-<key>` (times, long rest), "recharge after rest"
  -> `rest-<key>` (1 use, short or long rest). "at will" and no usage spend nothing.
- `LEGENDARY_KEY` "legendary-actions": `LEGENDARY_PER_ROUND` points refilled at the start of
  the monster's own turn (`turn_recharge` 1).
- Spells: the SRD spell index is the last segment of the spell URL (`spell_index`); per-day
  innate spells spend `innate-<index>`; `AT_WILL` marks an innate spell that costs nothing.
- `legendary_pool(points) -> Resource`: a legendary points pool refilled each own turn (M31.1d:
  also a master's turn, `rules.master_boost`).
- `legendary_cost(name) -> int`: the "(Costs N Actions)" number, else 1.
- `monster_resources(monster) -> dict[str, Resource]`: every pool the stat block needs (usage
  pools, legendary points, `spell-slot-<n>` slots, innate per-day spells).
"""

import re

from aidm.data.srd_monster_actions import ActionUsage
from aidm.data.srd_monsters import SrdMonster
from aidm.models.state import RechargeKind, Resource
from aidm.rules.spellcasting import SlotKind, slot_key

LEGENDARY_KEY = "legendary-actions"
LEGENDARY_PER_ROUND = 3
AT_WILL = "at-will"
DEFAULT_RECHARGE = 6

_COST = re.compile(r"\(\s*costs?\s+(\d+)\s+actions?\s*\)", re.IGNORECASE)
_NON_WORD = re.compile(r"[^a-z0-9]+")


def ability_slug(name: str) -> str:
    return _NON_WORD.sub("-", _COST.sub("", name).lower()).strip("-")


def legendary_cost(name: str) -> int:
    match = _COST.search(name)
    return int(match.group(1)) if match else 1


def spell_index(url: str) -> str:
    return url.rstrip("/").rsplit("/", 1)[-1]


def usage_resource(key: str, usage: ActionUsage | None) -> tuple[str, Resource] | None:
    if usage is None:
        return None
    match usage.type:
        case "recharge on roll":
            pool = Resource(
                current=1,
                maximum=1,
                recharge=RechargeKind.SHORT_REST,
                turn_recharge=usage.min_value or DEFAULT_RECHARGE,
            )
            return f"recharge-{key}", pool
        case "per day":
            times = max(1, usage.times or 1)
            return f"per-day-{key}", Resource(
                current=times, maximum=times, recharge=RechargeKind.LONG_REST
            )
        case "recharge after rest":
            short = any("short" in r for r in usage.rest_types)
            kind = RechargeKind.SHORT_REST if short else RechargeKind.LONG_REST
            return f"rest-{key}", Resource(current=1, maximum=1, recharge=kind)
        case _:
            return None


def _spell_resources(monster: SrdMonster) -> dict[str, Resource]:
    pools: dict[str, Resource] = {}
    for ability in monster.special_abilities:
        casting = ability.spellcasting
        if casting is None:
            continue
        for level, count in casting.slots.items():
            if level.isdigit() and 1 <= int(level) <= 9 and count > 0:
                key = slot_key(SlotKind.STANDARD, int(level))
                pools[key] = Resource(current=count, maximum=count, recharge=RechargeKind.LONG_REST)
        for spell in casting.spells:
            usage = spell.usage
            if usage is not None and usage.type == "per day":
                times = max(1, usage.times or 1)
                pools[f"innate-{spell_index(spell.url)}"] = Resource(
                    current=times, maximum=times, recharge=RechargeKind.LONG_REST
                )
    return pools


def legendary_pool(points: int, recharge: int = 1) -> Resource:
    """`points` legendary points, refilled at the start of the creature's own turn (on a d6 of
    at least `recharge`; 1: always)."""
    return Resource(
        current=points, maximum=points, recharge=RechargeKind.SHORT_REST, turn_recharge=recharge
    )


def monster_resources(monster: SrdMonster) -> dict[str, Resource]:
    pools: dict[str, Resource] = {}
    for action in monster.actions:
        found = usage_resource(ability_slug(action.name), action.usage)
        if found is not None:
            pools[found[0]] = found[1]
    if monster.legendary_actions:
        pools[LEGENDARY_KEY] = legendary_pool(LEGENDARY_PER_ROUND)
    pools.update(_spell_resources(monster))
    return dict(sorted(pools.items()))
