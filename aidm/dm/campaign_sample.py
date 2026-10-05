"""The built-in sample campaign: the fallback when the LLM is unavailable (M5.1, SPEC 9).

Public API: `load_sample_campaign(path=None) -> CampaignPlan` (validated structurally by the
model and against the data registries by `aidm.rules.campaign_check`; a broken file raises
`ValueError`, which a test guards).
"""

from __future__ import annotations

from pathlib import Path

from aidm.data.campaign_data import load_sample_campaign_json
from aidm.models.campaign import CampaignPlan
from aidm.rules.campaign_check import check_plan_refs


def load_sample_campaign(path: Path | None = None) -> CampaignPlan:
    plan = CampaignPlan.model_validate(load_sample_campaign_json(path))
    problems = check_plan_refs(plan)
    if problems:
        raise ValueError("; ".join(p.message for p in problems))
    return plan
