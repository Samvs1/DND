"""Valued action options for the combat AI (M3.10): what the actor could do from where it stands.

Each `AiChoice` is a ready command plus its value (`rules.ai_view` units). Nothing is validated
here beyond what the estimate needs; the planner (`rules.monster_ai`) dry-runs the best ones
through `execute_command` before it commits to any.
- `monster_choices(state, view, regs, *, legendary=False)`: every catalog option of a monster:
  single attacks (melee profile when the target shares the zone, else the ranged one), every
  multiattack routine focused on each target (the extra listed target catches the attacks left
  over after a kill), save actions and spells aimed by `rules.ai_spells` (areas count allies as
  losses). Spent recharge or per-day abilities, unready spells and (legendary) options costing
  more points than are left are skipped. `legendary` lists the legendary options only.
- `pc_choices(state, view, regs, phase)`: a party creature's options for a phase of its turn:
  "action" (weapon attacks of the Attack action and action spells), "attack" (the further
  attacks of an Attack action: weapons only), "bonus" (the off-hand attack, bonus action spells,
  and healing potions for the actor or an ally in its zone).

- `prefers_range(state, creature_id, regs) -> bool`: the creature's best ranged damage (ranged
  weapon profiles, damaging cantrips or spells reaching beyond its zone) beats its best melee
  damage: the planner then keeps distance (ranged/caster role) instead of closing in (brute).

Public API: `AiChoice(command, value, label)`, `monster_choices`, `pc_choices`, `Phase`,
`prefers_range`.
"""

from dataclasses import dataclass
from typing import Literal

from aidm.data.combat_data import CombatRegistries
from aidm.data.spell_defs import (
    AttackRollEffect,
    DamageEffect,
    Effect,
    MultiTargetEffect,
    SaveEffect,
    SpellDef,
)
from aidm.models.combat import AttackEconomy, AttackProfile
from aidm.models.commands import (
    AnyCommand,
    AttackCommand,
    CastCommand,
    MonsterActionCommand,
    UseItemCommand,
)
from aidm.models.state import Creature, GameState
from aidm.rules.abilities import ability_modifier
from aidm.rules.ai_estimates import SpellNumbers, attack_expectation, dice_average
from aidm.rules.ai_spells import spell_aims, spell_cost
from aidm.rules.ai_view import AiView, damage_value, heal_value
from aidm.rules.attack_profiles import attack_options
from aidm.rules.monster_actions import monster_catalog_of
from aidm.rules.monster_catalog import (
    SPELL_PREFIX,
    MonsterCatalog,
    MonsterOption,
    MonsterSpell,
    MultiattackStep,
    StepMode,
)
from aidm.rules.monster_keys import AT_WILL, LEGENDARY_KEY
from aidm.rules.resources import resource_left
from aidm.rules.sheet_spells import spellcasting_block
from aidm.rules.spellcasting import can_cast
from aidm.rules.zones import MELEE_BAND, range_band, zone_range_check

type Phase = Literal["action", "attack", "bonus"]
_AIMS_PER_SPELL = 3
_POTION_COST = 1.0


@dataclass(frozen=True)
class AiChoice:
    command: AnyCommand
    value: float
    label: str


def _in_range(state: GameState, actor_id: str, target_id: str, profile: AttackProfile) -> bool:
    enc = state.encounter
    if enc is None:
        return False
    band = range_band(profile.range_normal, profile.range_long) if profile.ranged else MELEE_BAND
    a, t = enc.combatant(actor_id).zone_id, enc.combatant(target_id).zone_id
    return zone_range_check(enc.zone_map, a, t, band).in_range


def _reaching(
    state: GameState, actor_id: str, target_id: str, option: MonsterOption, mode: StepMode
) -> AttackProfile | None:
    both = [p for p in (option.melee, option.ranged) if p is not None]
    if mode != "any":
        both = [p for p in both if p.ranged == (mode == "ranged")] or both
    return next((p for p in both if _in_range(state, actor_id, target_id, p)), None)


def _attack_choices(
    state: GameState, view: AiView, option: MonsterOption, regs: CombatRegistries
) -> list[AiChoice]:
    choices: list[AiChoice] = []
    feats = regs.chars.features
    for tid in view.enemies:
        profile = _reaching(state, view.actor_id, tid, option, "any")
        if profile is None:
            continue
        expected = attack_expectation(state, view.actor_id, tid, profile, feats)
        value = damage_value(view, state.creatures[tid], expected)
        cmd = MonsterActionCommand(actor_id=view.actor_id, action=option.key, target_ids=(tid,))
        choices.append(AiChoice(cmd, value, f"{option.key}->{tid}"))
    return choices


def _routine_damage(
    state: GameState,
    view: AiView,
    catalog: MonsterCatalog,
    routine: tuple[MultiattackStep, ...],
    tid: str,
    regs: CombatRegistries,
) -> float | None:
    total = 0.0
    for step in routine:
        sub = catalog.option(step.action)
        profile = _reaching(state, view.actor_id, tid, sub, step.mode) if sub else None
        if profile is None:
            return None
        total += attack_expectation(state, view.actor_id, tid, profile, regs.chars.features)
    return total


