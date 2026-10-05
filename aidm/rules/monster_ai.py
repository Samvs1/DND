"""Monster AI (M3.10, SPEC 7.4 Monster AI): value-based turns and legendary actions.

`next_monster_command(state, monster_id, regs, rng)` is the next command of the monster's open
turn; `choose_monster_turn` chains those steps over projected dry runs into the whole plan. The
caller executes one command at a time and asks again after each (re-planning on the real state);
every command returned is valid in the state it was planned for (`rules.ai_plan`). Order:
1. Morale: a broken creature retreats (`is_broken`: below a quarter of its HP, not undead,
   construct, ooze or plant, not mindless (INT <= 2), not legendary and not its side's leader,
   i.e. the creature worth the most XP on its side, so a lone monster never flees). It moves to
   an enemy-free zone and Flees (withdraws as FLED); cornered, it fights on.
2. A prone monster stands up when its movement allows.
3. With its action: the best catalog option (attacks, multiattack routines focused with a spill
   target, save actions and breath weapons aimed at zones that spare allies, spells) from its
   zone or any zone it can reach, scored by expected damage, kill chance, target threat,
   concentration breaking and control (`rules.ai_options`, `rules.ai_view`); brutes close in,
   ranged and caster monsters value high ground and cover and avoid zones with enemies.
   Nothing in reach: approach (move closer, then Dash). Nothing at all: Dodge.
4. Bonus action spells from its kit, if any are worth it. After a Dash, keep closing in.
5. A ranged monster that ends up sharing a zone with an enemy steps away.
6. End the turn.
Determinism: candidates are scored and ordered deterministically; exact ties use the injected RNG.

Legendary actions: `choose_legendary_action(state, monster_id, regs) -> LegendaryPick | None`
(call for each id of `rules.monster_legendary.legendary_ready` after a `TurnEnded`): the best
legendary option affordable with the points left, validated with a dry run of
`legendary_action`; None when nothing is worth it.

Public API: `next_monster_command`, `choose_monster_turn`, `is_broken`, `LegendaryPick(monster_id,
action, target_ids, target_zone, value)`, `choose_legendary_action`.
"""

from dataclasses import dataclass

from aidm.data.combat_data import CombatRegistries
from aidm.models.abilities import Ability
from aidm.models.commands import AnyCommand, DodgeCommand, EndTurnCommand, MonsterActionCommand
from aidm.models.state import Creature, GameState
from aidm.rules.ai_options import AiChoice, monster_choices, prefers_range
from aidm.rules.ai_plan import (
    MIN_VALUE,
    Chooser,
    ProbeRng,
    approach_step,
    best_action_step,
    dry_run,
    plan_turn,
    reposition_step,
    retreat_step,
    stand_step,
)
from aidm.rules.ai_view import AiView, ai_view
from aidm.rules.command_checks import CommandRefused
from aidm.rules.dice import Rng
from aidm.rules.monster_keys import LEGENDARY_KEY
from aidm.rules.monster_legendary import legendary_action
from aidm.rules.monster_stats import creature_type_of

BROKEN_FRACTION = 0.25
_FEARLESS_TYPES = frozenset({"undead", "construct", "ooze", "plant"})
_MINDLESS_INT = 2


def _has_block(creature: Creature, regs: CombatRegistries) -> bool:
    index = creature.monster_index
    return index is not None and regs.monsters.find(index) is not None


def _leader(state: GameState, creature_id: str) -> bool:
    enc = state.encounter
    if enc is None:
        return True
    me = enc.combatant(creature_id)
    others = [c.xp for cid, c in enc.combatants.items() if c.side is me.side and cid != creature_id]
    return all(me.xp > xp for xp in others)


def is_broken(state: GameState, creature_id: str) -> bool:
    creature = state.creatures[creature_id]
    if creature.pc is not None or creature.dead or creature.hp * 4 >= creature.max_hp:
        return False
    if creature_type_of(creature) in _FEARLESS_TYPES:
        return False
    if creature.abilities[Ability.INT] <= _MINDLESS_INT or LEGENDARY_KEY in creature.resources:
        return False
    return not _leader(state, creature_id)


def _choices(regs: CombatRegistries, casting: str = "action") -> Chooser:
    def choose(state: GameState, view: AiView) -> list[AiChoice]:
        if not _has_block(state.creatures[view.actor_id], regs):
            return []
        return monster_choices(state, view, regs, casting=casting)

    return choose


def _open_turn(state: GameState, creature_id: str) -> bool:
    enc = state.encounter
    return enc is not None and enc.active_id() == creature_id


def _action_steps(
    state: GameState, view: AiView, regs: CombatRegistries, rng: Rng
) -> AnyCommand | None:
    ranged = _has_block(state.creatures[view.actor_id], regs) and prefers_range(
        state, view.actor_id, regs
    )
    step = best_action_step(state, view, regs, rng, _choices(regs), ranged=ranged)
    if step is not None:
        return step
    step = approach_step(state, view, regs)
    if step is not None:
        return step
    dodge = DodgeCommand(actor_id=view.actor_id)
    return dodge if view.enemies and dry_run(state, dodge, regs) is not None else None


def next_monster_command(
    state: GameState, monster_id: str, regs: CombatRegistries, rng: Rng
) -> AnyCommand | None:
    if not _open_turn(state, monster_id):
        return None
    view = ai_view(state, monster_id, regs)
    end = EndTurnCommand(actor_id=monster_id)
    creature = state.creatures[monster_id]
    enc = state.encounter
    if view is None or enc is None or creature.hp <= 0:
        return end
    combatant = enc.combatant(monster_id)
    if combatant.withdrawn is not None:
        return end
    economy = combatant.economy
    if is_broken(state, monster_id) and (step := retreat_step(state, view, regs)) is not None:
        return step
    if (step := stand_step(state, view, regs)) is not None:
        return step
    if economy.action and (step := _action_steps(state, view, regs, rng)) is not None:
        return step
    if economy.bonus_action and _has_block(creature, regs):
        bonus = best_action_step(
            state, view, regs, rng, _choices(regs, "bonus_action"), ranged=False, move=False
        )
        if bonus is not None:
            return bonus
    ranged = _has_block(creature, regs) and prefers_range(state, monster_id, regs)
    if economy.dashed and (step := approach_step(state, view, regs)) is not None:
        return step
    return reposition_step(state, view, regs, ranged=ranged) or end


def choose_monster_turn(
    state: GameState, monster_id: str, regs: CombatRegistries, rng: Rng
) -> list[AnyCommand]:
    return plan_turn(state, monster_id, regs, rng, next_monster_command)


@dataclass(frozen=True)
class LegendaryPick:
    monster_id: str
    action: str
    target_ids: tuple[str, ...]
    target_zone: str | None
    value: float


def choose_legendary_action(
    state: GameState, monster_id: str, regs: CombatRegistries
) -> LegendaryPick | None:
    view = ai_view(state, monster_id, regs)
    if view is None or not _has_block(state.creatures[monster_id], regs):
        return None
    choices = monster_choices(state, view, regs, legendary=True)
    for choice in sorted(choices, key=lambda c: (-c.value, c.label)):
        cmd = choice.command
        if choice.value <= MIN_VALUE or not isinstance(cmd, MonsterActionCommand):
            break
        try:
            legendary_action(
                state, monster_id, cmd.action, cmd.target_ids, cmd.target_zone, regs, ProbeRng()
            )
        except CommandRefused:
            continue
        return LegendaryPick(monster_id, cmd.action, cmd.target_ids, cmd.target_zone, choice.value)
    return None
