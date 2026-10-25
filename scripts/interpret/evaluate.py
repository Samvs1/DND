"""The three eval modes over a corpus (M36.7): offline coverage, live chooser, router baseline."""

import time
from collections import defaultdict
from collections.abc import Iterator
from typing import Any

from aidm.dm.chooser import ChooserFailure, choose
from aidm.dm.llm_client import LlmClient
from aidm.dm.llm_types import LlmRole
from aidm.models.action_menu import MenuChoice
from aidm.rules.acts import OtherIntent
from aidm.rules.menu_steps import to_acts
from scripts.interpret import lib
from scripts.interpret.corpus import Row, gaps
from scripts.interpret.router import UNAVAILABLE, reading
from scripts.interpret.score import FLAGS, verdicts

DEFAULT_CAP = 300


def with_states(rows: list[Row]) -> Iterator[tuple[Row, lib.Line | None]]:
    """Each row with the line it names (None if the fixture has no such line); live state."""
    by_run: dict[str, dict[int, Row]] = defaultdict(dict)
    for row in rows:
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
            problems.append(f"{row.id}: no such typed line in the fixture")
            continue
        if line.event.creature_id != row.actor_id or line.event.text != row.text:
            problems.append(f"{row.id}: actor or text differs from the fixture line")
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


def router_baseline(rows: list[Row]) -> dict[str, Any]:
    """The old router's reading of each line, scored by act match (no model calls)."""
    results: list[dict[str, Any]] = []
    for row, line in with_states(rows):
        if line is None:
            continue
        menu = lib.menu_for(line.state, row.actor_id)
        found, label = reading(line.state, row.actor_id, row.text, menu.scope)
        if label == UNAVAILABLE:
            return {"results": [], "scored": 0, "asked": len(rows), "calls": 0}
        results.append(
            {
                "id": row.id,
                "scope": row.scope,
                "source": row.source,
                "text": row.text,
                "router": label,
                "verdict": _router_verdict(row, line, found),
                "calls": 0,
                "latency_s": 0.0,
            }
        )
    return {"results": results, "scored": len(results), "asked": len(rows), "calls": 0}


def _router_verdict(row: Row, line: lib.Line, found: object | None) -> dict[str, bool]:
    menu = lib.menu_for(line.state, row.actor_id)
    ours: list[object] = [OtherIntent(row.actor_id, row.text)] if found is None else [found]
    out: dict[str, bool] = dict.fromkeys(FLAGS, False)
    for choice in row.choices():
        try:
            want: list[object] = list(to_acts(line.state, menu, choice, lib.regs(), row.text))
        except Exception:  # an expectation the rules cannot play never matches
            continue
        if want == ours or (isinstance(found, list) and want == found):
            out["act"] = True
    return out
