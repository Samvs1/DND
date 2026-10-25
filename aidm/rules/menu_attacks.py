"""Fight menu entries that strike or touch a creature (M36.2, SPEC 6.2). Pure.

- One attack entry per attack the sheet lists (main hand, off hand as a bonus action, ranged,
  unarmed), keyed by the item (`attack:longsword`, `offhand:dagger`, `attack:unarmed`), and one per
  stowed weapon the hero carries (`attack:rapier`, drawn for free first: `draw`).
- `throw` (any object, improvised) and `throw:<item>` for each carried weapon with the thrown
  property.
Targets come from the real commands (`menu_probe.probe_targets`). A foe out of reach is never
hidden: it is an approach target ("moves 15 ft first") when the movement left gets the hero in
reach (`rules.approach`), else "out of reach this turn". Never a swap to another weapon.

Public API: `attack_entries(view) -> list[MenuEntry]` (attacks, stowed weapons, throws),
`drawn_state(state, actor_id, item, regs)` (the state with a stowed weapon drawn).
"""

from aidm.data.character_data import CharacterRegistries
from aidm.models.action_menu import ActionKind, EntryCost, MenuEntry
from aidm.models.combat import AttackProfile
from aidm.models.commands import AnyCommand, AttackCommand, ThrowCommand
from aidm.models.sheet import AttackLine
from aidm.models.state import GameState
from aidm.models.world_events import EquipmentChanged
from aidm.rules.approach import profile_band
from aidm.rules.attack_profiles import UNARMED_KEY, attack_options, throw_profile
from aidm.rules.equipment import EquipRefused, draw_events
from aidm.rules.hit_chance import hit_chance
from aidm.rules.menu_labels import strike_label
from aidm.rules.menu_probe import Reach, probe_targets, ready_state
from aidm.rules.menu_view import FightView, aim_of, chance_notes, is_spent
from aidm.rules.weapon_attacks import attack_lines

_OFF_HAND = "off_hand"


def _attack_id(line: AttackLine, taken: set[str]) -> str:
    prefix = "offhand" if line.hand == _OFF_HAND else "attack"
    base = f"{prefix}:{line.item or UNARMED_KEY}"
    return base if base not in taken else f"{base}:{line.hand.replace('_', '-')}"


def _one_target_chance(view: FightView, reach: Reach, notes: dict[str, str]) -> str:
    near = (*reach.ready, *reach.approach)
    if len(reach.listed) != 1 or len(near) != 1:
        return ""
    name = view.state.creatures[near[0]].name
    return f"{notes[near[0]]} vs {name}"


def _strike_reach(
    view: FightView, base: GameState, profile: AttackProfile
) -> tuple[Reach, dict[str, str]] | None:
    """The reach and hit-chance notes of one attack option against every foe."""

    def command(cid: str) -> AnyCommand:
        return AttackCommand(actor_id=view.actor_id, target_id=cid, option=profile.key)

    ready = ready_state(base, view.actor_id)
    reach = probe_targets(
        ready, view.actor_id, view.foes, command, view.regs, profile_band(profile), True
    )
    if not reach.listed:
        return None
    feats = view.regs.chars.features

    def chance(state: GameState, cid: str) -> float:
        return hit_chance(state, view.actor_id, cid, profile, feats).probability

    return reach, chance_notes(view, reach, chance)


def _weapon_entry(
    view: FightView,
    base: GameState,
    line: AttackLine,
    profile: AttackProfile,
    entry_id: str,
    draw: str | None = None,
) -> MenuEntry | None:
    found = _strike_reach(view, base, profile)
    if found is None:
        return None
    reach, notes = found
    aim = aim_of(reach, notes)
    cost: EntryCost = "bonus" if line.hand == _OFF_HAND else "attack"
    chance = _one_target_chance(view, reach, notes)
    return MenuEntry(
        id=entry_id,
        kind=ActionKind.ATTACK,
        label=strike_label(line.name, line.range_band, line.damage, chance, draw is not None),
        target_ids=aim.target_ids,
        max_targets=1,
        cost=cost,
        spent=is_spent(view, cost),
        note="draws first" if draw else "",
        target_notes=aim.notes,
        approach=aim.approach,
        far=aim.far,
        option=line.hand,
        item=line.item,
        draw=draw,
    )


