"""Fight menu entries for spells and class or race features (M36.2, SPEC 6.2). Pure.

- `cast:<spell>`: every spell the hero can cast now (a ready cantrip, or a ready leveled spell
  with a slot of its level or higher; `slot_level` is the lowest such slot). Aimed by the spell's
  own data: no target (self, or an area around the hero), a zone (an aimed area or point, or a
  self cone), or creatures (up to the sheet's `target_count`): every creature the cast accepts,
  foes first for a hostile spell (`spell_targets.strikes_creatures`), else the hero and the
  allies first (charming an ally or healing a foe is possible). A creature out of range that
  the movement left brings in range is an approach target; attack-roll spells note the hit chance.
- `feature:<name>`: every feature action with uses left (Second Wind, Action Surge, Turn Undead,
  Breath Weapon ...), aimed the same way through the hook's pseudo spell
  (`feature_commands.ability_spell`). An area around the hero names who it would reach, from the
  real command's `FeatureUsed` targets ("undead nearby: Cantor Ashmere Voll").

Public API: `spell_entries(view)`, `feature_entries(view)`, `needs_of(spell)`,
`lowest_slot(block, level)` (the lowest slot level with a slot left, and how many are left).
"""

from collections.abc import Callable
from typing import Literal

from aidm.data.feature_hooks import ActiveAbilityHook
from aidm.data.spell_defs import SpellDef
from aidm.models.action_menu import ActionKind, EntryCost, MenuEntry
from aidm.models.combat_events import FeatureUsed
from aidm.models.commands import AnyCommand, CastCommand, FeatureActionCommand
from aidm.models.sheet import FeatureActionLine, SpellcastingBlock, SpellLine
from aidm.models.state import GameState
from aidm.rules.feature_commands import ability_spell
from aidm.rules.features import command_hook
from aidm.rules.hit_chance import hit_chance
from aidm.rules.menu_labels import area_words, feature_label, spell_label
from aidm.rules.menu_probe import Reach, accepted, probe_targets
from aidm.rules.menu_view import FightView, aim_of, chance_notes, is_spent, slug
from aidm.rules.spell_chances import SPELL_OPTION_PREFIX, spell_attack_options
from aidm.rules.spell_targets import spell_band, strikes_creatures

type Needs = Literal["none", "zone", "creature"]
type Build = Callable[[tuple[str, ...], str | None], AnyCommand]
_COSTS: dict[str, EntryCost] = {
    "action": "action",
    "bonus_action": "bonus",
    "extra_action": "extra",
}


def needs_of(spell: SpellDef) -> Needs:
    kind = spell.targeting.kind
    if kind in ("creature", "creatures"):
        return "creature"
    if kind == "self" or (spell.range.kind == "self" and spell.targeting.shape is None):
        return "none"
    return "zone"


def _aim_reach(view: FightView, spell: SpellDef, build: Build) -> Reach | None:
    needs = needs_of(spell)
    if needs == "none":
        return Reach() if accepted(view.ready, build((), None), view.regs) is not None else None
    if needs == "zone":
        zones = [z.id for z in view.encounter.zone_map.zones]
        reach = probe_targets(view.ready, view.actor_id, zones, lambda z: build((), z), view.regs)
    else:
        party = (view.actor_id, *view.allies)
        candidates = (*view.foes, *party) if strikes_creatures(spell) else (*party, *view.foes)
        reach = probe_targets(
            view.ready,
            view.actor_id,
            candidates,
            lambda cid: build((cid,), None),
            view.regs,
            spell_band(spell),
        )
    return reach if reach.listed else None


def lowest_slot(block: SpellcastingBlock, level: int) -> tuple[int, int] | None:
    """(lowest slot level >= `level` with a slot left, slots left at that level)."""
    for group in block.levels:
        left = sum(s.current for s in group.slots)
        if group.level >= level and left > 0:
            return group.level, left
    return None


