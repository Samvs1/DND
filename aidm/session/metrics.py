"""Balance metrics read from a save's events.jsonl (M29.1). Read-only: never mutates a save.

`compute_metrics(events)` takes the unwrapped event dicts (`load_events` strips the {seq, event}
wrapper) and returns one JSON-able object. Notes on what a log can and cannot say:
- Gold is attributed to a source: a `reward_granted` just before the `gold_changed` (loot, quest,
  milestone), or an `items_traded` / `character_rewritten` just after it (shop buy/sell, Scribe).
- Server exceptions and AI fallback notices are not events, so they are reported as `unrecorded`.
- The act is 1 + the number of `region_resolved` events so far.
- M29.6b: `master_levels` is the party's lowest level when each act's master is first offered
  (fight and talk paths alike); `xp_each_by_source` splits one hero's XP into milestone and
  quest rewards (their `xp_each`) and the rest (fights and storyteller grants).
- M29.2: a party wipe that was retried leaves its discarded tail in `events.<n>.defeat`
  (`load_defeat_tails`); `compute_metrics(events, tails)` reports each as a lost fight under
  `wipes` (the main log alone only shows the retry that was won). A tail's first `seq` is the
  position in the main log where it was cut (the main log's seq is its line index).
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

Event = dict[str, Any]
_GOLD_PASS = {
    "gold_changed",
    "camp_supplies_changed",
    "inventory_changed",
    "equipment_changed",
    "item_removed",
    "item_placed",
}


_GOLD_BACK = 64  # a reward pays every hero: one gold and xp event each after the reward line


def load_events(path: Path) -> list[Event]:
    """Events of a save dir or an events.jsonl file (a line is {seq, event} or a bare event)."""
    file = path / "events.jsonl" if path.is_dir() else path
    out: list[Event] = []
    for line in file.read_text(encoding="utf-8").splitlines():
        if line.strip():
            raw = json.loads(line)
            out.append(raw.get("event", raw))
    return out


def _gold_source(events: list[Event], i: int) -> str:
    for back in range(1, _GOLD_BACK):
        if i - back < 0:
            break
        prev = events[i - back]
        if prev["type"] == "reward_granted":
            return str(prev["kind"])
        if prev["type"] not in ("gold_changed", "xp_gained"):
            break
    for nxt in events[i + 1 :]:
        if nxt["type"] == "items_traded":
            return "shop_sell" if nxt.get("sold") else "shop_buy"
        if nxt["type"] == "character_rewritten":
            return "scribe"
        if nxt["type"] not in _GOLD_PASS:
            break
    return "other"


class _Run:
    def __init__(self) -> None:
        self.act = 1
        self.pcs: set[str] = set()
        self.levels: dict[str, int] = {}
        self.offers: dict[str, Event] = {}
        self.boss_offer = False
        self.fight: Event | None = None
        self.fights: list[Event] = []
        self.gold_in: Counter[str] = Counter()
        self.gold_out: Counter[str] = Counter()
        self.xp: Counter[int] = Counter()
        self.act_levels: dict[int, int] = {}
        self.purse: dict[str, int] = {}
        self.act_gold: dict[int, int] = {}
        self.quests: dict[str, str] = {}
        self.items: Counter[str] = Counter()
        self.counts: Counter[str] = Counter()
        self.master_levels: dict[int, int] = {}
        self.reward_xp: Counter[str] = Counter()

    def min_level(self) -> int:
        return min((self.levels[p] for p in self.pcs if p in self.levels), default=1)

    def creature_added(self, e: Event) -> None:
        c = e["creature"]
        if c.get("kind") == "pc":
            self.pcs.add(c["id"])
            self.levels[c["id"]] = (c.get("pc") or {}).get("level", 1)
            self.purse[c["id"]] = (c.get("pc") or {}).get("gold", 0)

    def hp(self, e: Event) -> None:
        if e["creature_id"] in self.pcs and e["delta"] < 0:
            self.counts["hp_lost"] += -e["delta"]
            if e["new_hp"] == 0:
                self.counts["downs"] += 1
            if self.fight is not None:
                self.fight["hp_lost"] += -e["delta"]
                if e["new_hp"] == 0:
                    self.fight["heroes_down"] += 1

    def start_fight(self) -> None:
        self.fight = {
            "act": self.act,
            "boss": self.boss_offer,
            "rounds": 0,
            "hp_lost": 0,
            "heroes_down": 0,
            "level": self.min_level(),
            "status": "open",
        }

    def end_fight(self, e: Event) -> None:
        if self.fight is None:
            return
        self.fight["status"] = e["status"]
        self.fights.append(self.fight)
        self.fight = None
        self.boss_offer = False

    def step(self, events: list[Event], i: int) -> None:
        e = events[i]
        t = e["type"]
        self.counts[t] += 1
        if t == "creature_added":
            self.creature_added(e)
        elif t == "level_gained" and e["creature_id"] in self.pcs:
            self.levels[e["creature_id"]] = e["pc"]["level"]
        elif t == "encounter_offered":
            self.offers[e["offer"]["id"]] = e["offer"]
            if e["offer"].get("boss_npc_id") is not None:
                self.master_levels.setdefault(self.act, self.min_level())
        elif t == "reward_granted" and e.get("kind") in ("milestone", "quest"):
            self.reward_xp[e["kind"]] += e.get("xp_each", 0)
        elif t == "offer_resolved":
            offer = self.offers.get(e["offer_id"], {})
            self.boss_offer = offer.get("boss_npc_id") is not None
        elif t == "encounter_started":
            self.start_fight()
        elif t == "turn_started" and self.fight is not None:
            self.fight["rounds"] = max(self.fight["rounds"], e["round"])
        elif t == "encounter_ended":
            self.end_fight(e)
        elif t == "hp_changed":
            self.hp(e)
        elif t == "xp_gained" and e["creature_id"] in self.pcs:
            self.xp[self.act] += e["amount"]
        elif t == "gold_changed":
            self.purse[e["creature_id"]] = e["gold"]
            bucket = self.gold_in if e["delta"] > 0 else self.gold_out
            bucket[_gold_source(events, i)] += abs(e["delta"])
        elif t == "quest_updated":
            self.quests[e["quest"]["id"]] = e["quest"]["state"]
        elif t == "item_used":
            self.items[e["item"]] += 1
        elif t == "region_resolved":
            self.act_levels[self.act] = self.min_level()
            wallet = sorted(self.purse[p] for p in self.pcs if p in self.purse)
            self.act_gold[self.act] = wallet[len(wallet) // 2] if wallet else 0
            self.act += 1


def _act_block(fights: list[Event], act: int) -> dict[str, Any]:
    mine = [f for f in fights if f["act"] == act and not f["boss"]]
    won = [f for f in mine if f["status"] == "victory"]
    clean = [f for f in won if f["heroes_down"] == 0]
    return {"fights": len(mine), "won": len(won), "won_clean": len(clean)}


def load_defeat_tails(path: Path) -> list[tuple[int, list[Event]]]:
    """(cut position, events) of every `events.<n>.defeat` beside a save's log, by attempt."""
    folder = path if path.is_dir() else path.parent

    def attempt(file: Path) -> int:
        middle = file.name.split(".")[1]
        return int(middle) if middle.isdigit() else 0

    out: list[tuple[int, list[Event]]] = []
    for file in sorted(folder.glob("events.*.defeat"), key=attempt):
        rows = [json.loads(x) for x in file.read_text(encoding="utf-8").splitlines() if x.strip()]
        if rows:
            out.append((int(rows[0].get("seq", 0)), [r.get("event", r) for r in rows]))
    return out


