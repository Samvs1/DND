"""Headless combat driver (M3.11): runs a started encounter to its end with the combat AI.

The loop the table actor will also follow, minus players: for each turn `rules.turns.begin_turn`,
then the acting creature's AI asks for ONE command at a time (`rules.party_ai.next_pc_command`
for PCs, `rules.monster_ai.next_monster_command` for everything else), the command is executed
through `rules.commands.execute_command` and its events are applied by THE reducer, until the AI
ends the turn. After every applied batch `rules.encounter.encounter_outcome` is checked; an
outcome ends the fight through `end_encounter`. After each `TurnEnded`, every monster of
`rules.monster_legendary.legendary_ready` may take the legendary action the AI picks.
The planner only returns commands it validated, so a refusal here is an engine/AI disagreement:
it is counted in `CombatStats.refused` and the turn is ended instead (never a silent stall).
A turn longer than `MAX_COMMANDS` commands is ended too (`forced_ends`).

Public API: `CombatStats`, `CombatRunner(state, regs, rng, on_event=None)` with `.log` (every
applied event), `.stats`, `.run(max_rounds) -> EncounterStatus` (ACTIVE when the round limit
was reached), and the steps the table actor (M6.2) drives one turn at a time: `.execute(command)`
(a refusal ends the turn instead), `.play_turn(creature_id)` (the AI's whole turn) and
`.legendary()` (legendary actions after a turn); `ai_command(state, creature_id, regs, rng)`,
`MAX_COMMANDS`.
"""

from collections.abc import Callable
from dataclasses import dataclass

from aidm.data.combat_data import CombatRegistries
from aidm.models.commands import AnyCommand, EndTurnCommand
from aidm.models.encounter import EncounterStatus
from aidm.models.events import AnyEvent
from aidm.models.state import GameState
from aidm.rules.command_checks import CommandRefused
from aidm.rules.commands import execute_command
from aidm.rules.dice import Rng
from aidm.rules.encounter import encounter_outcome, end_encounter
from aidm.rules.monster_ai import choose_legendary_action, next_monster_command
from aidm.rules.monster_legendary import legendary_action, legendary_ready
from aidm.rules.party_ai import next_pc_command
from aidm.rules.turns import begin_turn, end_turn, next_turn
from aidm.session.reducer import apply

MAX_COMMANDS = 20

type EventHook = Callable[[GameState, AnyEvent], None]


@dataclass
class CombatStats:
    turns: int = 0
    commands: int = 0
    refused: int = 0
    forced_ends: int = 0
    legendary: int = 0


def ai_command(
    state: GameState, creature_id: str, regs: CombatRegistries, rng: Rng
) -> AnyCommand | None:
    if state.creatures[creature_id].pc is not None:
        return next_pc_command(state, creature_id, regs, rng)
    return next_monster_command(state, creature_id, regs, rng)


class CombatRunner:
    def __init__(
        self,
        state: GameState,
        regs: CombatRegistries,
        rng: Rng,
        on_event: EventHook | None = None,
    ) -> None:
        self.state = state
        self.regs = regs
        self.rng = rng
        self.on_event = on_event
        self.log: list[AnyEvent] = []
        self.stats = CombatStats()

    def _apply(self, events: list[AnyEvent]) -> None:
        for event in events:
            apply(self.state, event)
            self.log.append(event)
            if self.on_event is not None:
                self.on_event(self.state, event)

    def execute(self, command: AnyCommand) -> AnyCommand:
        try:
            events = execute_command(self.state, command, self.regs, self.rng)
        except CommandRefused:
            self.stats.refused += 1
            command = EndTurnCommand(actor_id=command.actor_id)
            events = execute_command(self.state, command, self.regs, self.rng)
        self.stats.commands += 1
        self._apply(events)
        return command

    def play_turn(self, creature_id: str) -> None:
        for _ in range(MAX_COMMANDS):
            command = ai_command(self.state, creature_id, self.regs, self.rng)
            if command is None:
                command = EndTurnCommand(actor_id=creature_id)
            done = self.execute(command)
            if isinstance(done, EndTurnCommand) or encounter_outcome(self.state) is not None:
                return
        self.stats.forced_ends += 1
        self._apply(end_turn(self.rng, self.state))

    def legendary(self) -> None:
        for monster_id in legendary_ready(self.state):
            pick = choose_legendary_action(self.state, monster_id, self.regs)
            if pick is None:
                continue
            events = legendary_action(
                self.state,
                monster_id,
                pick.action,
                pick.target_ids,
                pick.target_zone,
                self.regs,
                self.rng,
            )
            self.stats.legendary += 1
            self._apply(events)
            if encounter_outcome(self.state) is not None:
                return

    def run(self, max_rounds: int = 50) -> EncounterStatus:
        while True:
            status = encounter_outcome(self.state)
            if status is not None:
                self._apply(end_encounter(self.state, status))
                return status
            enc = self.state.encounter
            upcoming = next_turn(self.state)
            if enc is None or upcoming is None or upcoming[1] > max_rounds:
                return EncounterStatus.ACTIVE
            self._apply(begin_turn(self.rng, self.state))
            self.stats.turns += 1
            now = self.state.encounter
            active = now.active_id() if now is not None else None
            if active is not None and encounter_outcome(self.state) is None:
                self.play_turn(active)
            if encounter_outcome(self.state) is None:
                self.legendary()
