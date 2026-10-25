"""Concentration (SRD 5.1 "Concentration"): one effect at a time, checked on damage.

Public API:
- `CONCENTRATION_MIN_DC` (10); `concentration_dc(damage) -> int`: max(10, damage // 2).
- `start_concentration(state, caster_id, spell_id, links=()) -> list[AnyEvent]`: ends any current
  concentration first (its linked conditions are removed), then `ConcentrationStarted`.
  `links` name the conditions the caster applied (with `source_id` = caster) that end with it.
- `end_concentration(state, caster_id, reason) -> list[AnyEvent]`: `ConcentrationEnded` first
  (M35.3: so the orphan check below never fires half way through), then `ConditionRemoved`
  (exact source = the caster) for each linked condition still present on an existing creature
  and the removal of every zone surface the caster keeps up with concentration. Nothing when
  the caster is not concentrating.
- `concentration_after_damage(rng, state, damage, *, adv_sources=0, dis_sources=0, bonus=0)
  -> list[AnyEvent]`: call with the state AFTER the `resolve_damage` events were applied and the
  `DamageTaken` event they began with. A dead or incapacitated concentrator loses concentration
  without a roll; otherwise damage > 0 forces a Constitution save (`save_with_conditions`,
  logged as `CheckResolved`) against `concentration_dc(damage.total)`; failure ends it. One call
  per damage instance (SRD: separate saves for each source of damage).
- `concentration_upkeep(state, creature_id) -> list[AnyEvent]`: ends concentration when the
  creature is dead or incapacitated (call after a condition such as stunned is applied).
- `orphaned_concentration_events(state) -> list[AnyEvent]` (M35.3, round 6 Y3): a
  `ConcentrationEnded` for every creature whose concentration linked conditions and none of
  them is still present (used up, expired, saved off or removed on every target) and that keeps
  no concentration surface up. A concentration without links (a surface, a summons) is left
  alone. The session runs it after every applied batch (`TableCore.apply_all`, the combat
  runner), so it covers every way a condition ends.
"""

from collections.abc import Sequence

from aidm.models.abilities import Ability
from aidm.models.conditions import Concentration, ConditionLink
from aidm.models.events import (
    AnyEvent,
    CheckResolved,
    ConcentrationEnded,
    ConcentrationStarted,
    ConditionRemoved,
    DamageTaken,
)
from aidm.models.state import GameState
from aidm.rules.conditions import is_incapacitated, save_with_conditions
from aidm.rules.dice import Rng
from aidm.rules.surface_state import concentration_surface_events

CONCENTRATION_MIN_DC = 10


def concentration_dc(damage: int) -> int:
    if damage < 0:
        raise ValueError("damage must be >= 0")
    return max(CONCENTRATION_MIN_DC, damage // 2)


def _link_alive(state: GameState, caster_id: str, link: ConditionLink) -> bool:
    target = state.creatures.get(link.creature_id)
    if target is None:
        return False
    return any((c.name, c.source_id) == (link.name, caster_id) for c in target.conditions)


def end_concentration(state: GameState, caster_id: str, reason: str) -> list[AnyEvent]:
    caster = state.creatures.get(caster_id)
    if caster is None or caster.concentrating_on is None:
        return []
    spell_id = caster.concentrating_on.spell_id
    events: list[AnyEvent] = [
        ConcentrationEnded(creature_id=caster_id, spell_id=spell_id, reason=reason)
    ]
    for link in caster.concentrating_on.links:
        if _link_alive(state, caster_id, link):
            events.append(
                ConditionRemoved(
                    creature_id=link.creature_id,
                    name=link.name,
                    source_id=caster_id,
                    exact_source=True,
                )
            )
    events.extend(concentration_surface_events(state, caster_id))
    return events


def orphaned_concentration_events(state: GameState) -> list[AnyEvent]:
    events: list[AnyEvent] = []
    for creature in state.creatures.values():
        held = creature.concentrating_on
        if held is None or not held.links:
            continue
        if any(_link_alive(state, creature.id, link) for link in held.links):
            continue
        if concentration_surface_events(state, creature.id):
            continue
        events.extend(end_concentration(state, creature.id, "its last effect ended"))
    return events


def start_concentration(
    state: GameState, caster_id: str, spell_id: str, links: Sequence[ConditionLink] = ()
) -> list[AnyEvent]:
    if caster_id not in state.creatures:
        raise ValueError(f"unknown creature id {caster_id!r}")
    events = end_concentration(state, caster_id, f"started {spell_id}")
    concentration = Concentration(spell_id=spell_id, links=tuple(links))
    events.append(ConcentrationStarted(creature_id=caster_id, concentration=concentration))
    return events


def concentration_upkeep(state: GameState, creature_id: str) -> list[AnyEvent]:
    creature = state.creatures.get(creature_id)
    if creature is None or creature.concentrating_on is None:
        return []
    if creature.dead:
        return end_concentration(state, creature_id, "died")
    if is_incapacitated(creature):
        return end_concentration(state, creature_id, "incapacitated")
    return []


def concentration_after_damage(
    rng: Rng,
    state: GameState,
    damage: DamageTaken,
    *,
    adv_sources: int = 0,
    dis_sources: int = 0,
    bonus: int = 0,
) -> list[AnyEvent]:
    creature = state.creatures.get(damage.creature_id)
    if creature is None or creature.concentrating_on is None:
        return []
    broken = concentration_upkeep(state, creature.id)
    if broken or damage.total <= 0:
        return broken
    dc = concentration_dc(damage.total)
    result = save_with_conditions(
        rng,
        creature,
        Ability.CON,
        dc,
        adv_sources=adv_sources,
        dis_sources=dis_sources,
        bonus=bonus,
    )
    spell = creature.concentrating_on.spell_id
    events: list[AnyEvent] = [
        CheckResolved(creature_id=creature.id, result=result, reason=f"concentration {spell}")
    ]
    if not result.success:
        events.extend(end_concentration(state, creature.id, "failed concentration save"))
    return events