def _multi_choices(
    state: GameState,
    view: AiView,
    option: MonsterOption,
    catalog: MonsterCatalog,
    regs: CombatRegistries,
) -> list[AiChoice]:
    choices: list[AiChoice] = []
    for index, routine in enumerate(option.routines):
        damage = {
            t: d
            for t in view.enemies
            if (d := _routine_damage(state, view, catalog, routine, t, regs)) is not None
        }
        for tid, total in damage.items():
            target = state.creatures[tid]
            value = damage_value(view, target, total)
            spill = total - target.hp - target.temp_hp
            others = [o for o in damage if o != tid]
            backup = max(others, key=view.norm) if others else None
            ids = (tid,) * len(routine)
            if backup is not None:
                ids = (*ids, backup)
                if spill > 0:
                    value += 0.5 * damage_value(view, state.creatures[backup], spill)
            cmd = MonsterActionCommand(
                actor_id=view.actor_id, action=option.key, target_ids=ids, option=index
            )
            choices.append(AiChoice(cmd, value, f"{option.key}#{index}->{tid}"))
    return choices


def _save_choices(
    state: GameState, view: AiView, option: MonsterOption, regs: CombatRegistries
) -> list[AiChoice]:
    spell = option.save
    if spell is None:
        return []
    feet = spell.range.feet or 5
    numbers = SpellNumbers(
        save_dc=option.dc, attack_bonus=0, modifier=0, char_level=1, range_feet=feet
    )
    choices: list[AiChoice] = []
    for aim in spell_aims(state, view, view.actor_id, spell, numbers, regs)[:_AIMS_PER_SPELL]:
        cmd = MonsterActionCommand(
            actor_id=view.actor_id,
            action=option.key,
            target_ids=aim.target_ids,
            target_zone=aim.target_zone,
        )
        choices.append(
            AiChoice(cmd, aim.value, f"{option.key}@{aim.target_zone or aim.target_ids}")
        )
    return choices


def _monster_spell_ready(creature: Creature, ms: MonsterSpell, spell: SpellDef) -> bool:
    if spell.level == 0 or ms.resource == AT_WILL:
        return True
    if ms.resource is not None and resource_left(creature, ms.resource) > 0:
        return True
    return can_cast(creature, spell.level)


def _monster_spells(
    state: GameState, view: AiView, catalog: MonsterCatalog, regs: CombatRegistries, casting: str
) -> list[AiChoice]:
    creature = state.creatures[view.actor_id]
    choices: list[AiChoice] = []
    for ms in catalog.spells:
        spell = regs.spells.find(ms.index)
        if (
            spell is None
            or spell.casting_time != casting
            or not _monster_spell_ready(creature, ms, spell)
        ):
            continue
        numbers = SpellNumbers(
            ms.save_dc, ms.attack_bonus, ms.modifier, ms.caster_level, spell.range.feet or 5
        )
        cost = spell_cost(spell, creature)
        for aim in spell_aims(state, view, view.actor_id, spell, numbers, regs)[:_AIMS_PER_SPELL]:
            cmd = MonsterActionCommand(
                actor_id=view.actor_id,
                action=SPELL_PREFIX + ms.index,
                target_ids=aim.target_ids,
                target_zone=aim.target_zone,
            )
            choices.append(AiChoice(cmd, aim.value - cost, f"spell:{ms.index}"))
    return choices


def _option_choices(
    state: GameState,
    view: AiView,
    option: MonsterOption,
    catalog: MonsterCatalog,
    regs: CombatRegistries,
) -> list[AiChoice]:
    if option.shape == "attack":
        return _attack_choices(state, view, option, regs)
    if option.shape == "multiattack":
        return _multi_choices(state, view, option, catalog, regs)
    if option.shape == "save":
        return _save_choices(state, view, option, regs)
    return []


def monster_choices(
    state: GameState,
    view: AiView,
    regs: CombatRegistries,
    *,
    legendary: bool = False,
    casting: str = "action",
) -> list[AiChoice]:
    creature = state.creatures[view.actor_id]
    catalog = monster_catalog_of(creature, regs)
    choices: list[AiChoice] = []
    points = resource_left(creature, LEGENDARY_KEY)
    options = catalog.legendary if legendary else catalog.options
    for option in options if casting == "action" else ():
        if option.resource is not None and resource_left(creature, option.resource) < 1:
            continue
        if legendary and option.cost > points:
            continue
        choices.extend(_option_choices(state, view, option, catalog, regs))
    if not legendary:
        choices.extend(_monster_spells(state, view, catalog, regs, casting))
    return choices


