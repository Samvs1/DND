"""Loot after a victory: deterministic from the injected RNG and data/bg3/loot_tables.json.

Every defeated hostile combatant rolls its table (region tier x monster type; a campaign boss uses
the `boss` table): gold dice, an item chance with a weighted pick, and a camp supply find. The sum
is ONE `Payout` shared by the living PCs (`rules.rewards`), so a fight yields one `RewardGranted`
log event, `GoldChanged`, `InventoryChanged` and `CampSuppliesChanged` events. The session seeds
the RNG from the campaign seed and the encounter id (`loot_rng`).

Public API:
- `loot_kind(state, creature) -> str`: "boss" for a campaign boss, else the SRD creature type.
- `loot_payout(state, tables, rng) -> Payout`: the loot of the ACTIVE encounter's defeated foes.
- `victory_loot_events(state, tables, catalogue, rng) -> list[AnyEvent]`.
- `end_encounter_with_loot(state, status, tables, catalogue, rng) -> list[AnyEvent]`:
  `end_encounter` plus the loot of a VICTORY (the one call the session makes at a fight's end),
  totals chained (`rules.running_totals`: the kill XP and the loot read one state).
- `loot_rng(state) -> random.Random`: `Random(f"{seed}:loot:{encounter id}")`.
"""

import random

from aidm.data.item_catalogue import CatalogueItem
from aidm.data.loot_defs import LootTable, LootTables
from aidm.data.registry import Registry
from aidm.models.encounter import EncounterStatus
from aidm.models.events import AnyEvent
from aidm.models.state import Creature, GameState
from aidm.rules.dice import Rng, roll
from aidm.rules.encounter import active_encounter, defeated_hostiles, end_encounter
from aidm.rules.monster_stats import creature_type_of
from aidm.rules.rewards import Payout, payout_events
from aidm.rules.running_totals import chain_totals

BOSS_KIND = "boss"


def loot_rng(state: GameState) -> random.Random:
    enc = active_encounter(state)
    return random.Random(f"{state.seed}:loot:{enc.id}")


def loot_kind(state: GameState, creature: Creature) -> str:
    campaign = state.campaign
    if campaign is not None:
        for region in campaign.plan.all_regions():
            boss = region.boss
            if creature.name == boss.name and creature.monster_index == boss.monster_id:
                return BOSS_KIND
    return creature_type_of(creature)


def _pick(table: LootTable, rng: Rng) -> str:
    total = sum(entry.weight for entry in table.items)
    point = rng.randint(1, total)
    for entry in table.items:
        point -= entry.weight
        if point <= 0:
            return entry.item
    return table.items[-1].item


def _roll_one(table: LootTable, rng: Rng) -> Payout:
    gold = roll(table.gold, rng).total if table.gold.strip() not in ("", "0") else 0
    items: tuple[str, ...] = ()
    if table.items and rng.randint(1, 100) <= table.item_chance:
        items = (_pick(table, rng),)
    supplies = table.supply if table.supply and rng.randint(1, 100) <= table.supply_chance else 0
    return Payout(gold_total=max(0, gold), items=items, supplies=supplies)


def loot_payout(state: GameState, tables: LootTables, rng: Rng) -> Payout:
    gold, supplies = 0, 0
    items: list[str] = []
    for combatant in defeated_hostiles(state):
        creature = state.creatures.get(combatant.creature_id)
        if creature is None:
            continue
        table = tables.table_for(state.world.region_tier, loot_kind(state, creature))
        one = _roll_one(table, rng)
        gold += one.gold_total
        supplies += one.supplies
        items.extend(one.items)
    return Payout(gold_total=gold, items=tuple(items), supplies=supplies)


def victory_loot_events(
    state: GameState, tables: LootTables, catalogue: Registry[CatalogueItem], rng: Rng
) -> list[AnyEvent]:
    enc = active_encounter(state)
    return payout_events(state, loot_payout(state, tables, rng), enc.id, "loot", catalogue)


def end_encounter_with_loot(
    state: GameState,
    status: EncounterStatus,
    tables: LootTables,
    catalogue: Registry[CatalogueItem],
    rng: Rng,
) -> list[AnyEvent]:
    events = end_encounter(state, status)
    if status is EncounterStatus.VICTORY:
        events.extend(victory_loot_events(state, tables, catalogue, rng))
    return chain_totals(state, events)
