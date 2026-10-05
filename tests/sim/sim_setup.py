"""Seeded setup for the headless combat sim (M3.11): a 4-PC party and a CR-budget encounter."""

from __future__ import annotations

import random

from aidm.data.character_data import CharacterRegistries
from aidm.data.combat_data import combat_registries
from aidm.data.encounter_monsters import encounter_candidates
from aidm.data.encounter_tables import encounter_tables
from aidm.data.zone_templates import zone_templates
from aidm.models.abilities import ABILITIES, Ability
from aidm.models.character import InventoryItem
from aidm.models.encounter import (
    Difficulty,
    EncounterSetup,
    MonsterSpawn,
    PartyPlacement,
    SurpriseKind,
)
from aidm.models.events import AnyEvent
from aidm.models.state import Creature, GameState
from aidm.models.zones import ZoneMap
from aidm.rules.ability_gen import STANDARD_ARRAY
from aidm.rules.creation import build_character
from aidm.rules.creation_checks import class_spell_indexes
from aidm.rules.encounter_budget import party_budget, pick_monsters
from aidm.rules.zone_gen import generate_zone_map
from aidm.rules.zones import zone_path
from aidm.session.reducer import apply
from tests.unit.rules.creation_fixtures import default_choices
from tests.unit.rules.leveling_fixtures import level_to

REGS = combat_registries()
PARTY = ("fighter", "rogue", "wizard", "cleric")
_PRIMARY = {
    "fighter": (Ability.STR, Ability.CON, Ability.DEX),
    "rogue": (Ability.DEX, Ability.CON, Ability.WIS),
    "wizard": (Ability.INT, Ability.CON, Ability.DEX),
    "cleric": (Ability.WIS, Ability.CON, Ability.STR),
}
_WANTED = {
    "wizard": ("magic-missile", "burning-hands", "sleep", "shield", "thunderwave", "mage-armor"),
    "cleric": ("healing-word", "cure-wounds", "bless", "guiding-bolt"),
}


def _scores(class_index: str) -> dict[Ability, int]:
    order = [*_PRIMARY[class_index], *(a for a in ABILITIES if a not in _PRIMARY[class_index])]
    return dict(zip(order, STANDARD_ARRAY, strict=True))


def _spells(class_index: str, base: list[str], regs: CharacterRegistries) -> list[str]:
    allowed = class_spell_indexes(regs.spells, class_index, 1, 1)
    wanted = [s for s in _WANTED.get(class_index, ()) if s in allowed]
    return [*wanted, *(s for s in base if s not in wanted)]


def build_pc(class_index: str, cid: str, regs: CharacterRegistries) -> Creature:
    base = default_choices(class_index, "human", None)
    spells = _spells(class_index, base.spells, regs)[: len(base.spells)]
    prepared = _spells(class_index, [], regs)
    if class_index == "wizard":
        prepared = spells[:4]
    update: dict[str, object] = {
        "name": cid.title(),
        "base_scores": _scores(class_index),
        "spells": spells,
        "prepared": prepared[:4] if base.prepared else [],
    }
    creature = build_character(base.model_copy(update=update), regs, cid)
    assert creature.pc is not None
    creature.pc.inventory.append(InventoryItem(item="potion-of-healing", qty=1))
    return creature


def wear_down(creature: Creature) -> None:
    """End of an adventuring day: a third of the HP, a third of every slot and feature use."""
    creature.hp = max(1, creature.max_hp // 3)
    for key, pool in creature.resources.items():
        creature.resources[key] = pool.model_copy(update={"current": pool.maximum // 3})


def build_party(state: GameState, level: int) -> list[str]:
    log: list[AnyEvent] = []
    ids: list[str] = []
    for class_index in PARTY:
        pc = build_pc(class_index, class_index, REGS.chars)
        state.creatures[pc.id] = pc
        level_to(state, pc.id, level, REGS.chars, log)
        ids.append(pc.id)
    return ids


def _near_zone(zone_map: ZoneMap, start: str) -> str:
    others = [z.id for z in zone_map.zones if z.id != start]
    return min(others, key=lambda z: (zone_path(zone_map, start, z).feet, z))


def pick_encounter(
    rng: random.Random, level: int, difficulty: Difficulty, tags: list[str]
) -> list[str]:
    tier = 1 if level <= 2 else 2 if level <= 4 else 3
    pool = encounter_candidates(tier, tags, include_lower=True)
    xp = {m.index: REGS.monsters.get(m.index).xp for m in pool}
    tables = encounter_tables()
    budget = party_budget([level] * len(PARTY), difficulty, tables)
    picked = pick_monsters(rng, budget, xp, len(PARTY), tables)
    return picked or [min(xp, key=lambda i: (xp[i], i))]


def setup_fight(seed: int) -> tuple[GameState, EncounterSetup, random.Random, int, Difficulty]:
    rng = random.Random(seed)
    level = 1 + seed % 5
    difficulty = Difficulty.MEDIUM if seed % 2 else Difficulty.HARD
    state = GameState(campaign_id=f"sim-{seed}", seed=seed)
    party = build_party(state, level)
    if seed % 4 == 2:
        for cid in party:
            wear_down(state.creatures[cid])
    terrains = sorted(t.index for t in zone_templates().all())
    tags = rng.sample(terrains, rng.randint(1, 2))
    zone_map = generate_zone_map(rng, tags, zone_templates())
    start = zone_map.zones[0].id
    foes = _near_zone(zone_map, start)
    monsters = pick_encounter(rng, level, difficulty, tags)
    setup = EncounterSetup(
        encounter_id=f"sim-{seed}",
        zone_map=zone_map,
        party=tuple(PartyPlacement(creature_id=cid, zone_id=start) for cid in party),
        monsters=tuple(MonsterSpawn(monster=m, zone_id=foes) for m in monsters),
        surprise=SurpriseKind.PARTY if seed % 3 == 0 else SurpriseKind.NONE,
    )
    return state, setup, rng, level, difficulty


def apply_all(state: GameState, events: list[AnyEvent], log: list[AnyEvent]) -> None:
    for event in events:
        apply(state, event)
        log.append(event)
