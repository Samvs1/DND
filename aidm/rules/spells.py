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

Economy (`cast_command`, in combat): the spell's casting time spends the action or the bonus
action. BG3 rule: a bonus-action spell does NOT restrict the action to a cantrip (the SRD 5.1
rule is dropped; docs/RULES_DECISIONS.md M3.4). Reaction spells are Tier 2 (refused).

Public API:
- `cast_spell(state, caster_id, spell, slot_level, target_ids, target_zone, rng, regs) ->
  list[AnyEvent]` (no economy; usable outside a fight for non-attack, non-area spells).
- `cast_command(state, cmd, regs, rng) -> list[AnyEvent]`: the `CastCommand` with economy.
"""

from collections.abc import Sequence

from aidm.data.combat_data import CombatRegistries
from aidm.data.spell_defs import SpellDef, SurfaceEffect
from aidm.models.combat_events import SpellCast
from aidm.models.commands import CastCommand, RefusalCode
from aidm.models.events import AnyEvent
from aidm.models.state import GameState
from aidm.rules.command_checks import CommandRefused, acting, changed, spend
from aidm.rules.concentration import end_concentration, start_concentration
from aidm.rules.dice import Rng
from aidm.rules.features import character_level
from aidm.rules.projection import project_state
from aidm.rules.spell_effects import (
    CastContext,
    damage_types,
    place_surface,
    run_effects,
    zone_damage,
)
from aidm.rules.spell_targets import cast_slot, caster_numbers, resolve_targets


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
    caster = state.creatures.get(caster_id)
    if caster is None or caster.dead:
        raise CommandRefused(RefusalCode.CANNOT_ACT, "You cannot cast right now.")
    numbers = caster_numbers(caster, spell.index, regs.chars)
    cast_level, paid = cast_slot(caster, spell, slot_level, numbers.resource)
    char_level = character_level(caster)
    targets = resolve_targets(
        state, caster_id, spell, cast_level, char_level, target_ids, target_zone
    )
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
    if spell.concentration:
        ctx.emit(end_concentration(ctx.state, caster_id, f"cast {spell.index}"))
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
        ctx.emit(start_concentration(ctx.state, caster_id, spell.index, ctx.links))
    return ctx.events


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
