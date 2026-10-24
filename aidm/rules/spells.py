"""Casting a spell: validation, slot, concentration and the DSL interpreter (SPEC 7.4).

`cast_spell` is the ONE way a spell happens (the hotbar `cast` command, and later the DM tools
and monster spell kits). Everything is validated before any event: the spell exists in the DSL
data (unsupported spells are not shipped), is on the caster's sheet and prepared, a slot (or
the innate resource) can pay at the requested level, and the targets are valid and in range.

Event order: the slot `ResourceSet` (none for cantrips), `SpellCast` (log), the old
concentration's end (a concentration spell replaces it, SRD 5.1), area surfaces, the effects of
every target instance in order, the area's surface damage interactions (fire into an oil zone),
then `ConcentrationStarted` linking the conditions this cast applied (so they end with it; its
surfaces carry their own concentration flag).

Also refused before any event: a caster whose conditions block verbal components (Silence) and
a spell with a verbal component (SRD components), and a "minutes" spell (Prayer of Healing)
while the caster is in an active fight.

Economy (`cast_command`, in combat): the spell's casting time spends the action or the bonus
action. BG3 rule: a bonus-action spell does NOT restrict the action to a cantrip (the SRD 5.1
rule is dropped; docs/RULES_DECISIONS.md M3.4). Reaction spells are Tier 2 (refused).

Monsters (M3.8) cast from their SRD spell kits (`rules.monster_catalog.monster_spells`): the
kit's DC, attack bonus and caster level (cantrip scaling), slots as `spell-slot-<n>` resources,
innate per-day uses, at-will innate spells free; a spell outside the kit is not ready.

Public API:
- `cast_spell(state, caster_id, spell, slot_level, target_ids, target_zone, rng, regs) ->
  list[AnyEvent]` (no economy; usable outside a fight for non-attack, non-area spells).
- `scene_cast(state, caster_id, spell, regs) -> list[AnyEvent]` (M30.2b): out of a fight, a
  spell aimed at no creature (a point or area spell, or a hostile spell with no one to strike):
  the same caster, readiness, verbal and slot checks as `cast_spell`, then the paying events
  and one `SpellCast(at_scene=True)`. Nothing else is recorded: outside a fight there is no zone
  to move into or cover and no combatant to strike, so a teleport moves nobody between places
  (travel stays travel), a surface lies nowhere, and no concentration starts or ends (there is
  nothing to hold; docs/RULES_DECISIONS.md M30.2b).
- `scroll_cast(state, reader_id, spell, numbers, (target_ids, target_zone), rng, regs)` (M27.7):
  a spell read from a scroll with the scroll's numbers at the spell's own level, no slot
  (`aidm.rules.scroll_read`).
- `run_cast(ctx, targets) -> list[AnyEvent]`: the effect half of a cast on a prepared
  `CastContext` (concentration swap, surfaces, every target instance, zone damage,
  concentration start); monster save actions run their pseudo spells through it.
- `cast_command(state, cmd, regs, rng) -> list[AnyEvent]`: the `CastCommand` with economy.
"""

from collections.abc import Sequence

from aidm.data.combat_data import CombatRegistries
from aidm.data.spell_defs import SpellDef, SurfaceEffect
from aidm.models.combat_events import SpellCast
from aidm.models.commands import CastCommand, RefusalCode
from aidm.models.encounter import EncounterStatus
from aidm.models.events import AnyEvent
from aidm.models.state import Creature, GameState
from aidm.rules.command_checks import CommandRefused, acting, changed, spend
from aidm.rules.concentration import end_concentration, start_concentration
from aidm.rules.conditions import condition_blocks_verbal
from aidm.rules.dice import Rng
from aidm.rules.features import character_level
from aidm.rules.monster_catalog import monster_spells
from aidm.rules.projection import project_state
from aidm.rules.spell_context import CastContext
from aidm.rules.spell_effects import (
    damage_types,
    place_surface,
    run_effects,
    zone_damage,
)
from aidm.rules.spell_targets import (
    CasterNumbers,
    SpellTargets,
    cast_slot,
    caster_numbers,
    resolve_targets,
)


def _check_casting(
    state: GameState, caster_id: str, spell: SpellDef, regs: CombatRegistries
) -> None:
    caster = state.creatures[caster_id]
    srd = regs.chars.spells.find(spell.index)
    if srd is not None and "V" in srd.components and condition_blocks_verbal(caster):
        raise CommandRefused(
            RefusalCode.CANNOT_ACT, "No sound leaves your lips: you cannot cast that."
        )
    enc = state.encounter
    fighting = (
        enc is not None and enc.status is EncounterStatus.ACTIVE and caster_id in enc.combatants
    )
    if spell.casting_time == "minutes" and fighting:
        raise CommandRefused(
            RefusalCode.CANNOT_ACT, "That spell takes minutes to cast, not a heartbeat."
        )


def _numbers(
    caster: Creature, spell: SpellDef, regs: CombatRegistries
) -> tuple[CasterNumbers, int]:
    if caster.pc is not None or caster.monster_index is None:
        return caster_numbers(caster, spell.index, regs.chars), character_level(caster)
    block = regs.monsters.find(caster.monster_index)
    kit = monster_spells(block) if block is not None else ()
    entry = next((s for s in kit if s.index == spell.index), None)
    if entry is None:
        raise CommandRefused(RefusalCode.SPELL_NOT_READY, "You do not have that spell ready.")
    numbers = CasterNumbers(
        save_dc=entry.save_dc,
        attack_bonus=entry.attack_bonus,
        modifier=entry.modifier,
        resource=entry.resource,
    )
    return numbers, entry.caster_level


