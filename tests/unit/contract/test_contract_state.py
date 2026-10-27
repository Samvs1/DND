"""Contract rules A1-A4 on real fixture saves (M43.1)."""

from pathlib import Path

import pytest

from aidm.models.events import HpChanged
from aidm.session.persistence import SnapshotFile
from scripts.audit.replay import PRESENT, Run
from scripts.contractlib import state_rules
from scripts.contractlib.save import Save, walk
from scripts.contractlib.state_rules import Bounds, a1_replay, a2_ledger, a3_stale
from tests.unit.contract.helpers import fixture, rules, run

QUIET = "m39-r7-quests"  # a real round-7 save with 0 problems
OLD = "m35-r6-typed"  # a real round-6 save: the double payout at events 678-685 (fixed in M35.1)


def _snapshot_save(tmp_path: Path, hp_off: int) -> tuple[Save, int]:
    save = fixture(QUIET)
    final, _ = walk(save, [])
    final.creatures["pc-p4"].hp -= hp_off
    snap = SnapshotFile(seq=final.event_count, saved_at="t", state=final)
    (tmp_path / "snapshot.json").write_text(snap.model_dump_json(), "utf-8")
    return Save(save.name, tmp_path, save.initial, save.events), final.event_count


def test_contract_a1_replay_equals_snapshot(tmp_path: Path) -> None:
    save, _ = _snapshot_save(tmp_path, 0)
    assert a1_replay(save, walk(save, [])[0]) == []


def test_contract_a1_a_different_snapshot_is_found(tmp_path: Path) -> None:
    save, count = _snapshot_save(tmp_path, 1)
    found = a1_replay(save, walk(save, [])[0])
    assert [f.rule for f in found] == ["A1"] and found[0].idx == count


def test_contract_a2_ledger_clean_save() -> None:
    assert a2_ledger(fixture(QUIET)) == []


def test_contract_a2_double_payout_is_found() -> None:
    found = a2_ledger(fixture(OLD))
    assert {f.idx for f in found} == set(range(678, 686))
    assert "xp_gained" in found[0].reason


def test_contract_a3_clean_save_has_no_stale_story() -> None:
    assert a3_stale(fixture(QUIET)) == []


def test_contract_a3_a_stale_record_shown_as_present_is_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_ = Run("x")
    run_.cases.append((7, "facts", "The bridge is held by the toll-keeper", PRESENT))
    monkeypatch.setattr(state_rules, "audit_run", lambda folder: run_)
    found = a3_stale(fixture(QUIET))
    assert [(f.rule, f.idx) for f in found] == [("A3", 7)]


def test_contract_a4_values_in_bounds_pass() -> None:
    assert rules(run(fixture(QUIET), Bounds()), "A4") == []


def test_contract_a4_hp_out_of_bounds_are_found() -> None:
    save = fixture(QUIET)
    state, _ = walk(save, [])
    hero = state.creatures["pc-p4"]
    over = HpChanged(creature_id="pc-p4", delta=1, new_hp=hero.max_hp + 1)
    assert [f.idx for f in Bounds().see(5, state, over)] == [5]
    hero.hp = -1
    assert Bounds().end(state)[0].rule == "A4"
