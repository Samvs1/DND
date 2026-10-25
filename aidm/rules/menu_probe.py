"""Which targets an action accepts, asked of the real commands (M36.2, SPEC 6.2). Pure.

The fight menu never keeps a second copy of targeting or range rules: every candidate target is
tried with the very command the button sends (`rules.commands.execute_command` on a probe RNG,
nothing applied). The probe runs on `ready_state`: the hero's action and bonus action counted as
unused, so an entry whose economy is spent still lists its targets (the menu marks it `spent`
and the rules answer it plainly when chosen).

A target refused only for range is tried again after the walk `rules.approach.plan_into_band`
plans (when a band is given): accepted there, it is an approach target (feet walked first);
otherwise, when asked (`keep_far`, melee strikes), it stays as out of reach this turn.

Public API:
- `ready_state(state, actor_id) -> GameState`.
- `refusal(state, command, regs) -> RefusalCode | None` (None: the rules accept it).
- `accepted(state, command, regs) -> list[AnyEvent] | None` (the events of an accepted command).
- `walk(state, moves, regs) -> GameState | None`: the state after the moves (None: refused).
- `Reach(ready, approach, after, far)`; `probe_targets(state, actor_id, candidates, build, regs,
  band=None, keep_far=False) -> Reach`.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from aidm.data.combat_data import CombatRegistries
from aidm.models.commands import AnyCommand, MoveCommand, RefusalCode
from aidm.models.events import AnyEvent
from aidm.models.state import GameState
from aidm.models.zones import RangeBand
from aidm.rules.ai_plan import ProbeRng
from aidm.rules.approach import plan_into_band
from aidm.rules.command_checks import CommandRefused
from aidm.rules.commands import execute_command
from aidm.rules.projection import project_state

_PROBE = ProbeRng()


def ready_state(state: GameState, actor_id: str) -> GameState:
    enc = state.encounter
    if enc is None or actor_id not in enc.combatants:
        return state
    combatant = enc.combatants[actor_id]
    economy = combatant.economy.model_copy(update={"action": True, "bonus_action": True})
    combatants = dict(enc.combatants)
    combatants[actor_id] = combatant.model_copy(update={"economy": economy})
    encounter = enc.model_copy(update={"combatants": combatants})
    return state.model_copy(update={"encounter": encounter})


def accepted(
    state: GameState, command: AnyCommand, regs: CombatRegistries
) -> list[AnyEvent] | None:
    try:
        return execute_command(state, command, regs, _PROBE)
    except CommandRefused:
        return None


def refusal(state: GameState, command: AnyCommand, regs: CombatRegistries) -> RefusalCode | None:
    try:
        execute_command(state, command, regs, _PROBE)
    except CommandRefused as refused:
        return refused.code
    return None


def walk(
    state: GameState, moves: Sequence[MoveCommand], regs: CombatRegistries
) -> GameState | None:
    for move in moves:
        events = accepted(state, move, regs)
        if events is None:
            return None
        state = project_state(state, events)
    return state


@dataclass(frozen=True)
class Reach:
    ready: tuple[str, ...] = ()
    approach: dict[str, int] = field(default_factory=dict[str, int])
    after: dict[str, GameState] = field(default_factory=dict[str, GameState])
    far: tuple[str, ...] = ()

    @property
    def listed(self) -> tuple[str, ...]:
        return (*self.ready, *self.approach, *self.far)


def _after_walk(
    state: GameState,
    actor_id: str,
    target_id: str,
    command: AnyCommand,
    band: RangeBand,
    regs: CombatRegistries,
) -> tuple[int, GameState] | None:
    plan = plan_into_band(state, actor_id, target_id, band, regs)
    if plan is None or not plan.moves:
        return None
    after = walk(state, plan.moves, regs)
    if after is None or refusal(after, command, regs) is not None:
        return None
    return plan.feet, after


def probe_targets(
    state: GameState,
    actor_id: str,
    candidates: Sequence[str],
    build: Callable[[str], AnyCommand],
    regs: CombatRegistries,
    band: RangeBand | None = None,
    keep_far: bool = False,
) -> Reach:
    ready: list[str] = []
    far: list[str] = []
    approach: dict[str, int] = {}
    after: dict[str, GameState] = {}
    for cid in candidates:
        command = build(cid)
        code = refusal(state, command, regs)
        if code is None:
            ready.append(cid)
            continue
        if code is not RefusalCode.OUT_OF_RANGE or band is None:
            continue
        walked = _after_walk(state, actor_id, cid, command, band, regs)
        if walked is not None:
            approach[cid], after[cid] = walked
        elif keep_far:
            far.append(cid)
    return Reach(ready=tuple(ready), approach=approach, after=after, far=tuple(far))
