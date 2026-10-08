"""Which of the Scribe's lines he speaks (M13.2): table memory, never game state or events.

`ScribeMemory.pick(lines, seed)` chooses one line of a group with its OWN seeded random
(`random.Random("<campaign seed>:scribe:<pick count>")`), so the dice RNG, the event log and
replay never change; within a group the previous pick is never repeated when the group has
more than one line. `current` is the last line sent (what a host skip stops) and
`welcome_due` marks a boot-time `--load` whose welcome waits for the first connection.

Public API: `ScribeMemory`.
"""

import random
from collections.abc import Sequence
from dataclasses import dataclass, field

from aidm.data.scribe_lines import ScribeGroup, ScribeLine


@dataclass
class ScribeMemory:
    picks: int = 0
    last: dict[ScribeGroup, str] = field(default_factory=dict[ScribeGroup, str])
    current: str | None = None
    welcome_due: bool = False

    def pick(self, lines: Sequence[ScribeLine], seed: int) -> ScribeLine:
        if not lines:
            raise ValueError("no Scribe line to pick from")
        group = lines[0].group
        pool = [line for line in lines if line.id != self.last.get(group)] or list(lines)
        rng = random.Random(f"{seed}:scribe:{self.picks}")
        self.picks += 1
        line = rng.choice(pool)
        self.last[group] = line.id
        self.current = line.id
        return line
