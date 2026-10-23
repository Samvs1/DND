"""M29.1: metrics read from saves (goldens), the targets loader and the balance report."""

from __future__ import annotations

import json
from pathlib import Path

from aidm.data.balance_targets import load_balance_targets
from aidm.session.balance import evaluate, load_runs
from aidm.session.metrics import compute_metrics, load_events

SAVES = Path(__file__).resolve().parents[1] / "fixtures" / "saves"


def _m(name: str) -> dict:
    return compute_metrics(load_events(SAVES / name))


def test_golden_metrics_synthetic_save() -> None:
    # Counted by hand from synth-balanced: 2 heroes, 3 fights, hp lost 3+8+10, 2 downs.
    m = _m("synth-balanced")
    assert m["fights"]["count"] == 3 and m["fights"]["won"] == 3
    assert m["fights"]["rounds"] == 2 + 3 + 4
    assert m["fights"]["per_act"]["1"] == {"fights": 2, "won": 2, "won_clean": 1}
    assert m["hp_lost"] == 3 + 8 + 10 and m["downs"] == 2 and m["deaths"] == 1
    assert m["rests"] == {"short": 1, "long": 1}
    assert m["gold"]["in"] == {"loot": 40, "quest": 80, "shop_sell": 5}
    assert m["gold"]["out"] == {"shop_buy": 12}
    assert m["xp_per_act"] == {"1": 150}
    assert m["boss_fights"] == [{"act": 1, "level": 1, "heroes_down": 1}]
    assert m["level_end"] == 2 and m["quests"] == {"done": 1}
    assert m["item_uses"] == {"healing-potion": 2, "rope": 1} and m["item_refusals"] == 1
    assert m["gold_per_hero_act_end"] == {"1": 70}


def test_golden_metrics_owner_slendee_save() -> None:
    # Counted from the owner's c-20261010-161143-6031 events: 6 fights, 1 boss, 1 hero death.
    m = _m("real-slendee")
    assert m["events"] == 664
    assert m["fights"]["count"] == 6 and m["fights"]["won"] == 5
    assert m["boss_fights"] == [{"act": 1, "level": 2, "heroes_down": 0}]
    assert m["deaths"] == 1 and m["downs"] == 1 and m["rests"]["short"] == 2
    assert m["gold"]["in"] == {"loot": 60}
    assert m["ai"]["narrated_turns"] == 97


def test_golden_metrics_small_owner_save() -> None:
    m = _m("real-small")
    assert m["fights"]["count"] == 1 and m["gold"]["in"] == {"loot": 4}


def test_metrics_accept_events_file_and_do_not_mutate() -> None:
    path = SAVES / "synth-balanced" / "events.jsonl"
    before = path.read_bytes()
    assert compute_metrics(load_events(path)) == _m("synth-balanced")
    assert path.read_bytes() == before


def test_targets_loader() -> None:
    t = load_balance_targets()
    ids = {x.id for x in t.targets}
    assert {"normal_clean_win_rate", "boss_heroes_down_avg", "gold_act1_end"} <= ids
    win = next(x for x in t.targets if x.id == "normal_clean_win_rate")
    assert win.holds(0.8) and not win.holds(0.5) and not win.holds(0.95)
    assert win.applies("balanced", "classic_four") and not win.applies("aggressive", "solo")


def test_balance_report_pass_and_miss_on_fixture_folder() -> None:
    rows = evaluate(load_runs(SAVES), load_balance_targets())
    got = {(r["style"], r["target"]): r["verdict"] for r in rows}
    assert got[("balanced", "normal_clean_win_rate")] == "MISS"  # 1 clean of 2 normal fights
    assert got[("balanced", "boss_heroes_down_avg")] == "PASS"  # 1 down <= 1
    assert got[("balanced", "boss_level_act2")] == "N/A"
    assert json.dumps(rows)


def test_golden_master_levels_and_xp_sources() -> None:
    # M29.6b: the party's lowest level when each act's master is first offered (fight or talk),
    # and one hero's XP split into milestone / quest rewards (their xp_each) and the rest.
    synth, slendee = _m("synth-balanced"), _m("real-slendee")
    assert synth["master_levels"] == {"1": 1} and slendee["master_levels"] == {"1": 2}
    assert synth["xp_each_by_source"] == {"milestone": 0, "quest": 0, "other": 75}
    assert slendee["xp_each_by_source"]["milestone"] == 1200
    rows = evaluate(load_runs(SAVES), load_balance_targets())
    got = {(r["style"], r["target"]): (r["verdict"], r["value"]) for r in rows}
    assert got[("balanced", "master_level_act1")] == ("MISS", 1)  # level 1 < planned 2
