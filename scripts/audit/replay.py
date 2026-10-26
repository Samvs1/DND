"""Replay half of the narration audit (M40.3): see scripts/narration_audit.py."""

import gzip
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from aidm.dm.epilogue_facts import MAX_LEDGER_FACTS
from aidm.dm.event_text import event_notes
from aidm.dm.narration_weight import truth_notes
from aidm.dm.narrator import narration_messages
from aidm.dm.turn_facts import turn_facts
from aidm.models.events import AnyEvent, LoggedEvent
from aidm.models.state import GameState
from aidm.models.world_events import (
    ActionDeclared,
    FactRecorded,
    NarrationRecorded,
    NodeDescribed,
    SceneSummarised,
)
from aidm.session.reducer import apply
from aidm.session.views import public_facts, public_summaries
from scripts.audit.stale import (
    alias_table,
    changed,
    entities_named,
    giver_table,
    is_stale,
    statuses,
)

STORES = ("facts", "summaries", "narration", "descriptions")

type Made = dict[tuple[str, str], int]
type Log = list[tuple[int, str]]
type Ctx = tuple[Made, Log, dict[str, int]]


@dataclass
class Run:
    name: str
    narrations: int = 0
    skipped: int = 0
    shown: dict[str, int] = field(default_factory=lambda: dict.fromkeys(STORES, 0))
    stale: dict[str, int] = field(default_factory=lambda: dict.fromkeys(STORES, 0))
    prompts_stale: int = 0
    journal: tuple[int, int] = (0, 0)  # (records, stale)
    epilogue: tuple[int, int] = (0, 0)
    cases: list[tuple[int, str, str]] = field(default_factory=list)  # (seq, store, text)


@dataclass
class Record:
    store: str
    text: str
    ids: tuple[str, ...]
    made: int


def log_events(folder: Path) -> Iterator[LoggedEvent]:
    gz = folder / "events.jsonl.gz"
    if gz.exists():
        with gzip.open(gz, "rt", encoding="utf-8") as raw:
            lines = [x for x in raw.read().splitlines() if x]
    else:
        lines = [x for x in (folder / "events.jsonl").read_text("utf-8").splitlines() if x]
    return (LoggedEvent.model_validate_json(x) for x in lines)


def build_prompt(
    state: GameState, segment: Sequence[AnyEvent], actor: str | None, text: str | None
) -> str:
    notes = [
        *truth_notes(segment),
        *turn_facts(state, segment, actor_id=actor, player_text=text),
        *event_notes(state, segment),
    ]
    messages = narration_messages(state, segment, notes, "STYLE", actor_id=actor, player_text=text)
    return "\n".join(str(m["content"]) for m in messages)


def current_records(state: GameState, made: Made) -> list[Record]:
    def rec(store: str, text: str, ids: tuple[str, ...]) -> Record:
        return Record(store, text, ids, made.get((store, text), 0))

    out = [rec("facts", f.text, f.entity_ids) for f in state.world.facts]
    out += [rec("summaries", s.text, s.entity_ids) for s in state.memory.summaries]
    out += [rec("narration", t, ()) for t in state.memory.narration]
    out += [rec("descriptions", t, (n,)) for n, t in state.world.descriptions.items()]
    return out


def stale_of(state: GameState, records: list[Record], now: int, ctx: Ctx) -> list[Record]:
    table, givers = alias_table(state), giver_table(state)
    return [
        r
        for r in records
        if is_stale(entities_named(r.text, r.ids, table, givers), r.made, now, ctx[1], ctx[2])
    ]


def note_made(made: Made, event: AnyEvent, seq: int) -> None:
    if isinstance(event, FactRecorded):
        made.setdefault(("facts", event.fact.text), seq)
    elif isinstance(event, SceneSummarised):
        made.setdefault(("summaries", event.summary.text), seq)
    elif isinstance(event, NarrationRecorded):
        made.setdefault(("narration", event.text), seq)
    elif isinstance(event, NodeDescribed):
        made.setdefault(("descriptions", event.text), seq)


def count_narration(run: Run, state: GameState, prompt: str, seq: int, ctx: Ctx):
    made = ctx[0]
    shown = [r for r in current_records(state, made) if r.text in prompt]
    stale = stale_of(state, shown, seq, ctx)
    run.narrations += 1
    for r in shown:
        run.shown[r.store] += 1
    for r in stale:
        run.stale[r.store] += 1
        run.cases.append((seq, r.store, r.text))
    run.prompts_stale += 1 if stale else 0


def finish(run: Run, state: GameState, seq: int, ctx: Ctx) -> None:
    made = ctx[0]
    journal_facts = set(public_facts(state))
    journal_sums = {s.text for s in public_summaries(state)}
    recs = current_records(state, made)
    ledger = {f.text for f in state.world.facts[-MAX_LEDGER_FACTS:]}
    j = [r for r in recs if r.text in (journal_facts | journal_sums)]
    e = [r for r in recs if r.store == "facts" and r.text in ledger]
    run.journal = (len(j), len(stale_of(state, j, seq, ctx)))
    run.epilogue = (len(e), len(stale_of(state, e, seq, ctx)))


def audit_run(folder: Path) -> Run:
    state = GameState.model_validate_json((folder / "initial.json").read_text("utf-8"))
    run = Run(folder.name)
    made: Made = {}
    log: Log = []
    born: dict[str, int] = {k: 0 for k in statuses(state)}
    segment: list[AnyEvent] = []
    actor: str | None = None
    text: str | None = None
    before, seq = statuses(state), 0
    for entry in log_events(folder):
        seq, event = entry.seq, entry.event
        if isinstance(event, NarrationRecorded):
            try:
                prompt = build_prompt(state, segment, actor, text)
            except (KeyError, ValueError, AttributeError):
                run.skipped += 1
            else:
                count_narration(run, state, prompt, seq, (made, log, born))
            segment = []
        elif isinstance(event, ActionDeclared):
            actor, text = event.creature_id, event.text
        else:
            segment.append(event)
        apply(state, event)
        note_made(made, event, seq)
        after = statuses(state)
        log.extend((seq, k) for k in changed(before, after))
        for k in after.keys() - before.keys():
            born.setdefault(k, seq)
        before = after
    finish(run, state, seq, (made, log, born))
    return run


def table_lines(runs: list[Run]) -> list[str]:
    head = (
        "run | narr | shown f/s/n/d | stale f/s/n/d | prompts>=1 stale | journal r/s | epilogue r/s"
    )
    out = [head, "-" * len(head)]
    for r in runs:
        shown = "/".join(str(r.shown[s]) for s in STORES)
        stale = "/".join(str(r.stale[s]) for s in STORES)
        out.append(
            f"{r.name} | {r.narrations} | {shown} | {stale} | {r.prompts_stale} | "
            f"{r.journal[0]}/{r.journal[1]} | {r.epilogue[0]}/{r.epilogue[1]}"
        )
    return out
