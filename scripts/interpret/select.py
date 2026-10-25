"""The deterministic pick of the typed lines to label (M36.8a, docs/next/M36_LABELLING.md).

1. Finding-cited lines: every cite in `citations.json` (a typed line a playtest finding about typed
   actions quotes) resolves to the nearest `action_declared` at or before the cited event, within
   the file's window, whose text holds the cite's quote (a doc may cite the result event, not the
   line). A cite that does not resolve raises: the citation table is wrong, not the sample.
2. A stratified sample (fixed seed) fills each scope up to its quota, round-robin over the runs,
   skipping a text already taken in the same scope; button and chip sentences are capped.

Public API: `load_citations`, `resolve`, `cited_rows`, `is_button`, `sample`, `select`, `mix`.
"""

import gzip
import json
import random
import re
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

from scripts.interpret import lib

CITATIONS = Path(__file__).with_name("citations.json")
SEED = 368
TOTAL = 300
QUOTAS = {"explore": 140, "fight": 100, "offer": 50, "off_turn": 10}  # sums to TOTAL
FILL = "explore"  # a scope short of rows gives its quota here
BUTTON_CAP = 20
ROUND_OF = {"G": 1, "R": 2, "T": 3, "V": 4, "X": 5, "Y": 6}  # finding letters per round
BUTTONS = tuple(
    re.compile(p)
    for p in (
        r"^I travel to [^,;]+\.?$",
        r"^trade with [^,;]+$",
        r"^I talk to [^,;]+\.$",
        r"^I take a closer look at [^,;]+\.$",
        r"^I pick up [^,;]+\.$",
        r"^I look around\.$",
        r"^I search the area carefully\.$",
        r"^We take a short rest\.$",
    )
)
_SPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class Cite:
    source: str  # "<round tag> <finding id>", e.g. "M34 Y11"
    run: str  # the fixture run
    cited: int  # the event number the doc cites
    quote: str


@dataclass(frozen=True)
class Citations:
    window: int
    cites: tuple[Cite, ...]
    missing: tuple[tuple[str, str], ...]  # (source, reason) of lines not in the fixtures


def norm(text: str) -> str:
    return _SPACE.sub(" ", text.replace("’", "'")).strip().lower()


def _cite(rounds: dict[str, Any], doc: str, fid: str, ref: str, quote: str) -> Cite:
    short, number = ref.split()
    meta = rounds[doc]
    return Cite(f"{meta['tag']} {fid}", meta["runs"][short], int(number), quote)


def load_citations(path: Path = CITATIONS) -> Citations:
    raw = json.loads(path.read_text(encoding="utf-8"))
    rounds = raw["rounds"]
    cites = tuple(_cite(rounds, *row) for row in raw["cites"])
    missing = tuple((f"{rounds[d]['tag']} {f}", why) for d, f, _, why in raw["missing"])
    return Citations(int(raw["window"]), cites, missing)


@cache
def declared(run: str) -> tuple[tuple[int, str], ...]:
    """(seq, text) of every typed line of a fixture run, read straight from its event log."""
    found: list[tuple[int, str]] = []
    with gzip.open(lib.FIXTURES / run / "events.jsonl.gz", "rt", encoding="utf-8") as raw:
        for line in raw:
            if '"action_declared"' in line:
                row = json.loads(line)
                if row["event"]["type"] == "action_declared":
                    found.append((int(row["seq"]), str(row["event"]["text"])))
    return tuple(found)


def resolve(cite: Cite, window: int) -> int:
    """The seq of the typed line a cite points at; ValueError when none matches."""
    quote = norm(cite.quote)
    for seq, text in reversed(declared(cite.run)):
        if cite.cited - window <= seq <= cite.cited and quote in norm(text):
            return seq
    raise ValueError(
        f"{cite.source}: no typed line at or before {cite.run} {cite.cited} holds {cite.quote!r}"
    )


def cited_rows(citations: Citations, by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per cited line (first finding wins the source, the rest go in the note)."""
    rows: dict[str, dict[str, Any]] = {}
    for cite in citations.cites:
        row_id = f"{cite.run}:{resolve(cite, citations.window)}"
        if row_id in rows:
            seen = rows[row_id]
            if cite.source != seen["source"] and cite.source not in seen["note"]:
                seen["note"] = (
                    f"{seen['note']}, {cite.source}"
                    if seen["note"]
                    else (f"also cited by {cite.source}")
                )
            continue
        rows[row_id] = {**by_id[row_id], "source": cite.source, "note": ""}
    return list(rows.values())


def is_button(text: str) -> bool:
    return any(p.match(text.strip()) for p in BUTTONS)


def _by_run(pool: Iterable[dict[str, Any]], rng: random.Random) -> list[list[dict[str, Any]]]:
    runs: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in pool:
        runs[row["run"]].append(row)
    queues = [runs[name] for name in sorted(runs)]
    for queue in queues:
        rng.shuffle(queue)
    return queues


def _fill(
    queues: list[list[dict[str, Any]]], need: int, taken: set[tuple[str, str]], budget: list[int]
) -> list[dict[str, Any]]:
    """Round-robin over the runs; `budget[0]` is how many button rows may still be taken."""
    picked: list[dict[str, Any]] = []
    while len(picked) < need and any(queues):
        for queue in queues:
            while queue and len(picked) < need:
                row = queue.pop()
                key = (row["scope"], norm(row["text"]))
                button = is_button(row["text"])
                if key in taken or (button and budget[0] <= 0):
                    continue
                taken.add(key)
                budget[0] -= int(button)
                picked.append({**row, "source": "button" if button else "sample", "note": ""})
                break
    return picked


def sample(
    candidates: list[dict[str, Any]], cited: list[dict[str, Any]], seed: int = SEED
) -> list[dict[str, Any]]:
    """The stratified rows that fill each scope's quota after the cited rows."""
    rng = random.Random(seed)
    taken = {(r["scope"], norm(r["text"])) for r in cited}
    have = Counter(r["scope"] for r in cited)
    cited_ids = {r["id"] for r in cited}
    budget = [BUTTON_CAP]
    picked: list[dict[str, Any]] = []
    short = 0
    for scope in sorted(QUOTAS, key=lambda s: s == FILL):
        need = max(0, QUOTAS[scope] - have[scope]) + (short if scope == FILL else 0)
        pool = [r for r in candidates if r["scope"] == scope and r["id"] not in cited_ids]
        got = _fill(_by_run(pool, rng), need, taken, budget)
        short += need - len(got)
        picked += got
    return picked


def select(
    candidates: list[dict[str, Any]], citations: Citations, seed: int = SEED
) -> list[dict[str, Any]]:
    by_id = {r["id"]: r for r in candidates}
    cited = cited_rows(citations, by_id)
    return cited + sample(candidates, cited, seed)


def mix(rows: list[dict[str, Any]]) -> dict[str, Counter[str]]:
    """Counts by scope, by source kind and by finding round (the report)."""
    kinds: Counter[str] = Counter()
    rounds: Counter[str] = Counter()
    for row in rows:
        source = str(row["source"])
        kinds["finding" if source not in ("sample", "button") else source] += 1
        if source not in ("sample", "button"):
            rounds[f"round {ROUND_OF[source.split()[1][0]]}"] += 1
    return {"scope": Counter(str(r["scope"]) for r in rows), "kind": kinds, "round": rounds}
