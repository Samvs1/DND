"""Scoring of the chooser's picks against the corpus expectations (M36.7).

Definitions (a "choice" is steps + other + other_first; targets compare as sets):
- exact: the pick's steps (entry, targets, qty), other and other_first equal the expectation
  or one alt (`colour` and other's words are never scored, M36.9);
- entry match: the pick's entry ids in order and its other flag equal the expectation's or an alt's;
- act match: exact, or `to_acts` of the pick equals `to_acts` of the expectation or an alt
  (equivalent ids count); an `OtherIntent` compares by presence and position only, never its
  words (M36.9: the model's other.text against a label's empty text), so act >= exact always;
- false action: the pick has a step whose entry is in no expectation (it did something not asked);
- false other: the pick has `other` while no expectation has it and the expectation has steps;
- fast path: the exact label fast path answered (no model call); failure: the chooser failed.
"""

import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from aidm.models.action_menu import ActionMenu, MenuChoice
from aidm.models.state import GameState
from aidm.rules.acts import OtherIntent
from aidm.rules.menu_steps import Act, to_acts
from scripts.interpret import lib
from scripts.interpret.corpus import Row, shape

FLAGS = ("exact", "entry", "act", "false_action", "false_other", "fast", "failed")


def _entries(choice: MenuChoice) -> tuple[tuple[str, ...], bool]:
    return tuple(s.entry for s in choice.steps), choice.other


OTHER_MARK = "<other>"


def _acts(state: GameState, menu: ActionMenu, choice: MenuChoice, text: str) -> list[object] | None:
    """The pick's acts, each `OtherIntent` as one marker (its words are not scored)."""
    try:
        acts: list[Act] = to_acts(state, menu, choice, lib.regs(), text)
    except Exception:  # an unplayable pick is simply not a match
        return None
    return [OTHER_MARK if isinstance(a, OtherIntent) else a for a in acts]


def verdicts(
    row: Row, state: GameState, menu: ActionMenu, pick: MenuChoice | None, calls: int
) -> dict[str, bool]:
    out: dict[str, bool] = dict.fromkeys(FLAGS, False)
    if pick is None:
        out["failed"] = True
        return out
    wanted = row.choices()
    out["fast"] = calls == 0
    out["exact"] = shape(pick) in [shape(c) for c in wanted]
    out["entry"] = _entries(pick) in [_entries(c) for c in wanted]
    got = _acts(state, menu, pick, row.text)
    same = got is not None and any(got == _acts(state, menu, c, row.text) for c in wanted)
    out["act"] = out["exact"] or same  # exact compares targets as sets, acts keep their order
    known = {s.entry for c in wanted for s in c.steps}
    out["false_action"] = any(s.entry not in known for s in pick.steps)
    asked_steps = any(c.steps for c in wanted)
    out["false_other"] = pick.other and asked_steps and not any(c.other for c in wanted)
    return out


@dataclass
class Tally:
    rows: int = 0
    flags: dict[str, int] = field(default_factory=lambda: dict.fromkeys(FLAGS, 0))

    def add(self, verdict: dict[str, bool]) -> None:
        self.rows += 1
        for name in FLAGS:
            self.flags[name] += int(verdict[name])


def tallies(results: list[dict[str, Any]]) -> dict[str, dict[str, Tally]]:
    """Tallies by `overall`, `scope`, `source` and `findings` (sources citing a finding)."""
    groups: dict[str, dict[str, Tally]] = defaultdict(lambda: defaultdict(Tally))
    for result in results:
        verdict: dict[str, bool] = result["verdict"]
        keys = [("overall", "all"), ("scope", result["scope"]), ("source", result["source"])]
        if result["source"] not in ("sample", "button", ""):
            keys.append(("findings", "finding-cited"))
        for group, key in keys:
            groups[group][key].add(verdict)
    return groups


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(pct * (len(ordered) - 1)))]


def latency(results: list[dict[str, Any]]) -> tuple[float, float]:
    times = [r["latency_s"] for r in results if r["calls"] > 0]
    return (statistics.median(times) if times else 0.0), percentile(times, 0.9)


def table(groups: dict[str, dict[str, Tally]]) -> list[str]:
    head = f"{'group':<10}{'key':<24}{'rows':>5}" + "".join(f"{f[:9]:>10}" for f in FLAGS)
    lines = [head]
    for group, rows in groups.items():
        for key, tally in rows.items():
            cells = "".join(f"{tally.flags[f] / max(1, tally.rows) * 100:>9.1f}%" for f in FLAGS)
            lines.append(f"{group:<10}{key[:23]:<24}{tally.rows:>5}{cells}")
    return lines
