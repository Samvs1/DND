from functools import cache
from pathlib import Path

from .helpers import SCRIPTS_DIR, load_script

FIXTURES = SCRIPTS_DIR.parent / "tests" / "fixtures" / "saves"

audit = load_script("narration_audit")


@cache
def _run(name: str):
    from scripts.audit.replay import audit_run

    return audit_run(Path(FIXTURES / name))


def _cases(name: str, seq: int, store: str) -> list[str]:
    return [t for s, st, t in _run(name).cases if s == seq and st == store]


def test_audit_finds_the_stale_stirges_fact_at_r7_full_513() -> None:
    texts = _cases("m39-r7-full", 513, "facts")
    assert any("stirges" in t and "no blow" in t for t in texts)


def test_audit_finds_the_accepted_pair_at_r7_quests_119() -> None:
    texts = _cases("m39-r7-quests", 119, "facts")
    assert any("not yet accepted or refused" in t for t in texts)


def test_audit_counts_are_consistent_and_ascii() -> None:
    from scripts.audit.replay import table_lines

    run = _run("m39-r7-quests")
    assert run.narrations > 0 and run.skipped == 0
    assert all(run.stale[s] <= run.shown[s] for s in run.shown)
    assert all(line.isascii() for line in table_lines([run]))
