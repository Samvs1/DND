"""Raw loader for the built-in sample campaign: data/campaigns/sample_campaign.json (M5.1).

`aidm.data` may not import `aidm.models`, so this returns the parsed JSON; the typed plan is built
and validated by `aidm.dm.campaign_sample.load_sample_campaign`.

Public API: `SAMPLE_CAMPAIGN_PATH`, `load_sample_campaign_json(path=None) -> dict[str, object]`.
"""

from __future__ import annotations

import json
from pathlib import Path

SAMPLE_CAMPAIGN_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "campaigns" / "sample_campaign.json"
)


def load_sample_campaign_json(path: Path | None = None) -> dict[str, object]:
    target = path if path is not None else SAMPLE_CAMPAIGN_PATH
    raw: dict[str, object] = json.loads(target.read_text(encoding="utf-8"))
    return raw
