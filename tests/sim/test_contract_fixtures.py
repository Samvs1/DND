"""M43.5: the game's contract on every fixture save (docs/next/M43_CONTRACT.md), in the gate.

`tests/fixtures/contract_baseline.json` is the recorded history: findings in saves made by
engines older than the fix that answers them (A2 m35-r6-typed: the double payout M35.1 fixed;
C1-C4: quests registered before M43.4). A recorded save cannot change, so each count must
EQUAL its baseline: a new finding fails, and so does a check that stops finding the old ones."""

import json
from pathlib import Path

from scripts.contract import FIXTURES, findings

BASELINE = Path(__file__).resolve().parents[1] / "fixtures" / "contract_baseline.json"


def test_contract_on_every_fixture_matches_its_recorded_history() -> None:
    counts, _ = findings(sorted(p for p in FIXTURES.iterdir() if p.is_dir()))
    found = {save: {r: n for r, n in row.items() if n} for save, row in counts.items()}
    expected = json.loads(BASELINE.read_text(encoding="utf-8"))
    assert {save: row for save, row in found.items() if row} == expected
