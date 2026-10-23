"""M29.2: full scripted campaigns to the epilogue, per play style and party shape (fake AI).

The two runs use the host's monster difficulty at 0.25 so the party wins and the whole path is
exercised every time (three regions, the master of each, the finale card and the epilogue);
the baseline (docs/playtests/M29_baseline.md) plays at the default 1.0.
"""

import json
from pathlib import Path

import pytest

from aidm.session.balance import load_runs
from aidm.session.metrics import load_events
from scripts.sim.grid import run_campaign
from scripts.sim.run import SimOptions

EASY = 0.25


@pytest.mark.sim
async def test_m29_full_campaign_classic_reaches_the_epilogue(tmp_path: Path) -> None:
    report = await run_campaign(1, "balanced", "classic", SimOptions(timeout=30.0), tmp_path, EASY)
    assert report.ok, "\n".join(report.failures)
    assert report.outcome == "epilogue"
    assert report.level >= 3 and report.combats >= 6
    run = tmp_path / "balanced-classic-s1"
    tags = json.loads((run / "tags.json").read_text(encoding="utf-8"))
    assert tags["style"] == "balanced" and tags["party"] == "classic"
    assert tags["outcome"] == "epilogue" and tags["failures"] == 0
    [(style, party, metrics)] = load_runs(tmp_path)
    assert (style, party) == ("balanced", "classic")
    assert set(metrics["level_per_act_end"]) == {"1", "2", "3"}
    assert [b["act"] for b in metrics["boss_fights"]] == [1, 2, 3]


@pytest.mark.sim
async def test_m29_solo_talker_campaign_parleys_to_the_epilogue(tmp_path: Path) -> None:
    report = await run_campaign(1, "talker", "solo", SimOptions(timeout=30.0), tmp_path, EASY)
    assert report.ok, "\n".join(report.failures)
    assert report.outcome == "epilogue"
    events = load_events(tmp_path / "talker-solo-s1")
    parleys = [e for e in events if e["type"] == "offer_resolved" and e["choice"] == "parley"]
    assert parleys, "the talker never parleyed"
    assert sum(e["type"] == "region_resolved" for e in events) == 3
