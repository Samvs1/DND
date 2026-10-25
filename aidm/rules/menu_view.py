"""What the fight menu builders share: the acting hero's view of the fight (M36.2). Pure.

`FightView` gathers once what every entry builder reads: the real state and the probe state
(`menu_probe.ready_state`), the hero's sheet (the hotbar's own source, `rules.sheet.build_sheet`
with the hero's lit light), the real turn economy, the foes (every standing combatant not on the
hero's side), the allies (the hero's side, downed ones included) and the walking feet from the
hero's zone to every zone.

Public API: `FightView`, `fight_view(state, actor_id, regs)`, `is_spent(view, cost)`,
`Aim(target_ids, approach, far, notes)`, `aim_of(reach, notes)`, `chance_notes(view, reach,
chance)`, `slug(text)`.
"""

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

from aidm.data.combat_data import CombatRegistries
from aidm.models.action_menu import EntryCost
from aidm.models.encounter import Combatant, Encounter, TurnEconomy
from aidm.models.sheet import CharacterSheet
from aidm.models.state import GameState
from aidm.rules.light import hero_light
from aidm.rules.menu_labels import chance_note
from aidm.rules.menu_probe import Reach, ready_state
from aidm.rules.sheet import build_sheet
from aidm.rules.zones import reachable_zones

FAR_NOTE = "out of reach this turn"
_EVERYWHERE = 10**6


@dataclass(frozen=True)
class FightView:
    state: GameState
    ready: GameState
    actor_id: str
    regs: CombatRegistries
    sheet: CharacterSheet
    economy: TurnEconomy
    zone_id: str
    foes: tuple[str, ...]
    allies: tuple[str, ...]
    zone_feet: dict[str, int] = field(default_factory=dict[str, int])

    @property
    def encounter(self) -> Encounter:
        enc = self.state.encounter
        if enc is None:
            raise KeyError("no encounter")
        return enc

    def creature_feet(self, creature_id: str) -> int | None:
        combatant = self.encounter.combatants.get(creature_id)
        return self.zone_feet.get(combatant.zone_id) if combatant is not None else None


def _standing(state: GameState, combatant: Combatant) -> bool:
    creature = state.creatures.get(combatant.creature_id)
    return creature is not None and not creature.dead and combatant.withdrawn is None


def fight_view(state: GameState, actor_id: str, regs: CombatRegistries) -> FightView:
    enc = state.encounter
    if enc is None:
        raise KeyError("no encounter")
    me = enc.combatant(actor_id)
    creature = state.creatures[actor_id]
    light = hero_light(state, actor_id)
    sheet = build_sheet(creature, regs.chars, None, light.item if light is not None else None)
    others = [c for c in enc.combatants.values() if c.creature_id != actor_id]
    foes = [c for c in others if c.side is not me.side and _standing(state, c)]
    allies = [c for c in others if c.side is me.side and _standing(state, c)]
    return FightView(
        state=state,
        ready=ready_state(state, actor_id),
        actor_id=actor_id,
        regs=regs,
        sheet=sheet,
        economy=me.economy,
        zone_id=me.zone_id,
        foes=tuple(c.creature_id for c in foes),
        allies=tuple(c.creature_id for c in allies),
        zone_feet=reachable_zones(enc.zone_map, me.zone_id, _EVERYWHERE),
    )


def is_spent(view: FightView, cost: EntryCost) -> bool:
    economy = view.economy
    if cost == "action":
        return not economy.action
    if cost == "attack":
        return not economy.action and economy.attacks_left == 0
    if cost == "bonus":
        return not economy.bonus_action
    if cost == "movement":
        return economy.movement_left == 0
    return False


@dataclass(frozen=True)
class Aim:
    target_ids: tuple[str, ...]
    approach: dict[str, int]
    far: tuple[str, ...]
    notes: dict[str, str]


def aim_of(reach: Reach, notes: Mapping[str, str] | None = None) -> Aim:
    found = dict(notes or {})
    for cid, feet in reach.approach.items():
        found.setdefault(cid, chance_note(None, feet))
    for cid in reach.far:
        found.setdefault(cid, FAR_NOTE)
    kept = {cid: text for cid, text in found.items() if text and cid in reach.listed}
    return Aim(target_ids=reach.listed, approach=dict(reach.approach), far=reach.far, notes=kept)


def chance_notes(
    view: FightView, reach: Reach, chance: Callable[[GameState, str], float | None]
) -> dict[str, str]:
    """Hit chances per target: now for the ready ones, after the walk for the approach ones."""
    notes: dict[str, str] = {}
    for cid in reach.ready:
        notes[cid] = chance_note(chance(view.state, cid), 0)
    for cid, feet in reach.approach.items():
        notes[cid] = chance_note(chance(reach.after[cid], cid), feet)
    return notes


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
