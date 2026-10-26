"""The two eval modes over a corpus (M36.7): offline coverage and the live chooser."""

import time
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from aidm.dm.chooser import ChooserFailure, choose
from aidm.dm.llm_client import LlmClient
from aidm.dm.llm_types import LlmRole
from aidm.models.action_menu import MenuChoice
from aidm.models.events import AnyEvent
from aidm.models.state import GameState
from scripts.interpret import lib
from scripts.interpret.corpus import Row, SceneRow, gaps
from scripts.interpret.score import verdicts
from scripts.interpret.synthetic import scene

DEFAULT_CAP = 300


@dataclass
class Situation:
    """A scene row's state: nothing happened before it (M38.1)."""

    state: GameState
    recent: list[AnyEvent]


def _scene_state(row: SceneRow) -> Situation | None:
    try:
        return Situation(scene(row.scene).state, [])
    except KeyError:
        return None


def with_states(rows: list[Row]) -> Iterator[tuple[Row, lib.Line | Situation | None]]:
    """Each row with the line (or scene) it names (None if there is none); live state."""
    by_run: dict[str, dict[int, Row]] = defaultdict(dict)
    for row in rows:
        if isinstance(row, SceneRow):
            yield row, _scene_state(row)
        else:
            by_run[row.run][row.seq] = row
    for run, wanted in by_run.items():
        seen: set[int] = set()
        for line in lib.walk(run, frozenset(wanted)):
            seen.add(line.seq)
            yield wanted[line.seq], line
        for seq in sorted(set(wanted) - seen):
            yield wanted[seq], None


def coverage(rows: list[Row]) -> list[str]:
    problems: list[str] = []
    for row, line in with_states(rows):
        if line is None:
            problems.append(f"{row.id}: no such typed line or scene")
            continue
        if isinstance(line, lib.Line) and (
            line.event.creature_id != row.actor_id or line.event.text != row.text
        ):
            problems.append(f"{row.id}: actor or text differs from the fixture line")
        if row.actor_id not in line.state.creatures:
            problems.append(f"{row.id}: actor {row.actor_id} is not in the state")
            continue
        menu = lib.menu_for(line.state, row.actor_id)
        problems += [f"{row.id}: {g}" for g in gaps(menu, row)]
    return problems


def _fast_totals(llm: LlmClient) -> tuple[int, int, int]:
    t = llm.totals.by_role[LlmRole.FAST]
    return t.calls, t.prompt_tokens, t.completion_tokens


def _describe(choice: MenuChoice | None) -> dict[str, Any] | None:
    return None if choice is None else choice.model_dump(mode="json")


async def live(rows: list[Row], llm: LlmClient, cap: int, limit: int | None) -> dict[str, Any]:
    """Run the real chooser on each row; stops cleanly once `cap` model calls are used."""
    results: dict[str, dict[str, Any]] = {}
    used = 0
    todo = rows[:limit] if limit else rows
    for row, line in with_states(todo):
        if used >= cap or line is None:
            continue
        menu = lib.menu_for(line.state, row.actor_id)
        before = _fast_totals(llm)
        start = time.perf_counter()
        picked = await choose(line.state, row.actor_id, row.text, menu, llm, recent=line.recent)
        took = time.perf_counter() - start
        after = _fast_totals(llm)
        calls = after[0] - before[0]
        used += calls
        pick = None if isinstance(picked, ChooserFailure) else picked
        results[row.id] = {
            "id": row.id,
            "scope": row.scope,
            "source": row.source,
            "text": row.text,
            "pick": _describe(pick),
            "failure": picked.reason if isinstance(picked, ChooserFailure) else None,
            "expected": row.expect.model_dump(),
            "verdict": verdicts(row, line.state, menu, pick, calls),
            "latency_s": round(took, 3),
            "calls": calls,
            "prompt_tokens": after[1] - before[1],
            "completion_tokens": after[2] - before[2],
        }
    ordered = [results[r.id] for r in todo if r.id in results]
    return {"results": ordered, "calls": used, "scored": len(ordered), "asked": len(todo)}
