"""M36.7: the typed-line extraction and the interpreter eval scripts (no network, FakeLLM only)."""

import json
from pathlib import Path
from typing import Any

from aidm.dm.chooser import exact_choice
from aidm.dm.fake_llm import FakeReply, fake_tool_call
from scripts.eval_interpret import main as eval_main
from scripts.extract_typed_lines import main as extract_main
from scripts.interpret import lib
from scripts.interpret.corpus import Expect, Row, load_corpus
from scripts.interpret.evaluate import coverage, live, router_baseline, with_states
from scripts.interpret.score import tallies
from tests.ai.chooser_fixtures import chooser_client

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "interpret"
SAMPLE = FIXTURES / "sample_corpus.jsonl"
CORPUS = FIXTURES / "corpus.jsonl"


def _pick(steps: list[tuple[str, list[str]]], other: bool = False) -> FakeReply:
    rows = [{"do": e, "to": t, "qty": None} for e, t in steps]
    return fake_tool_call(
        "choose_actions", {"steps": rows, "other": {"text": "", "first": False} if other else None}
    )


def _as_model_would(expect: Expect) -> FakeReply:
    """The expectation as the model answers it, with words a label never holds: other.text and
    colour set (M36.9: neither may change exact or act match)."""
    rows = [
        {"do": s.entry, "to": s.targets, "qty": s.qty if s.qty > 1 else None} for s in expect.steps
    ]
    other = {"text": "words no label has", "first": expect.other_first} if expect.other else None
    args: dict[str, Any] = {"steps": rows, "other": other, "colour": "with a flourish"}
    return fake_tool_call("choose_actions", args)


def _scripted_expectations(rows: list[Row]) -> list[FakeReply]:
    """One reply per row the model is asked, in the order `live` asks (no reply for a row the
    exact fast path answers)."""
    script: list[FakeReply] = []
    for row, line in with_states(rows):
        menu = lib.menu_for(line.state, row.actor_id) if line is not None else None
        if menu is not None and menu.entries and exact_choice(menu, row.text) is None:
            script.append(_as_model_would(row.expect))
    return script


async def _act_never_below_exact(tmp_path: Path, rows: list[Row]) -> list[dict[str, Any]]:
    llm, _ = chooser_client(tmp_path, {"choose_actions": _scripted_expectations(rows)})
    run = await live(rows, llm, cap=1_000, limit=None)
    verdicts = [r["verdict"] for r in run["results"]]
    assert verdicts and all(v["act"] or not v["exact"] for v in verdicts)
    return run["results"]


async def test_eval_act_match_ignores_other_words_and_colour(tmp_path: Path) -> None:
    """M36.9 scorer bug: rows exact but not act match (other.text compared against "")."""
    results = await _act_never_below_exact(tmp_path, load_corpus(SAMPLE))
    asked = [r for r in results if r["calls"] == 1]
    assert asked and all(r["verdict"]["exact"] and r["verdict"]["act"] for r in asked)
    assert any(r["pick"]["other"] for r in asked) and all(r["pick"]["colour"] for r in asked)


async def test_eval_act_match_is_never_below_exact_on_the_corpus(tmp_path: Path) -> None:
    results = await _act_never_below_exact(tmp_path, load_corpus(CORPUS))
    assert len(results) == 300
    asked = [r for r in results if r["calls"] == 1]
    assert all(r["verdict"]["exact"] and r["verdict"]["act"] for r in asked)


def test_extract_typed_lines_one_run(tmp_path: Path) -> None:
    out = tmp_path / "c.jsonl"
    assert extract_main(["--runs", "m35-r6-typed", "--out", str(out)]) == 0
    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 135
    by_id = {r["id"]: r for r in rows}
    y11 = by_id["m35-r6-typed:179"]
    assert y11["actor_id"] == "pc-p6" and y11["scope"] == "fight"
    assert "cast:fire-bolt" in y11["menu_ids"] and "spell_cast:fire-bolt" not in y11["engine"]
    assert set(y11) == {
        "id",
        "run",
        "seq",
        "actor_id",
        "text",
        "scope",
        "menu_ids",
        "router",
        "engine",
    }
    assert by_id["m35-r6-typed:770"]["router"] is None


