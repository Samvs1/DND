"""The combat AI's view of a fight (M3.10): sides, threat and the value of outcomes.

`ai_view(state, actor_id, regs)` is computed once per decision. Values are in "hit points of
enemy damage potential" units so damage, kills, healing and control compare on one scale:
- damage on an enemy: the expected damage that counts (capped at its remaining HP and temp HP),
  weighted up by its threat; a kill bonus when the expected damage reaches its HP; a bonus for
  hitting a concentrating creature (a damage roll forces a concentration save);
- damage on an ally (area spells, breath weapons): a heavy loss, heavier for a kill or a dying ally;
- healing: getting a dying ally up is worth a lot, topping up a wounded one a little;
- control: the expected disabling weight times the target's threat; buffs on allies a little.

Threat (`creature_threat`): the creature's best average damage per turn (PC weapons, a monster's
best catalog option) plus its remaining spell slot levels and a bonus for a healer (a heal spell
it can cast). It is normalised to 0..1 by `t / (t + 10)`.

Public API: `AiView(actor_id, side, zone_id, enemies, allies, threat)`, `ai_view(state, actor_id,
regs) -> AiView | None` (None outside an active fight or for a non-combatant), `creature_threat(
state, creature, regs) -> float`, `damage_value`, `ally_loss`, `heal_value`, `control_value`,
`buff_value`, `KILL_BONUS`, `CONCENTRATION_BONUS`.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from aidm.data.combat_data import CombatRegistries
from aidm.data.spell_defs import Effect, HealEffect
from aidm.models.encounter import EncounterStatus, Side
from aidm.models.state import Creature, GameState
from aidm.rules.ai_estimates import dice_average
from aidm.rules.attack_profiles import attack_options
from aidm.rules.monster_actions import monster_catalog_of
from aidm.rules.monster_catalog import MonsterCatalog, MonsterOption
from aidm.rules.spellcasting import parse_slot_key

KILL_BONUS = 6.0
CONCENTRATION_BONUS = 4.0
_HEALER_BONUS = 4.0
_SLOT_WEIGHT = 1.0
_SLOT_CAP = 10.0
_OPPOSED = {Side.PARTY: Side.HOSTILE, Side.HOSTILE: Side.PARTY}


@dataclass(frozen=True)
class AiView:
    actor_id: str
    side: Side
    zone_id: str
    enemies: tuple[str, ...]
    allies: tuple[str, ...]
    threat: Mapping[str, float]

    def norm(self, creature_id: str) -> float:
        raw = self.threat.get(creature_id, 5.0)
        return raw / (raw + 10.0)


def _option_damage(option: MonsterOption, catalog: MonsterCatalog) -> float:
    if option.shape == "multiattack" and option.routines:
        steps = option.routines[0]
        return sum(
            _option_damage(sub, catalog)
            for step in steps
            if (sub := catalog.option(step.action)) is not None and sub.shape == "attack"
        )
    profiles = [p for p in (option.melee, option.ranged) if p is not None]
    best = max((dice_average(p.damage) for p in profiles), default=0.0)
    extra = sum(dice_average(x.dice) for x in profiles[0].extra_damage) if profiles else 0.0
    return best + extra


def _heals(effects: tuple[Effect, ...]) -> bool:
    return any(isinstance(e, HealEffect) for e in effects)


def _monster_threat(creature: Creature, regs: CombatRegistries) -> float:
    catalog = monster_catalog_of(creature, regs)
    best = max((_option_damage(o, catalog) for o in catalog.options), default=0.0)
    healer = any(
        (spell := regs.spells.find(s.index)) is not None and _heals(spell.effects)
        for s in catalog.spells
    )
    return best + (_HEALER_BONUS if healer else 0.0)


def _pc_threat(creature: Creature, regs: CombatRegistries) -> float:
    pc = creature.pc
    if pc is None:
        return 3.0
    best = max((dice_average(p.damage) for p in attack_options(creature, regs.chars)), default=1.0)
    slots = 0.0
    for key, pool in creature.resources.items():
        ref = parse_slot_key(key)
        if ref is not None:
            slots += ref.level * pool.current * _SLOT_WEIGHT
    known = {*pc.prepared, *pc.spells_known, *pc.cantrips}
    healer = any((s := regs.spells.find(i)) is not None and _heals(s.effects) for i in known)
    return best + min(slots, _SLOT_CAP) + (_HEALER_BONUS if healer else 0.0)


def creature_threat(state: GameState, creature: Creature, regs: CombatRegistries) -> float:
    if creature.dead:
        return 0.0
    if creature.monster_index is not None and regs.monsters.find(creature.monster_index):
        return _monster_threat(creature, regs)
    return _pc_threat(creature, regs)


def _standing(creature: Creature) -> bool:
    return not creature.dead and creature.hp > 0


def ai_view(state: GameState, actor_id: str, regs: CombatRegistries) -> AiView | None:
    enc = state.encounter
    if enc is None or enc.status is not EncounterStatus.ACTIVE or actor_id not in enc.combatants:
        return None
    me = enc.combatant(actor_id)
    enemy_side = _OPPOSED.get(me.side)
    enemies: list[str] = []
    allies: list[str] = []
    for cid in sorted(enc.combatants):
        combatant, creature = enc.combatants[cid], state.creatures.get(cid)
        if creature is None or creature.dead or combatant.withdrawn is not None or cid == actor_id:
            continue
        if combatant.side is enemy_side and _standing(creature):
            enemies.append(cid)
        elif combatant.side is me.side:
            allies.append(cid)
    ids = [actor_id, *enemies, *allies]
    threat = {cid: creature_threat(state, state.creatures[cid], regs) for cid in ids}
    return AiView(actor_id, me.side, me.zone_id, tuple(enemies), tuple(allies), threat)


def damage_value(view: AiView, target: Creature, expected: float) -> float:
    if expected <= 0:
        return 0.0
    pool = target.hp + target.temp_hp
    norm = view.norm(target.id)
    value = min(expected, pool) * (1.0 + norm)
    if expected >= pool:
        value += KILL_BONUS * (1.0 + 2.0 * norm)
    if target.concentrating_on is not None:
        value += CONCENTRATION_BONUS * min(1.0, expected / 4.0)
    return value


def ally_loss(view: AiView, target: Creature, expected: float) -> float:
    if expected <= 0:
        return 0.0
    if target.hp == 0:
        return 3.0 * KILL_BONUS
    pool = target.hp + target.temp_hp
    loss = 2.0 * min(expected, pool) * (1.0 + view.norm(target.id))
    return loss + (3.0 * KILL_BONUS if expected >= pool else 0.0)


def heal_value(view: AiView, target: Creature, amount: float) -> float:
    if amount <= 0 or target.dead:
        return 0.0
    if target.hp == 0:
        return 15.0 + 10.0 * view.norm(target.id)
    missing = target.max_hp - target.hp
    weight = 1.0 if target.hp * 2 < target.max_hp else 0.25
    return min(amount, missing) * weight


def control_value(view: AiView, target: Creature, control: float) -> float:
    if control <= 0 or target.hp == 0:
        return 0.0
    return control * (2.0 + 8.0 * view.norm(target.id))


def buff_value(view: AiView, target: Creature, buff: float) -> float:
    if buff <= 0 or target.hp == 0:
        return 0.0
    return buff * (1.0 + 4.0 * view.norm(target.id))
