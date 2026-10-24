"""M31.1d: the master-fight metrics (party HP lost share) and the floor targets."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from aidm.data.balance_targets import load_balance_targets
from aidm.session.balance import aggregate, evaluate
from aidm.session.metrics import compute_metrics, load_events

SAVES = Path(__file__).resolve().parents[1] / "fixtures" / "saves"
Ev = dict[str, Any]


def _pc(i: int, max_hp: int) -> Ev:
    pc = {"level": 2, "gold": 10}
    creature = {"id": f"pc-{i}", "kind": "pc", "pc": pc, "max_hp": max_hp}
    return {"type": "creature_added", "creature": creature}


def _hp(i: int, delta: int, new: int) -> Ev:
    return {"type": "hp_changed", "creature_id": f"pc-{i}", "delta": delta, "new_hp": new}


def _master_fight(*hits: Ev) -> list[Ev]:
    offer = {"id": "o1", "boss_npc_id": "boss-1"}
    return [
        {"type": "encounter_offered", "offer": offer},
        {"type": "offer_resolved", "offer_id": "o1"},
        {"type": "encounter_started"},
        *hits,
        {"type": "encounter_ended", "status": "victory"},
    ]


def test_golden_m31_master_fight_hp_share() -> None:
    # Two heroes of 10 and 20 HP lose 6 and 3: 9 / 30 = 0.3 of the party's maximum.
    m = compute_metrics([_pc(0, 10), _pc(1, 20), *_master_fight(_hp(0, -6, 4), _hp(1, -3, 17))])
    assert m["boss_hp_shares"] == [0.3]
    assert aggregate([m])["boss_hp_lost_share"] == 0.3


def test_m31_hp_share_uses_the_level_up_maximum_and_caps_at_one() -> None:
    gain = {"type": "level_gained", "creature_id": "pc-0", "max_hp": 20, "pc": {"level": 3}}
    m = compute_metrics([_pc(0, 10), gain, *_master_fight(_hp(0, -20, 0), _hp(0, -5, 0))])
    assert m["boss_hp_shares"] == [1.0]


def test_m31_hp_share_is_unknown_without_hero_maximums() -> None:
    assert compute_metrics(load_events(SAVES / "synth-balanced"))["boss_hp_shares"] == []
    assert compute_metrics(load_events(SAVES / "real-slendee"))["boss_hp_shares"] == [0.0]


def test_m31_master_floor_targets_bound_both_sides() -> None:
    targets = {t.id: t for t in load_balance_targets().targets}
    cap, floor = targets["boss_heroes_down_avg"], targets["master_heroes_down_floor"]
    assert floor.metric_id == "boss_heroes_down_avg"
    assert floor.min is not None and floor.max is not None and cap.max is not None
    assert floor.max <= cap.max  # never above the existing cap
    share = targets["boss_hp_lost_share"]
    assert share.min is not None and share.max is None


def test_m31_floor_rows_in_the_report() -> None:
    m = compute_metrics([_pc(0, 10), _pc(1, 20), *_master_fight(_hp(0, -6, 4), _hp(1, -3, 17))])
    rows = evaluate([("balanced", "duo", m)], load_balance_targets())
    got = {r["target"]: r["verdict"] for r in rows}
    assert got["master_heroes_down_floor"] == "MISS"  # 0 heroes down < the floor
    assert got["boss_heroes_down_avg"] == "PASS"
    assert got["boss_hp_lost_share"] == "MISS"  # 0.3 of the party's hit points < 0.4
