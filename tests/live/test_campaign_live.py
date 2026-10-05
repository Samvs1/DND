"""Live campaign generation (M5.7, SPEC 9, 13 Live): skipped unless RUN_LIVE=1 (tests/conftest.py).

One structured QUALITY call (plus bounded retries) with the real DeepSeek model. The key comes
from the environment or the gitignored .env (read by name, never printed).
"""

import dataclasses
import json
import os
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from dotenv import dotenv_values

from aidm.dm.campaign_gen import CampaignSource, generate_campaign, plan_problems
from aidm.dm.llm_client import LlmClient
from aidm.dm.llm_factory import make_llm_client
from aidm.dm.llm_settings import llm_settings_from_env
from aidm.dm.llm_types import LlmMode

ROOT = Path(__file__).resolve().parents[2]
THEME = "a haunted river delta"
PARTY = "four level-1 adventurers: fighter, rogue, cleric, wizard"
SEED = 5
# The campaign draft is ~3.3k output tokens: deepseek-v4-pro needs 43 to 45 s per call, which is
# the default 45 s client timeout (a live run fell back with `tools:timeout:45011ms`), so this
# test allows a generous timeout; raising the production budget for this call is logged in
# PROGRESS Notes (M5.7) for hard-engineer.
CAMPAIGN_TIMEOUT_S = 150.0


def _environ() -> dict[str, str]:
    values = {k: v for k, v in dotenv_values(ROOT / ".env").items() if v is not None}
    return {**values, **os.environ}


@pytest.fixture
async def client(tmp_path: Path) -> AsyncIterator[LlmClient]:
    settings = dataclasses.replace(
        llm_settings_from_env(_environ()),
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
    return [f"{r.get('kind')}:{r.get('outcome')}:{r.get('latency_ms')}ms" for r in rows]


async def test_live_campaign_generation_returns_a_valid_model_plan(
    client: LlmClient, tmp_path: Path
) -> None:
    result = await generate_campaign(THEME, PARTY, client, seed=SEED)
    why = [f"{p.code}: {p.message}" for p in result.problems][:5]
    why += _call_outcomes(tmp_path / "llm.jsonl")
    print(
        f"LIVE campaign: source={result.source.value} attempts={result.attempts} "
        f"title={result.plan.title!r} problems={why}"
    )
    assert plan_problems(result.plan, SEED) == [], "the returned plan must validate"
    assert result.source is CampaignSource.MODEL, f"fell back to the sample: {why}"
    assert len(result.plan.acts) == 3 and len(result.plan.npcs) >= 1