def _spell_entry(view: FightView, line: SpellLine, block: SpellcastingBlock) -> MenuEntry | None:
    spell = view.regs.spells.find(line.index)
    slot = lowest_slot(block, line.level) if line.level > 0 and line.resource is None else None
    if spell is None or (line.level > 0 and line.resource is None and slot is None):
        return None
    slot_level = slot[0] if slot is not None else None

    def build(ids: tuple[str, ...], zone: str | None) -> AnyCommand:
        return CastCommand(
            actor_id=view.actor_id, spell_id=spell.index, target_ids=ids, target_zone=zone
        )

    reach = _aim_reach(view, spell, build)
    if reach is None:
        return None
    hero = view.state.creatures[view.actor_id]
    key = f"{SPELL_OPTION_PREFIX}{spell.index}"
    profiles = spell_attack_options(hero, view.regs.chars, view.regs.spells)
    profile = next((p for p in profiles if p.key == key), None)
    feats = view.regs.chars.features

    def chance(state: GameState, cid: str) -> float | None:
        if profile is None:
            return None
        return hit_chance(state, view.actor_id, cid, profile, feats).probability

    aim = aim_of(reach, chance_notes(view, reach, chance))
    cost: EntryCost = "bonus" if spell.casting_time == "bonus_action" else "action"
    needs = needs_of(spell)
    return MenuEntry(
        id=f"cast:{spell.index}",
        kind=ActionKind.CAST,
        label=spell_label(spell, line, slot[1] if slot is not None else None),
        target_ids=aim.target_ids,
        max_targets=0 if needs == "none" else (line.target_count if needs == "creature" else 1),
        cost=cost,
        spent=is_spent(view, cost),
        target_notes=aim.notes,
        approach=aim.approach,
        spell_id=spell.index,
        slot_level=slot_level,
    )


def spell_entries(view: FightView) -> list[MenuEntry]:
    block = view.sheet.spellcasting
    if block is None:
        return []
    lines = [*block.cantrips, *(s for g in block.levels for s in g.spells)]
    out: list[MenuEntry] = []
    for line in lines:
        if not line.prepared:
            continue
        made = _spell_entry(view, line, block)
        if made is not None:
            out.append(made)
    return out


def _reached_names(view: FightView, build: Build) -> list[str]:
    events = accepted(view.ready, build((), None), view.regs) or []
    used = next((e for e in events if isinstance(e, FeatureUsed)), None)
    targets = used.target_ids if used is not None else ()
    return [view.state.creatures[cid].name for cid in targets if cid in view.state.creatures]


def _area_words(view: FightView, hook: ActiveAbilityHook, build: Build) -> list[str]:
    kinds = "/".join(hook.targeting.creature_types) or "creatures"
    where = area_words(hook.targeting.area)
    names = _reached_names(view, build)
    if not names:
        return [f"no {kinds} {where}"]
    return [f"{kinds} {where}: {', '.join(names)}"]


def _feature_entry(view: FightView, line: FeatureActionLine, entry_id: str) -> MenuEntry | None:
    hero = view.state.creatures[view.actor_id]
    hook = command_hook(hero, view.regs.chars.features, line.feature)

    def build(ids: tuple[str, ...], zone: str | None) -> AnyCommand:
        return FeatureActionCommand(
            actor_id=view.actor_id, feature_id=line.feature, target_ids=ids, target_zone=zone
        )

    extra: list[str] = []
    reach: Reach | None = Reach()
    max_targets = 0
    if isinstance(hook, ActiveAbilityHook):
        spell = ability_spell(hook, line.feature)
        needs = needs_of(spell)
        if needs == "none":
            extra = _area_words(view, hook, build) if spell.targeting.kind == "area" else []
        else:
            reach = _aim_reach(view, spell, build)
            max_targets = spell.targeting.count if needs == "creature" else 1
    elif line.economy == "extra_action" and view.economy.action:
        extra = ["after your action"]
    if reach is None:
        return None
    aim = aim_of(reach)
    cost = _COSTS.get(line.economy, "action")
    return MenuEntry(
        id=entry_id,
        kind=ActionKind.FEATURE,
        label=feature_label(line, extra),
        target_ids=aim.target_ids,
        max_targets=max_targets,
        cost=cost,
        spent=is_spent(view, cost),
        target_notes=aim.notes,
        approach=aim.approach,
        feature_id=line.feature,
    )


def feature_entries(view: FightView) -> list[MenuEntry]:
    out: list[MenuEntry] = []
    taken: set[str] = set()
    for line in view.sheet.feature_actions:
        if not line.available:
            continue
        entry_id = f"feature:{slug(line.name)}"
        if entry_id in taken:
            entry_id = f"feature:{line.feature}"
        made = _feature_entry(view, line, entry_id)
        if made is not None:
            out.append(made)
            taken.add(entry_id)
    return out
