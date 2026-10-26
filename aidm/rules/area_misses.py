"""Who an area spell left untouched in its area, and why (M40.5, SPEC 6.4). Pure.

Round 7 Z10 (r7b-full 505-513): Sleep only put Mortha to sleep, yet the story told the
skeletons' strings slackening: the engine's events named the one it affected and said nothing
of the rest, so the storyteller filled the gap. `area_misses(state, spell, cast, events)` names
the creatures standing in a cast's area (the zone it was aimed at, its neighbours too for
"zone_and_adjacent"; `spell_targets.area_creatures`, the caster and anyone at 0 HP left out)
that none of the cast's own events touched, with the engine's reason, read from the spell's
data and those events, never from a spell name:
- `EXCLUDED`: the targeting leaves them out (`spell_targets.spell_can_affect`): `detail` is
  the creature type it excludes (Sleep and undead), the condition they are immune to, or the
  type they are not (Turn Undead and a living foe);
- `SAVED`: a save against this spell (`CheckResolved` reason "<spell> save") succeeded;
- `NO_HARM`: its damage did them no harm (an immunity: `DamageTaken` of 0);
- `POOL`: an HP-pool spell (Sleep) whose dice ran out before them (too many hit points);
- `UNTOUCHED`: anything else.
The cast's events are the ones after its `SpellCast` up to the next cast, attack, monster action
or turn boundary. The area is read on `state` as it is now (the narrator's state, after the
events), so a creature that walked in after the cast in the same telling counts too.

Public API: `MissReason`, `AreaMiss`, `area_misses(state, spell, cast, events)`.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from aidm.data.spell_defs import HpPoolEffect, SpellDef
from aidm.models.combat_events import AttackRolled, MonsterActionUsed, SpellCast
from aidm.models.events import AnyEvent, CheckResolved, ConditionTicked, DamageTaken, DiceRolled
from aidm.models.state import GameState
from aidm.rules.monster_stats import creature_type_of
from aidm.rules.spell_targets import all_effects, area_creatures, spell_can_affect

_BOUNDARY = (SpellCast, AttackRolled, MonsterActionUsed)
_TURN = ("turn_started", "turn_ended")
_LOG_ONLY = (CheckResolved, DiceRolled, DamageTaken, ConditionTicked)  # touch nobody alone


class MissReason(StrEnum):
    EXCLUDED = "excluded"
    SAVED = "saved"
    NO_HARM = "no_harm"
    POOL = "pool"
    UNTOUCHED = "untouched"


@dataclass(frozen=True)
class AreaMiss:
    creature_id: str
    reason: MissReason
    detail: str = ""


def _span(cast: SpellCast, events: Sequence[AnyEvent]) -> list[AnyEvent]:
    out: list[AnyEvent] = []
    started = False
    for event in events:
        if event is cast:
            started = True
            continue
        if not started:
            continue
        if isinstance(event, _BOUNDARY) or event.type in _TURN:
            break
        out.append(event)
    return out


def _who(event: AnyEvent) -> str | None:
    who = getattr(event, "creature_id", None)
    return who if isinstance(who, str) else None


def _excluded(state: GameState, spell: SpellDef, cid: str) -> str:
    creature = state.creatures[cid]
    targeting = spell.targeting
    kind = creature_type_of(creature)
    if targeting.creature_types and kind not in targeting.creature_types:
        return f"not {' or '.join(targeting.creature_types)}"
    if kind in targeting.exclude_creature_types:
        return kind
    immune = set(targeting.exclude_condition_immune) & set(creature.condition_immunities)
    return f"immune to {', '.join(sorted(immune))}"


def _reason(spell: SpellDef, cid: str, span: Sequence[AnyEvent]) -> MissReason:
    mine = [e for e in span if _who(e) == cid]
    save = f"{spell.index} save"
    if any(isinstance(e, CheckResolved) and e.reason == save and e.result.success for e in mine):
        return MissReason.SAVED
    if any(isinstance(e, DamageTaken) and e.total == 0 for e in mine):
        return MissReason.NO_HARM
    if any(isinstance(e, HpPoolEffect) for e in all_effects(spell.effects)):
        return MissReason.POOL
    return MissReason.UNTOUCHED


def _area(state: GameState, spell: SpellDef, cast: SpellCast) -> tuple[str, ...]:
    enc = state.encounter
    zone = cast.target_zone
    if zone is None and enc is not None and cast.caster_id in enc.combatants:
        zone = enc.combatant(cast.caster_id).zone_id
    if zone is None:
        return ()
    found = area_creatures(state, zone, spell.targeting.area or "zone", {cast.caster_id})
    return tuple(c for c in found if state.creatures[c].hp > 0)


def area_misses(
    state: GameState, spell: SpellDef, cast: SpellCast, events: Sequence[AnyEvent]
) -> tuple[AreaMiss, ...]:
    if spell.targeting.kind != "area" or cast.at_scene:
        return ()
    span = _span(cast, events)
    touched = {_who(e) for e in span if not isinstance(e, _LOG_ONLY)}
    touched |= {_who(e) for e in span if isinstance(e, DamageTaken) and e.total > 0}
    out: list[AreaMiss] = []
    for cid in _area(state, spell, cast):
        if cid in touched:
            continue
        if not spell_can_affect(state.creatures[cid], spell.targeting):
            out.append(AreaMiss(cid, MissReason.EXCLUDED, _excluded(state, spell, cid)))
        else:
            out.append(AreaMiss(cid, _reason(spell, cid, span)))
    return tuple(out)
