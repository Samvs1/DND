"""Live campaign generation (M5.7, SPEC 9, 13 Live): skipped unless RUN_LIVE=1 (tests/conftest.py).

One structured QUALITY call (plus bounded retries) with the real DeepSeek model. The key comes
from the environment or the gitignored .env (read by name, never printed).
"""

import dataclasses
import json
from collections.abc import AsyncIterator, Callable
from pathlib import Path

import pytest

from aidm.dm.campaign_gen import CampaignSource, generate_campaign, plan_problems
from aidm.dm.llm_client import LlmClient
from aidm.dm.llm_factory import make_llm_client
from aidm.dm.llm_settings import llm_settings_from_env
from aidm.dm.llm_types import LlmMode
from aidm.models.campaign import CampaignPlan
from aidm.models.quests import RouteKind
from aidm.rules.quest_plan import main_quests, quest_steps

THEME = "a haunted river delta"
PARTY = "four level-1 adventurers: fighter, rogue, cleric, wizard"
SEED = 5
# The campaign draft is ~3.3k output tokens: deepseek-v4-pro needs 43 to 45 s per call, which is
# the default 45 s client timeout (a live run fell back with `tools:timeout:45011ms`), so this
# test allows a generous timeout; raising the production budget for this call is logged in
# PROGRESS Notes (M5.7) for hard-engineer.
CAMPAIGN_TIMEOUT_S = 150.0


@pytest.fixture
async def client(tmp_path: Path, live_env: dict[str, str]) -> AsyncIterator[LlmClient]:
    settings = dataclasses.replace(
        llm_settings_from_env(live_env),
        log_path=tmp_path / "llm.jsonl",
        fake=False,
        timeout_s=CAMPAIGN_TIMEOUT_S,
    )
    client = make_llm_client(settings)
    if client.mode is not LlmMode.LIVE:
        pytest.fail("RUN_LIVE=1 needs DEEPSEEK_API_KEY in the environment or .env")
    await client.discover_models()
    yield client
    await client.aclose()


def _call_outcomes(log: Path) -> list[str]:
    """The outcome of every logged call (the log holds no keys and no player text)."""
    if not log.exists():
        return []
    rows = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line]
    return [
        f"{r.get('kind')}:{r.get('outcome')}:{r.get('latency_ms')}ms:"
        f"{r.get('completion_tokens')}tok"
        for r in rows
    ]


def _quest_report(plan: CampaignPlan) -> list[str]:
    """Per act: side quests with their step counts, the Peace route, Cunning, then the finale."""
    lines = []
    for main in main_quests(plan):
        sides = [len(quest_steps(plan, q)) for q in plan.quests if q.act == main.act]
        peace = next((r for r in main.routes if r.kind is RouteKind.PEACE), None)
        cunning = next((r for r in main.routes if r.kind is RouteKind.CUNNING), None)
        lines.append(
            f"act {main.act}: side quests {len(sides)} steps {sides}; "
            f"peace {[s.kind.value for s in peace.steps] if peace else None}; "
            f"cunning {cunning.effect if cunning else None}"
        )
    finale = plan.finale
    ends = [o.title for o in finale.options] if finale else []
    lines.append(f"finale: {finale.question if finale else None} -> {ends}")
    return lines


async def test_live_campaign_generation_returns_a_valid_model_plan(
    client: LlmClient, tmp_path: Path, live_say: Callable[[str], None]
) -> None:
    result = await generate_campaign(THEME, PARTY, client, seed=SEED)
    why = [f"{p.code}: {p.message}" for p in result.problems][:5]
    why += _call_outcomes(tmp_path / "llm.jsonl")
    live_say(
        f"LIVE campaign: source={result.source.value} attempts={result.attempts} "
        f"title={result.plan.title!r} problems={why}"
    )
    assert plan_problems(result.plan, SEED) == [], "the returned plan must validate"
    assert result.source is CampaignSource.MODEL, f"fell back to the sample: {why}"
    assert len(result.plan.acts) == 3 and len(result.plan.npcs) >= 1
    for line in _quest_report(result.plan):
        live_say(f"LIVE campaign quests: {line}")
    live_say(f"LIVE campaign repairs: {[p.message for p in result.problems]}")
    mains = main_quests(result.plan)  # M23.6 soft checks: every act derives a main quest
    assert len(mains) == 3 and all(m.routes for m in mains)
