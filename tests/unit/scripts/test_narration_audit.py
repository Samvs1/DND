from functools import cache
from pathlib import Path

from .helpers import SCRIPTS_DIR, load_script

FIXTURES = SCRIPTS_DIR.parent / "tests" / "fixtures" / "saves"

audit = load_script("narration_audit")


@cache
def _run(name: str):
    from scripts.audit.replay import audit_run

    return audit_run(Path(FIXTURES / name))


def _cases(name: str, seq: int, store: str) -> list[tuple[str, str]]:
    return [(t, how) for s, st, t, how in _run(name).cases if s == seq and st == store]


def test_audit_finds_the_stale_stirges_fact_at_r7_full_513_left_out() -> None:
    # M40.3 found it shown as the present; M40.4 leaves it out (`rules.story_records`)
    cases = _cases("m39-r7-full", 513, "facts")
    assert any("stirges" in t and "no blow" in t and how == "left out" for t, how in cases)


def test_audit_finds_the_accepted_pair_at_r7_quests_119_left_out() -> None:
    cases = _cases("m39-r7-quests", 119, "facts")
    assert any("not yet accepted or refused" in t and how == "left out" for t, how in cases)


def test_audit_finds_no_stale_record_shown_as_present_in_round_7() -> None:
    for name in ("m39-r7-full", "m39-r7-quests"):
        run = _run(name)
        assert sum(run.stale.values()) == 0 and run.prompts_stale == 0, name
        assert run.journal[1] == 0 and run.epilogue[1] == 0, name


def test_audit_counts_are_consistent_and_ascii() -> None:
    from scripts.audit.replay import table_lines

    run = _run("m39-r7-quests")
    assert run.narrations > 0 and run.skipped == 0
    assert all(run.stale[s] + run.past[s] <= run.shown[s] for s in run.shown)
    assert all(line.isascii() for line in table_lines([run]))
