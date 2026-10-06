"""Per-seed results: counters, failures (each with the step it happened in) and verbose logging.

Public API: `Report`.
"""

from dataclasses import dataclass, field


@dataclass
class Report:
    seed: int
    verbose: bool = False
    failures: list[str] = field(default_factory=list[str])
    turns: int = 0  # submitted exploration actions plus combat commands that were answered
    combats: int = 0
    submits: int = 0
    notes: list[str] = field(default_factory=list[str])
    step: str = "start"
    level: int = 1  # the highest hero level reached by play
    rests: tuple[int, int] = (0, 0)  # short and long rests taken by play

    def fail(self, message: str) -> None:
        text = f"seed={self.seed} step={self.step}: {message}"
        self.failures.append(text)
        self.say(f"FAIL {text}", force=True)

    def say(self, message: str, *, force: bool = False) -> None:
        if self.verbose or force:
            print(f"  [seed {self.seed}] {message}", flush=True)

    @property
    def ok(self) -> bool:
        return not self.failures

    def summary(self) -> str:
        status = "ok" if self.ok else f"FAILED({len(self.failures)})"
        short, long = self.rests
        return (
            f"seed {self.seed}: {status} turns={self.turns} combats={self.combats} "
            f"level={self.level} rests={short}s/{long}l"
        )
