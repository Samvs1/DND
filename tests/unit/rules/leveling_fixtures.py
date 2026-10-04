"""A deterministic level-up choice script for any PC (first legal option everywhere)."""

from __future__ import annotations

from aidm.data.character_data import CharacterRegistries
from aidm.models.abilities import Ability
from aidm.models.events import AnyEvent
from aidm.models.leveling import LevelUpChoices
from aidm.models.state import Creature, GameState
from aidm.rules.creation_checks import class_spell_indexes
from aidm.rules.level_spells import learnable_spells
from aidm.rules.leveling import gain_xp, level_up, xp_for_level
from aidm.rules.spellcasting import cantrips_known_count, spells_known_count
from aidm.session.reducer import apply


def _asi(creature: Creature, primary: Ability) -> dict[Ability, int]:
    if creature.abilities[primary] <= 18:
        return {primary: 2}
    second = Ability.CON if primary is not Ability.CON else Ability.DEX
    return {primary: 1, second: 1}


def _spell_picks(
    creature: Creature, regs: CharacterRegistries, subclass: str | None
) -> tuple[list[str], list[str]]:
    pc = creature.pc
    assert pc is not None
    cls = regs.classes.get(pc.class_index)
    level, casting = pc.level + 1, cls.spellcasting
    if casting is None or level < casting.first_level:
        return [], []
    count = cantrips_known_count(cls, level) - cantrips_known_count(cls, level - 1)
    taken = set(pc.cantrips + pc.race_cantrips)
    pool = sorted(class_spell_indexes(regs.spells, cls.index, 0, 0) - taken)
    cantrips = pool[:count]
    if casting.kind == "prepared":
        n, known = (casting.spellbook_per_level if casting.spellbook_start else 0), pc.spellbook
    else:
        n = spells_known_count(cls, level) - spells_known_count(cls, level - 1)
        known = pc.spells_known
    learnable = learnable_spells(cls, level, [*pc.features, *pc.traits], subclass, regs)
    ranked = sorted(learnable - set(known), key=lambda s: (-regs.spells.get(s).level, s))
    return cantrips, ranked[:n]


def script_choices(creature: Creature, regs: CharacterRegistries) -> LevelUpChoices:
    pc = creature.pc
    assert pc is not None
    cls = regs.classes.get(pc.class_index)
    level = pc.level + 1
    subclass = cls.subclass_index if level == cls.subclass_level else None
    asi = _asi(creature, Ability(cls.primary_abilities[0])) if cls.level(level).asi else {}
    cantrips, spells = _spell_picks(creature, regs, subclass or pc.subclass)
    return LevelUpChoices(
        subclass=subclass,
        class_choices={
            c.id: list(c.pick.options[: c.pick.choose]) for c in cls.choices if c.level == level
        },
        asi=asi,
        cantrips=cantrips,
        spells=spells,
    )


def run_events(state: GameState, events: list[AnyEvent], log: list[AnyEvent]) -> None:
    for event in events:
        apply(state, event)
        log.append(event)


def level_to(
    state: GameState, creature_id: str, target: int, regs: CharacterRegistries, log: list[AnyEvent]
) -> None:
    """Grant the XP for each level and level up with the scripted choices until `target`."""
    while (pc := state.creatures[creature_id].pc) is not None and pc.level < target:
        missing = xp_for_level(pc.level + 1) - pc.xp
        run_events(state, gain_xp(state.creatures[creature_id], max(0, missing)), log)
        creature = state.creatures[creature_id]
        run_events(state, level_up(creature, script_choices(creature, regs), regs), log)