def test_extract_unknown_run_is_refused(tmp_path: Path) -> None:
    assert extract_main(["--runs", "nope", "--out", str(tmp_path / "x.jsonl")]) == 2


def test_eval_offline_sample_corpus_is_covered() -> None:
    rows = load_corpus(SAMPLE)
    assert len(rows) == 7
    assert coverage(rows) == []
    assert eval_main(["--corpus", str(SAMPLE)]) == 0


def test_eval_offline_reports_a_gap(tmp_path: Path) -> None:
    rows = [json.loads(line) for line in SAMPLE.read_text(encoding="utf-8").splitlines()]
    rows[0]["expect"]["steps"][0]["entry"] = "cast:not-a-spell"
    bad = tmp_path / "bad.jsonl"
    bad.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    assert eval_main(["--corpus", str(bad)]) == 1
    assert any("cast:not-a-spell" in p for p in coverage(load_corpus(bad)))


async def test_eval_live_scoring_arithmetic(tmp_path: Path) -> None:
    rows: list[Row] = load_corpus(SAMPLE)[:6]
    # the model is asked in fixture order: typed 55, 161, 179, 435, 770, then quests 563
    script = [
        _pick([], other=True),  # 55: other expected -> exact
        _pick([("attack:dagger", ["swarm-of-rats-1"])]),  # 161: wrong weapon -> false action
        _pick([("cast:fire-bolt", ["swarm-of-rats-1"])]),  # 179: exact
        _pick([("attack:longsword", ["kobold-2"])]),  # 435: an alt -> exact and act
        _pick([("travel", ["sunken-vestry"])]),  # 770: right entry, wrong place
        _pick([], other=True),  # 563: other where a give was asked -> false other
    ]
    llm, _ = chooser_client(tmp_path, {"choose_actions": script})
    run = await live(rows, llm, cap=300, limit=None)
    assert run["scored"] == 6 and run["calls"] == 6
    by_id = {r["id"]: r["verdict"] for r in run["results"]}
    assert by_id["m35-r6-typed:55"]["exact"] and by_id["m35-r6-typed:55"]["act"]
    wrong = by_id["m35-r6-typed:161"]
    assert wrong["false_action"] and not wrong["act"] and not wrong["entry"]
    assert by_id["m35-r6-typed:179"]["exact"]
    alt = by_id["m35-r6-typed:435"]
    assert alt["exact"] and alt["act"] and not alt["false_action"]
    place = by_id["m35-r6-typed:770"]
    assert place["entry"] and not place["exact"] and not place["act"]
    other = by_id["m35-r6-quests:563"]
    assert other["false_other"] and not other["act"] and not other["false_action"]
    overall = tallies(run["results"])["overall"]["all"]
    assert overall.rows == 6 and overall.flags["exact"] == 3 and overall.flags["false_action"] == 1
    assert all(r["verdict"]["act"] or not r["verdict"]["exact"] for r in run["results"])


async def test_eval_live_stops_at_the_cap(tmp_path: Path) -> None:
    rows = load_corpus(SAMPLE)[:6]
    script = [_pick([], other=True)] * 6
    llm, _ = chooser_client(tmp_path, {"choose_actions": script})
    run = await live(rows, llm, cap=2, limit=None)
    assert run["scored"] == 2 and run["calls"] == 2 and run["asked"] == 6


def test_eval_router_baseline_scores_by_acts() -> None:
    run = router_baseline(load_corpus(SAMPLE))
    assert run["scored"] == 7 and run["calls"] == 0
    verdicts = {r["id"]: r["verdict"] for r in run["results"]}
    assert not verdicts["m35-r6-typed:161"]["act"]  # Y11: the router missed the pronoun line
