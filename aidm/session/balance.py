"""Aggregate many runs' metrics against the balance targets (M29.1). Pure over metrics dicts."""

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
    M29.2: a retried wipe counts as a lost fight (normal) or a boss fight with its downs."""
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