def run_cast(ctx: CastContext, targets: SpellTargets) -> list[AnyEvent]:
    spell = ctx.spell
    if spell.concentration:
        ctx.emit(end_concentration(ctx.state, ctx.caster_id, f"cast {spell.index}"))
    if targets.zone is not None:
        for effect in spell.effects:
            if isinstance(effect, SurfaceEffect):
                place_surface(ctx, effect, targets.zone)
    shared = spell.targeting.kind == "area"
    for target_id in targets.instances:
        run_effects(ctx, spell.effects, target_id, shared=shared)
    if targets.zone is not None:
        for damage_type in damage_types(spell.effects):
            zone_damage(ctx, targets.zone, damage_type)
    if spell.concentration:
        ctx.emit(start_concentration(ctx.state, ctx.caster_id, spell.index, ctx.links))
    return ctx.events


def _resolve_cast(
    state: GameState,
    caster_id: str,
    spell: SpellDef,
    plan: tuple[CasterNumbers, int, int, list[AnyEvent]],
    aim: tuple[Sequence[str], str | None],
    rng: Rng,
    regs: CombatRegistries,
) -> list[AnyEvent]:
    """`plan` = (numbers, cast level, character level, the paying events); `aim` = (target ids,
    target zone)."""
    numbers, cast_level, char_level, paid = plan
    targets = resolve_targets(state, caster_id, spell, cast_level, char_level, aim[0], aim[1])
    srd = regs.chars.spells.find(spell.index)
    ctx = CastContext(
        rng=rng,
        spell=spell,
        caster_id=caster_id,
        cast_level=cast_level,
        numbers=numbers,
        char_level=char_level,
        feats=regs.chars.features,
        state=project_state(state, paid),
        name=srd.name if srd is not None else spell.index,
        target_zone=targets.zone,
        events=list(paid),
    )
    ctx.emit(
        [
            SpellCast(
                caster_id=caster_id,
                spell_id=spell.index,
                cast_level=cast_level,
                target_ids=targets.chosen,
                target_zone=targets.zone,
            )
        ]
    )
    return run_cast(ctx, targets)


def _caster(state: GameState, caster_id: str, spell: SpellDef, regs: CombatRegistries) -> Creature:
    caster = state.creatures.get(caster_id)
    if caster is None or caster.dead:
        raise CommandRefused(RefusalCode.CANNOT_ACT, "You cannot cast right now.")
    _check_casting(state, caster_id, spell, regs)
    return caster


def cast_spell(
    state: GameState,
    caster_id: str,
    spell: SpellDef,
    slot_level: int | None,
    target_ids: Sequence[str],
    target_zone: str | None,
    rng: Rng,
    regs: CombatRegistries,
) -> list[AnyEvent]:
    caster = _caster(state, caster_id, spell, regs)
    numbers, char_level = _numbers(caster, spell, regs)
    cast_level, paid = cast_slot(caster, spell, slot_level, numbers.resource)
    plan = (numbers, cast_level, char_level, paid)
    return _resolve_cast(state, caster_id, spell, plan, (target_ids, target_zone), rng, regs)


def scene_cast(
    state: GameState, caster_id: str, spell: SpellDef, regs: CombatRegistries
) -> list[AnyEvent]:
    enc = state.encounter
    if enc is not None and enc.status is EncounterStatus.ACTIVE and caster_id in enc.combatants:
        raise CommandRefused(RefusalCode.CANNOT_ACT, "In a fight, cast it from your spells.")
    caster = _caster(state, caster_id, spell, regs)
    numbers, _ = _numbers(caster, spell, regs)
    cast_level, paid = cast_slot(caster, spell, None, numbers.resource)
    cast = SpellCast(
        caster_id=caster_id, spell_id=spell.index, cast_level=cast_level, at_scene=True
    )
    return [*paid, cast]


def scroll_cast(
    state: GameState,
    reader_id: str,
    spell: SpellDef,
    numbers: CasterNumbers,
    aim: tuple[Sequence[str], str | None],
    rng: Rng,
    regs: CombatRegistries,
) -> list[AnyEvent]:
    """A spell read from a scroll (M27.7): the scroll's own numbers, cast at the spell's own
    level, no slot and no sheet check (anyone may read one, BG3)."""
    reader = _caster(state, reader_id, spell, regs)
    plan: tuple[CasterNumbers, int, int, list[AnyEvent]] = (
        numbers,
        spell.level,
        character_level(reader),
        [],
    )
    return _resolve_cast(state, reader_id, spell, plan, aim, rng, regs)


def cast_command(
    state: GameState, cmd: CastCommand, regs: CombatRegistries, rng: Rng
) -> list[AnyEvent]:
    acting(state, cmd.actor_id)
    spell = regs.spells.find(cmd.spell_id)
    if spell is None:
        raise CommandRefused(RefusalCode.UNKNOWN_SPELL, "That spell cannot be cast here.")
    if spell.casting_time == "reaction":
        raise CommandRefused(RefusalCode.CANNOT_ACT, "Reaction spells are cast in response.")
    bonus = spell.casting_time == "bonus_action"
    economy = spend(state, cmd.actor_id, action=not bonus, bonus_action=bonus, reason=spell.index)
    events = cast_spell(
        state, cmd.actor_id, spell, cmd.slot_level, cmd.target_ids, cmd.target_zone, rng, regs
    )
    return [changed(cmd.actor_id, economy, spell.index), *events]