def _weapon_choices(
    state: GameState, view: AiView, regs: CombatRegistries, economy: AttackEconomy
) -> list[AiChoice]:
    creature = state.creatures[view.actor_id]
    feats = regs.chars.features
    choices: list[AiChoice] = []
    for profile in attack_options(creature, regs.chars):
        if profile.economy is not economy:
            continue
        for tid in view.enemies:
            if not _in_range(state, view.actor_id, tid, profile):
                continue
            expected = attack_expectation(state, view.actor_id, tid, profile, feats)
            cmd = AttackCommand(actor_id=view.actor_id, target_id=tid, option=profile.key)
            choices.append(
                AiChoice(
                    cmd, damage_value(view, state.creatures[tid], expected), f"{profile.key}->{tid}"
                )
            )
    return choices


def _pc_spells(
    state: GameState, view: AiView, regs: CombatRegistries, casting: str
) -> list[AiChoice]:
    creature = state.creatures[view.actor_id]
    block = spellcasting_block(creature, regs.chars)
    if block is None or creature.pc is None:
        return []
    modifier = ability_modifier(creature.abilities[block.ability])
    lines = [*block.cantrips, *(s for g in block.levels for s in g.spells)]
    choices: list[AiChoice] = []
    for line in lines:
        spell = regs.spells.find(line.index)
        if spell is None or not line.prepared or spell.casting_time != casting:
            continue
        innate = line.resource is not None and resource_left(creature, line.resource) > 0
        if spell.level > 0 and not innate and not can_cast(creature, spell.level):
            continue
        numbers = SpellNumbers(
            block.save_dc, block.attack_bonus, modifier, creature.pc.level, spell.range.feet or 5
        )
        cost = spell_cost(spell, creature)
        for aim in spell_aims(state, view, view.actor_id, spell, numbers, regs)[:_AIMS_PER_SPELL]:
            cmd = CastCommand(
                actor_id=view.actor_id,
                spell_id=spell.index,
                target_ids=aim.target_ids,
                target_zone=aim.target_zone,
            )
            choices.append(AiChoice(cmd, aim.value - cost, f"cast:{spell.index}"))
    return choices


def _potion_choices(state: GameState, view: AiView, regs: CombatRegistries) -> list[AiChoice]:
    creature, enc = state.creatures[view.actor_id], state.encounter
    if creature.pc is None or enc is None:
        return []
    near = [view.actor_id, *(a for a in view.allies if enc.combatant(a).zone_id == view.zone_id)]
    choices: list[AiChoice] = []
    for row in creature.pc.inventory:
        item = regs.consumables.find(row.item)
        if item is None or item.heal is None:
            continue
        for tid in near:
            value = heal_value(view, state.creatures[tid], dice_average(item.heal)) - _POTION_COST
            cmd = UseItemCommand(actor_id=view.actor_id, item=row.item, target_id=tid)
            choices.append(AiChoice(cmd, value, f"potion->{tid}"))
    return choices


def pc_choices(
    state: GameState, view: AiView, regs: CombatRegistries, phase: Phase
) -> list[AiChoice]:
    if phase == "attack":
        return _weapon_choices(state, view, regs, AttackEconomy.ATTACK)
    if phase == "action":
        return [
            *_weapon_choices(state, view, regs, AttackEconomy.ATTACK),
            *_pc_spells(state, view, regs, "action"),
        ]
    return [
        *_weapon_choices(state, view, regs, AttackEconomy.BONUS_ACTION),
        *_pc_spells(state, view, regs, "bonus_action"),
        *_potion_choices(state, view, regs),
    ]


def _effects_damage(effects: tuple[Effect, ...]) -> float:
    total = 0.0
    for effect in effects:
        if isinstance(effect, DamageEffect):
            total += dice_average(effect.dice)
        elif isinstance(effect, AttackRollEffect):
            total += _effects_damage(effect.on_hit)
        elif isinstance(effect, (SaveEffect, MultiTargetEffect)):
            nested = effect.on_fail if isinstance(effect, SaveEffect) else effect.effects
            total += _effects_damage(nested)
    return total


def _spell_reach_damage(spell: SpellDef | None) -> float:
    if spell is None or (spell.range.feet or 0) <= 10:
        return 0.0
    return _effects_damage(spell.effects)


def prefers_range(state: GameState, creature_id: str, regs: CombatRegistries) -> bool:
    creature = state.creatures[creature_id]
    melee, ranged = 0.0, 0.0
    if creature.pc is not None:
        profiles = attack_options(creature, regs.chars)
        known = [*creature.pc.cantrips, *creature.pc.race_cantrips]
        spells = [_spell_reach_damage(regs.spells.find(i)) for i in known]
    else:
        catalog = monster_catalog_of(creature, regs)
        profiles = [p for o in catalog.options for p in (o.melee, o.ranged) if p is not None]
        spells = [_spell_reach_damage(regs.spells.find(s.index)) for s in catalog.spells]
    for profile in profiles:
        average = dice_average(profile.damage)
        if profile.ranged:
            ranged = max(ranged, average)
        else:
            melee = max(melee, average)
    return max([ranged, *spells]) > melee
