"""Contract rules A1-A4 (state), wired to the checks that already exist (M43.1)."""

from aidm.models.events import AnyEvent
from aidm.models.state import GameState
from scripts.audit.replay import PRESENT, audit_run
from scripts.contractlib.save import Finding, Save
from scripts.sim.checks import _first_difference, engine_invariants
from scripts.sim.ledger import ledger_problems


def a1_replay(save: Save, final: GameState) -> list[Finding]:
    """A1: the replayed log equals snapshot.json (a save without one: replay alone)."""
    snap = save.snapshot
    if snap is None or snap.model_dump() == final.model_dump():
        return []
    return [
        Finding("A1", final.event_count, _first_difference(final.model_dump(), snap.model_dump()))
    ]


def a2_ledger(save: Save) -> list[Finding]:
    """A2: every gold, XP and item change has its cause (scripts.sim.ledger)."""
    assert save.initial is not None
    events: list[AnyEvent] = [e.event for e in save.events]
    return [Finding("A2", _index(p), p) for p in ledger_problems(save.initial, events, limit=50)]


def _index(problem: str) -> int:
    words = problem.split()
    return int(words[1]) if len(words) > 1 and words[1].isdigit() else 0


def a3_stale(save: Save) -> list[Finding]:
    """A3: no stale story record shown as the present (the narration audit)."""
    run = audit_run(save.folder)
    found = [
        Finding("A3", seq, f"{store}: {text[:60]}")
        for seq, store, text, how in run.cases
        if how == PRESENT
    ]
    if run.journal[1]:
        found.append(Finding("A3", 0, f"{run.journal[1]} stale journal records shown as present"))
    return found


class Bounds:
    """A4 at each event: the hp it writes stays within 0..max (a resource cannot be written
    past its maximum: the model refuses it), and at the end of the log."""

    def see(self, seq: int, state: GameState, event: AnyEvent) -> list[Finding]:
        creature = state.creatures.get(getattr(event, "creature_id", ""))
        if creature is None:
            return []
        if event.type == "hp_changed" and not 0 <= event.new_hp <= creature.max_hp:
            return [
                Finding("A4", seq, f"{creature.id} hp {event.new_hp} outside 0..{creature.max_hp}")
            ]
        return []

    def end(self, state: GameState) -> list[Finding]:
        return [Finding("A4", state.event_count, p) for p in engine_invariants(state)]
