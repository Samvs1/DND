"""M29.2: what the full scripted campaigns showed the M29.1 metrics missed.

- A retried party wipe is cut from the main log into `events.<n>.defeat`; the metrics count it
  as a lost fight (`wipes`) and the balance aggregate puts it in the clean-win rate.
- A reward pays every hero (four heroes = four gold lines after one reward line), and camp food
  bought at a shop changes the supplies between the gold line and the trade line.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aidm.session.balance import aggregate, load_runs, outcomes
from aidm.session.metrics import compute_metrics, load_defeat_tails, load_events

Ev = dict[str, Any]


def _pc(i: int) -> Ev:
    pc = {"level": 2, "gold": 10}
    return {"type": "creature_added", "creature": {"id": f"pc-{i}", "kind": "pc", "pc": pc}}


def _hp(i: int, delta: int, new: int) -> Ev:
    return {"type": "hp_changed", "creature_id": f"pc-{i}", "delta": delta, "new_hp": new}


def _gold(i: int, delta: int, gold: int) -> Ev:
    return {"type": "gold_changed", "creature_id": f"pc-{i}", "delta": delta, "gold": gold}


def _fight_open() -> list[Ev]:
    offer = {"id": "o1", "boss_npc_id": None}
    return [
        {"type": "encounter_offered", "offer": offer},
        {"type": "offer_resolved", "offer_id": "o1"},
        {"type": "encounter_started"},
    ]


def _main() -> list[Ev]:
    heroes = [_pc(i) for i in range(4)]
    won = [_hp(0, -3, 7), {"type": "encounter_ended", "status": "victory"}]
    return heroes + _fight_open() + won


def _save(tmp: Path) -> Path:
    main = _main()
    cut = len(_main()) - 2  # the checkpoint: just after the fight started
    tail = [_hp(i, -10, 0) for i in range(4)] + [{"type": "encounter_ended", "status": "defeat"}]
    folder = tmp / "run"
    folder.mkdir()
    lines = [json.dumps({"seq": i, "event": e}) for i, e in enumerate(main)]
    (folder / "events.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    rows = [json.dumps({"seq": cut + i, "event": e}) for i, e in enumerate(tail)]
    (folder / "events.1.defeat").write_text("\n".join(rows) + "\n", encoding="utf-8")
    return folder


def test_m29_metrics_count_a_retried_wipe_as_a_lost_fight(tmp_path: Path) -> None:
    save = _save(tmp_path)
    tails = load_defeat_tails(save)
    assert [cut for cut, _ in tails] == [7]
    m = compute_metrics(load_events(save), tails)
    assert m["fights"]["count"] == 1 and m["fights"]["won"] == 1  # the main log: the retry won
    assert m["wipes"]["count"] == 1
    assert m["wipes"]["fights"] == [
        {
            "act": 1,
            "boss": False,
            "level": 2,
            "heroes_down": 4,
            "hp_lost": 40,
            "rounds": 0,
            "status": "defeat",
        }
    ]
    assert compute_metrics(load_events(save))["wipes"] == {"count": 0, "fights": []}


def test_m29_balance_puts_a_wipe_in_the_clean_win_rate(tmp_path: Path) -> None:
    runs = load_runs(_save(tmp_path))
    values = aggregate([metrics for _, _, metrics in runs])
    assert values["normal_clean_win_rate"] == 0.5  # one clean win, one wipe


def test_m29_metrics_reward_paid_to_four_heroes_is_attributed() -> None:
    reward = {"type": "reward_granted", "kind": "quest"}
    xp = [{"type": "xp_gained", "creature_id": f"pc-{i}", "amount": 50} for i in range(4)]
    gold = [_gold(i, 25, 35) for i in range(4)]
    m = compute_metrics([*(_pc(i) for i in range(4)), reward, *xp, *gold])
    assert m["gold"]["in"] == {"quest": 100}


def test_m29_metrics_camp_food_bought_is_a_shop_buy() -> None:
    supplies = {"type": "camp_supplies_changed", "delta": 3}
    trade = {"type": "items_traded", "sold": False}
    m = compute_metrics([_pc(0), _gold(0, -2, 8), supplies, trade])
    assert m["gold"]["out"] == {"shop_buy": 2}


def test_m29_outcomes_per_style_and_party() -> None:
    m = {"level_end": 3, "wipes": {"count": 2, "fights": []}}
    entries = [
        ({"style": "talker", "party": "solo", "outcome": "epilogue", "level": 5}, m),
        (
            {"style": "talker", "party": "solo", "outcome": "defeated act 2 at bridge", "level": 3},
            m,
        ),
        ({"style": "talker", "party": "solo", "outcome": "defeated act 2 at tower", "level": 4}, m),
    ]
    assert outcomes(entries) == [
        {
            "style": "talker",
            "party": "solo",
            "runs": 3,
            "epilogue": 1,
            "lost": {"act 2": 2},
            "level": 4,
            "wipes_per_run": 2.0,
        }
    ]
