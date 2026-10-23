"""The built-in sample campaign: the fallback when the LLM is unavailable (M5.1, SPEC 9).

Public API: `load_sample_campaign(path=None) -> CampaignPlan` (validated structurally by the
model, against the data registries by `aidm.rules.campaign_check` and its quests by
`aidm.rules.quest_check`; a broken file raises `ValueError`, which a test guards). M29.9b: it
goes through the same plan repairs as a model plan (`aidm.rules.plan_repair`), so its step
lines are the engine's too.
"""

from __future__ import annotations

from pathlib import Path

from aidm.data.campaign_data import load_sample_campaign_json
from aidm.models.campaign import CampaignPlan
from aidm.rules.campaign_check import check_plan_refs
from aidm.rules.plan_repair import repair_plan
from aidm.rules.quest_check import check_plan_quests


def load_sample_campaign(path: Path | None = None) -> CampaignPlan:
    plan = repair_plan(CampaignPlan.model_validate(load_sample_campaign_json(path)), [])
    problems = check_plan_refs(plan) + check_plan_quests(plan)
    if problems:
        raise ValueError("; ".join(p.message for p in problems))
    return plan
