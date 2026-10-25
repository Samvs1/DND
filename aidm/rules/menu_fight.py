"""The fight menu: everything a hero can do on their own turn (M36.2, SPEC 6.2). Pure.

Built from the hotbar's own sources (the sheet, attack options, spellcasting, feature actions,
fight gear, hit chances) and probed with the real commands (`menu_probe`), never a second copy of
range, targeting or hit-chance rules. Entry order: attacks and throws, spells, features, items,
then touch actions (help, shove), movement, the standard actions and the closing ones (flee,
surrender, end turn). Targets: every standing combatant (foes first, then allies, then the hero)
and every zone, each labelled for a model choosing ("Kobold A, 15 ft, unhurt"); M36.9: a zone's
label names the creatures standing in it ("Archway (Zombie A), 25 ft"), so an area spell can be
aimed by creature.

Public API: `fight_menu(state, actor_id, regs) -> ActionMenu` (the actor's turn must be open).
"""

from aidm.data.combat_data import CombatRegistries
from aidm.models.action_menu import ActionMenu, MenuScope, MenuTarget, TargetKind
from aidm.models.state import GameState
from aidm.rules.menu_attacks import attack_entries
from aidm.rules.menu_gear import item_entries
from aidm.rules.menu_labels import creature_label, zone_label
from aidm.rules.menu_magic import feature_entries, spell_entries
from aidm.rules.menu_moves import move_entries, standard_entries, touch_entries
from aidm.rules.menu_view import FightView, fight_view


def _targets(view: FightView) -> tuple[MenuTarget, ...]:
    out: list[MenuTarget] = []
    standing: dict[str, list[str]] = {}
    groups: tuple[tuple[tuple[str, ...], TargetKind], ...] = (
        (view.foes, "foe"),
        (view.allies, "ally"),
        ((view.actor_id,), "self"),
    )
    for ids, kind in groups:
        for cid in ids:
            creature = view.state.creatures[cid]
            label = creature_label(creature, view.creature_feet(cid))
            out.append(MenuTarget(id=cid, label=label, kind=kind))
            zone_id = view.encounter.combatants[cid].zone_id
            standing.setdefault(zone_id, []).append(creature.name)
    for zone in view.encounter.zone_map.zones:
        label = zone_label(zone.name, view.zone_feet.get(zone.id), standing.get(zone.id, ()))
        out.append(MenuTarget(id=zone.id, label=label, kind="zone"))
    return tuple(out)


def fight_menu(state: GameState, actor_id: str, regs: CombatRegistries) -> ActionMenu:
    view = fight_view(state, actor_id, regs)
    entries = [
        *attack_entries(view),
        *spell_entries(view),
        *feature_entries(view),
        *item_entries(view),
        *touch_entries(view),
        *move_entries(view),
        *standard_entries(view),
    ]
    return ActionMenu(
        scope=MenuScope.FIGHT, actor_id=actor_id, entries=tuple(entries), targets=_targets(view)
    )
