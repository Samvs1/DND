"""Aggregate many runs' metrics against the balance targets (M29.1). Pure over metrics dicts.

M29.2: `outcomes(entries)` summarises how scripted runs ended per (style, party), from each
run's `tags.json` (`outcome`, written by `scripts/sim/grid.py`) and its metrics (`wipes`).
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from statistics import median
from typing import Any

from aidm.data.balance_targets import BalanceTargets
from aidm.session.metrics import compute_metrics, load_defeat_tails, load_events

Metrics = dict[str, Any]


def find_saves(root: Path) -> list[Path]:
    """Save dirs or events files under `root` (a dir holding events.jsonl is one save)."""
    if root.is_file() or (root / "events.jsonl").exists():
        return [root]
    return sorted(p.parent for p in root.rglob("events.jsonl"))


def tags_of(save: Path) -> tuple[str, str]:
    """(style, party) from a `tags.json` next to the events, else ('untagged', 'untagged')."""
    folder = save if save.is_dir() else save.parent
    tag_file = folder / "tags.json"
    if tag_file.exists():
        raw = json.loads(tag_file.read_text(encoding="utf-8"))
        return str(raw.get("style", "untagged")), str(raw.get("party", "untagged"))
    return "untagged", "untagged"


def load_runs(root: Path) -> list[tuple[str, str, Metrics]]:
    return [
        (*tags_of(s), compute_metrics(load_events(s), load_defeat_tails(s)))
        for s in find_saves(root)
    ]


def aggregate(runs: list[Metrics]) -> dict[str, float]:
    """Target id -> value over the runs; ids with no data are left out (reported N/A).
    M29.2: a retried wipe counts as a lost fight (normal) or a boss fight with its downs.
    M29.6b: `master_level_act<n>` is the median level when the act's master is first offered."""
    out: dict[str, float] = {}
    lost = [f for r in runs for f in r.get("wipes", {}).get("fights", [])]
    normal = [f for r in runs for f in r["fights"]["list"] if not f["boss"]]
    normal += [f for f in lost if not f["boss"]]
    if normal:
        clean = sum(f["status"] == "victory" and f["heroes_down"] == 0 for f in normal)
        out["normal_clean_win_rate"] = clean / len(normal)
    bosses = [b for r in runs for b in r["boss_fights"]]
    bosses += [{k: f[k] for k in ("act", "level", "heroes_down")} for f in lost if f["boss"]]
    if bosses:
        out["boss_heroes_down_avg"] = sum(b["heroes_down"] for b in bosses) / len(bosses)
    for act in ("1", "2", "3"):
        levels = [b["level"] for b in bosses if str(b["act"]) == act]
        if levels:
            out[f"boss_level_act{act}"] = min(levels)
        met = [r["master_levels"][act] for r in runs if act in r.get("master_levels", {})]
        if met:
            out[f"master_level_act{act}"] = median(met)
        gold = [r["gold_per_hero_act_end"][act] for r in runs if act in r["gold_per_hero_act_end"]]
        if gold:
            out[f"gold_act{act}_end"] = median(gold)
    return out


def evaluate(runs: list[tuple[str, str, Metrics]], targets: BalanceTargets) -> list[dict[str, Any]]:
    """One row per (style, party, target): value and PASS / MISS / N/A."""
    groups: dict[tuple[str, str], list[Metrics]] = defaultdict(list)
    for style, party, metrics in runs:
        groups[(style, party)].append(metrics)
    rows: list[dict[str, Any]] = []
    for (style, party), members in sorted(groups.items()):
        values = aggregate(members)
        for t in targets.targets:
            if not t.applies(style, party):
                continue
            value = values.get(t.id)
            verdict = "N/A" if value is None else ("PASS" if t.holds(value) else "MISS")
            rows.append(
                {
                    "style": style,
                    "party": party,
                    "runs": len(members),
                    "target": t.id,
                    "value": value,
                    "min": t.min,
                    "max": t.max,
                    "verdict": verdict,
                }
            )
    return rows


def run_tags(save: Path) -> dict[str, Any]:
    """The whole `tags.json` beside a save ({} when there is none)."""
    folder = save if save.is_dir() else save.parent
    tag_file = folder / "tags.json"
    return dict(json.loads(tag_file.read_text(encoding="utf-8"))) if tag_file.exists() else {}


def _ended(outcome: str) -> str:
    """'epilogue', 'act N' (lost for good in act N) or 'other'."""
    if outcome == "epilogue":
        return "epilogue"
    words = outcome.split()
    return f"act {words[2]}" if outcome.startswith("defeated act") and len(words) > 2 else "other"


def outcomes(entries: list[tuple[dict[str, Any], Metrics]]) -> list[dict[str, Any]]:
    """Per (style, party): runs, how they ended, the median final level and wipes per run."""
    groups: dict[tuple[str, str], list[tuple[dict[str, Any], Metrics]]] = defaultdict(list)
    for tags, metrics in entries:
        key = (str(tags.get("style", "untagged")), str(tags.get("party", "untagged")))
        groups[key].append((tags, metrics))
    rows: list[dict[str, Any]] = []
    for (style, party), members in sorted(groups.items()):
        ends = [_ended(str(t.get("outcome", ""))) for t, _ in members]
        wipes = [m.get("wipes", {}).get("count", 0) for _, m in members]
        rows.append(
            {
                "style": style,
                "party": party,
                "runs": len(members),
                "epilogue": ends.count("epilogue"),
                "lost": {e: ends.count(e) for e in sorted(set(ends)) if e != "epilogue"},
                "level": median(int(t.get("level", m["level_end"])) for t, m in members),
                "wipes_per_run": sum(wipes) / len(members),
            }
        )
    return rows
