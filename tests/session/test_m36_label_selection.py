"""M36.8a: the citation table, the deterministic pick of lines to label, and the label sheets."""

from collections import Counter
from typing import Any

import pytest

from scripts.interpret import lib
from scripts.interpret.score import FLAGS, tallies
from scripts.interpret.select import (
    BUTTON_CAP,
    QUOTAS,
    Citations,
    Cite,
    declared,
    is_button,
    load_citations,
    mix,
    resolve,
    select,
)
from scripts.interpret.sheets import sheet_rows, split

# finding-cited lines per round (docs/playtests: M29 rounds 1-3, M31 rounds 4-5, M34 round 6)
CITED_PER_ROUND = {"round 1": 23, "round 2": 17, "round 3": 14, "round 4": 27, "round 5": 23}
CITED_PER_ROUND["round 6"] = 16


def _cited_candidates(citations: Citations) -> list[dict[str, Any]]:
    """Minimal candidate rows for every typed line of the cited runs (no menus needed)."""
    rows: list[dict[str, Any]] = []
    for run in sorted({c.run for c in citations.cites}):
        for seq, text in declared(run):
            rows.append(
                {
                    "id": f"{run}:{seq}",
                    "run": run,
                    "seq": seq,
                    "actor_id": "pc-p2",
                    "text": text,
                    "scope": "explore",
                }
            )
    return rows


def test_citation_runs_are_committed_fixtures() -> None:
    known = set(lib.run_names())
    citations = load_citations()
    assert {c.run for c in citations.cites} <= known
    assert all(source.startswith("M34 Y") for source, _ in citations.missing)


def test_every_citation_resolves_to_a_line_holding_its_quote() -> None:
    citations = load_citations()
    for cite in citations.cites:
        seq = resolve(cite, citations.window)
        text = dict(declared(cite.run))[seq]
        assert cite.quote.lower() in text.lower().replace("’", "'")
        assert cite.cited - citations.window <= seq <= cite.cited


def test_a_cited_result_event_maps_back_to_the_typed_line() -> None:
    # M34 Y11 cites "typed 161-164" and "181-184": 164 and 181 are results; lines 161 and 179
    assert resolve(Cite("M34 Y11", "m35-r6-typed", 164, "arrow in its chest"), 30) == 161
    assert resolve(Cite("M34 Y11", "m35-r6-typed", 181, "bolt of fire"), 30) == 179
    # M31 X6 cites "typed 37" for the sheathe line 35 (37 is a later, different typed line)
    assert resolve(Cite("M31 X6", "m32-r5-typed", 37, "sheathe my sword"), 30) == 35
    with pytest.raises(ValueError):
        resolve(Cite("M34 Y11", "m35-r6-typed", 164, "a quote no line holds"), 30)


def test_finding_cited_rows_per_round() -> None:
    citations = load_citations()
    rows = select(_cited_candidates(citations), citations)
    cited = [r for r in rows if r["source"] not in ("sample", "button")]
    assert len(cited) == 120 == len({r["id"] for r in cited})
    assert dict(mix(cited)["round"]) == CITED_PER_ROUND
    shared = next(r for r in cited if r["id"] == "m32-r5-typed:354")
    assert shared["source"] == "M31 X1" and "M31 X3" in shared["note"]


def _synthetic() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for n in range(600):
        scope = ("explore", "fight", "offer")[n % 3]
        run = f"run-{n % 4}"
        text = f"I travel to Place {n}" if n % 10 == 0 else f"line {n % 250} of {scope}"
        rows.append(
            {
                "id": f"{run}:{n}",
                "run": run,
                "seq": n,
                "actor_id": "pc-p2",
                "text": text,
                "scope": scope,
            }
        )
    return rows


def test_selection_is_deterministic_and_stratified() -> None:
    none = Citations(30, (), ())
    first, second = select(_synthetic(), none), select(_synthetic(), none)
    assert [r["id"] for r in first] == [r["id"] for r in second]
    scopes = Counter(r["scope"] for r in first)
    assert scopes["fight"] == QUOTAS["fight"] and scopes["offer"] == QUOTAS["offer"]
    assert scopes["explore"] == QUOTAS["explore"] + QUOTAS["off_turn"]  # no off-turn rows
    assert len(first) == sum(QUOTAS.values())
    keys = [(r["scope"], r["text"]) for r in first]
    assert len(keys) == len(set(keys))  # no repeated text inside a scope
    buttons = [r for r in first if r["source"] == "button"]
    assert 0 < len(buttons) <= BUTTON_CAP and all(is_button(r["text"]) for r in buttons)
    assert len({r["run"] for r in first if r["scope"] == "offer"}) == 4  # every run drawn


def test_button_sentences() -> None:
    assert is_button("I travel to Lamplighters' Rest") and is_button("I travel to Gullmere Quay.")
    assert is_button("trade with Bramble Pike") and is_button("I look around.")
    assert not is_button("We leave the vestry and head on to Lamplighters' Rest")
    assert not is_button("I travel to the quay, then trade with the peddler")


def test_button_rows_do_not_count_as_finding_cited() -> None:
    verdict = dict.fromkeys(FLAGS, False)
    results = [{"scope": "explore", "source": s, "verdict": verdict} for s in ("button", "M34 Y11")]
    assert tallies(results)["findings"]["finding-cited"].rows == 1


def test_split_balances_parts_and_scopes() -> None:
    rows = select(_synthetic(), Citations(30, (), ()))
    parts = split(rows)
    assert sorted(len(p) for p in parts) == [100, 100, 100]
    for scope in ("explore", "fight", "offer"):
        counts = [sum(r["scope"] == scope for r in p) for p in parts]
        assert max(counts) - min(counts) <= 1
    assert [[r["id"] for r in p] for p in split(rows)] == [[r["id"] for r in p] for p in parts]


def test_sheet_row_carries_the_menu_as_the_chooser_sees_it() -> None:
    row = {
        "id": "m35-r6-typed:161",
        "run": "m35-r6-typed",
        "seq": 161,
        "actor_id": "pc-p4",
        "text": "I put an arrow in its chest",
        "scope": "fight",
        "source": "M34 Y11",
        "note": "",
        "router": None,
        "engine": [],
    }
    (sheet,) = sheet_rows([row])
    assert "- attack:shortbow = Shortbow" in sheet["prompt"]
    assert "swarm-of-rats-1 = " in sheet["prompt"]
    assert "## MENU" in sheet["prompt"] and "## PRONOUNS" in sheet["prompt"]
    assert sheet["exact"] is None and sheet["source"] == "M34 Y11"