def _lost_fight(events: list[Event], cut: int, tail: list[Event]) -> Event | None:
    run = _Run()
    merged = events[:cut] + tail
    for i in range(len(merged)):
        run.step(merged, i)
    last = run.fight or (run.fights[-1] if run.fights else None)
    if last is None:
        return None
    keep = ("act", "boss", "level", "heroes_down", "hp_lost", "rounds")
    return {**{k: last[k] for k in keep}, "status": "defeat"}


def _wipes(events: list[Event], tails: list[tuple[int, list[Event]]]) -> dict[str, Any]:
    lost = [f for cut, tail in tails if (f := _lost_fight(events, cut, tail)) is not None]
    return {"count": len(tails), "fights": lost}


def compute_metrics(
    events: list[Event], tails: list[tuple[int, list[Event]]] | None = None
) -> dict[str, Any]:
    run = _Run()
    for i in range(len(events)):
        run.step(events, i)
    c = run.counts
    fights = run.fights
    acts = sorted({f["act"] for f in fights} | set(run.xp))
    bosses = [f for f in fights if f["boss"]]
    return {
        "events": len(events),
        "fights": {
            "count": len(fights),
            "won": sum(f["status"] == "victory" for f in fights),
            "rounds": sum(f["rounds"] for f in fights),
            "per_act": {str(a): _act_block(fights, a) for a in acts},
            "list": fights,
        },
        "hp_lost": c["hp_lost"],
        "downs": c["downs"],
        "deaths": _pc_deaths(events, run.pcs),
        "rests": {"short": c["short_rest_taken"], "long": c["long_rest_taken"]},
        "gold": {"in": dict(run.gold_in), "out": dict(run.gold_out)},
        "xp_per_act": {str(a): run.xp[a] for a in acts},
        "level_end": run.min_level(),
        "level_per_act_end": {str(a): v for a, v in run.act_levels.items()},
        "gold_per_hero_act_end": {str(a): v for a, v in run.act_gold.items()},
        "boss_fights": [
            {"act": b["act"], "level": b["level"], "heroes_down": b["heroes_down"]} for b in bosses
        ],
        "master_levels": {str(a): v for a, v in sorted(run.master_levels.items())},
        "xp_each_by_source": _xp_sources(run),
        "wipes": _wipes(events, tails or []),
        "quests": dict(Counter(run.quests.values())),
        "item_uses": dict(run.items),
        "item_refusals": c["item_use_refused"],
        "ai": {
            "narrated_turns": c["narration_recorded"],
            "unrecorded": ["fallbacks", "exceptions"],
        },
    }


def _xp_sources(run: _Run) -> dict[str, int]:
    heroes = max(1, len(run.pcs))
    each = sum(run.xp.values()) // heroes
    rewards = {k: run.reward_xp[k] for k in ("milestone", "quest")}
    return {**rewards, "other": max(0, each - sum(rewards.values()))}


def _pc_deaths(events: list[Event], pcs: set[str]) -> int:
    return sum(1 for e in events if e["type"] == "creature_died" and e["creature_id"] in pcs)