def drawn_state(
    state: GameState, actor_id: str, item: str, regs: CharacterRegistries
) -> GameState | None:
    """The state with the stowed weapon `item` drawn (None: it cannot be drawn)."""
    creature = state.creatures[actor_id]
    try:
        events = draw_events(creature, item, regs)
    except EquipRefused:
        return None
    changed = next((e for e in events if isinstance(e, EquipmentChanged)), None)
    if changed is None or creature.pc is None:
        return state if not events else None
    pc = creature.pc.model_copy(update={"equipped": changed.equipped})
    creatures = dict(state.creatures)
    creatures[actor_id] = creature.model_copy(update={"pc": pc})
    return state.model_copy(update={"creatures": creatures})


def _drawn_state(view: FightView, item: str) -> GameState | None:
    return drawn_state(view.state, view.actor_id, item, view.regs.chars)


def _stowed_entries(view: FightView, taken: set[str]) -> list[MenuEntry]:
    out: list[MenuEntry] = []
    equipment = view.regs.chars.equipment
    for row in view.sheet.inventory:
        entry = equipment.find(row.item)
        if entry is None or entry.weapon_category is None or row.equipped_slot or row.qty < 1:
            continue
        entry_id = f"attack:{row.item}"
        drawn = _drawn_state(view, row.item)
        if entry_id in taken or drawn is None:
            continue
        hero = drawn.creatures[view.actor_id]
        lines = [x for x in attack_lines(hero, view.regs.chars) if x.item == row.item]
        profiles = {p.key: p for p in attack_options(hero, view.regs.chars)}
        line = next((x for x in lines if x.hand != _OFF_HAND), None)
        if line is None or line.hand not in profiles:
            continue
        made = _weapon_entry(view, drawn, line, profiles[line.hand], entry_id, row.item)
        if made is not None:
            out.append(made)
            taken.add(entry_id)
    return out


def attack_entries(view: FightView) -> list[MenuEntry]:
    hero = view.state.creatures[view.actor_id]
    profiles = {p.key: p for p in attack_options(hero, view.regs.chars)}
    out: list[MenuEntry] = []
    taken: set[str] = set()
    for line in view.sheet.attacks:
        profile = profiles.get(line.hand)
        if profile is None:
            continue
        entry_id = _attack_id(line, taken)
        made = _weapon_entry(view, view.state, line, profile, entry_id)
        if made is not None:
            out.append(made)
            taken.add(entry_id)
    out.extend(_stowed_entries(view, taken))
    out.extend(_throw_entries(view))
    return out


def _throw_entry(view: FightView, item: str | None) -> MenuEntry | None:
    hero = view.state.creatures[view.actor_id]
    weapon = view.regs.chars.equipment.find(item) if item else None
    profile = throw_profile(hero, weapon, view.regs.chars)

    def command(cid: str) -> AnyCommand:
        return ThrowCommand(actor_id=view.actor_id, target_id=cid, item=item)

    reach = probe_targets(view.ready, view.actor_id, view.foes, command, view.regs)
    if not reach.listed:
        return None
    feats = view.regs.chars.features

    def chance(state: GameState, cid: str) -> float:
        return hit_chance(state, view.actor_id, cid, profile, feats).probability

    notes = chance_notes(view, reach, chance)
    aim = aim_of(reach, notes)
    label = strike_label(
        profile.name, "thrown", profile.damage, _one_target_chance(view, reach, notes)
    )
    return MenuEntry(
        id=f"throw:{item}" if item else "throw",
        kind=ActionKind.THROW,
        label=label,
        target_ids=aim.target_ids,
        max_targets=1,
        spent=is_spent(view, "action"),
        target_notes=aim.notes,
        item=item,
    )


def _throw_entries(view: FightView) -> list[MenuEntry]:
    out = [e for e in [_throw_entry(view, None)] if e is not None]
    equipment = view.regs.chars.equipment
    for row in view.sheet.inventory:
        weapon = equipment.find(row.item)
        thrown = weapon is not None and any(p.index == "thrown" for p in weapon.properties)
        if thrown and row.qty > 0 and (made := _throw_entry(view, row.item)) is not None:
            out.append(made)
    return out
