"""M5.3 campaign generator: one structured QUALITY call, validation, retry, fallback (FakeLLM)."""

import json
from pathlib import Path
from typing import Any

import pytest

from aidm.dm import campaign_gen
from aidm.dm.campaign_draft import CampaignDraft, assemble_plan
from aidm.dm.campaign_gen import (
    CAMPAIGN_TIMEOUT_S,
    CampaignSource,
    campaign_messages,
    generate_campaign,
    is_surprise,
    plan_problems,
)
from aidm.dm.campaign_sample import load_sample_campaign
from aidm.dm.fake_llm import FakeHang, FakeLLM, FakeReply, fake_tool_call
from aidm.dm.llm_client import LlmClient
from aidm.dm.llm_log import LlmCallLog
from aidm.dm.llm_settings import LlmSettings
from aidm.dm.llm_types import LlmMode, LlmRole
from aidm.models.campaign import CampaignPlan
from aidm.models.problem import Problem
from tests.ai.campaign_fixtures import draft_from_plan, with_bad_theme
from tests.ai.fake_scripts import fake_client

PARTY = "four level-1 adventurers: fighter, rogue, cleric, wizard"


def _submit(draft: dict[str, Any]) -> FakeReply:
    return fake_tool_call("submit_result", draft)


async def test_valid_draft_is_accepted_first_try(tmp_path: Path) -> None:
    client, fake = fake_client(tmp_path, [_submit(draft_from_plan())])
    result = await generate_campaign("a drowned lighthouse", PARTY, client, seed=3)
    assert result.source is CampaignSource.MODEL
    assert result.attempts == 1 and result.problems == ()
    assert result.plan.title == load_sample_campaign().title
    assert plan_problems(result.plan, 3) == []
    assert len(fake.requests) == 1
    request = fake.requests[0]
    assert request.model == client.model_for(LlmRole.QUALITY)
    assert request.tool_choice == "submit_result"
    assert request.timeout_s == CAMPAIGN_TIMEOUT_S > client.settings.timeout_s


async def test_campaign_call_has_its_own_timeout(tmp_path: Path) -> None:
    """A timed-out call spends one plan attempt and the next asks again (M35.4, Y20)."""
    client, fake = fake_client(tmp_path, [FakeHang(0.3), _submit(draft_from_plan())])
    quick = await generate_campaign("x", PARTY, client, timeout_s=0.05)
    assert quick.source is CampaignSource.MODEL and quick.attempts == 2
    assert fake.requests[0].timeout_s == 0.05 and len(fake.requests) == 2


def _graph_problem(monkeypatch: pytest.MonkeyPatch, times: int) -> None:
    """A region-graph problem on the first `times` checks (repair fixes every reference, so a
    rejection is tested by stubbing the structural check)."""
    calls = {"n": 0}
    problem = Problem(code="softlock", message="glutmere: the gateway cannot be reached")

    def fake_problems(plan: CampaignPlan, seed: int = 0) -> list[Problem]:
        calls["n"] += 1
        return [problem] if calls["n"] <= times else []

    monkeypatch.setattr(campaign_gen, "plan_problems", fake_problems)


async def test_structural_problems_are_fed_back_then_accepted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _graph_problem(monkeypatch, 1)
    good = draft_from_plan()
    client, fake = fake_client(tmp_path, [_submit(good), _submit(good)])
    result = await generate_campaign("salt and storms", PARTY, client)
    assert result.source is CampaignSource.MODEL
    assert result.attempts == 2
    retry = fake.requests[1].messages
    feedback = str(retry[-1]["content"])
    assert "ENGINE VALIDATOR" in feedback and "gateway cannot be reached" in feedback
    assert retry[-2]["role"] == "assistant"


async def test_unknown_theme_is_repaired_without_a_retry(tmp_path: Path) -> None:
    client, fake = fake_client(tmp_path, [_submit(with_bad_theme(draft_from_plan()))])
    result = await generate_campaign("salt and storms", PARTY, client)
    assert result.source is CampaignSource.MODEL
    assert result.attempts == 1 and len(fake.requests) == 1
    assert any(p.code == "plan_repair" and "tarrasque" in p.message for p in result.problems)
    assert plan_problems(result.plan) == []


async def test_out_of_tier_theme_is_a_problem(tmp_path: Path) -> None:
    bad = with_bad_theme(draft_from_plan(), "shield-guardian")
    plan = assemble_plan(CampaignDraft.model_validate(bad))
    assert isinstance(plan, CampaignPlan)
    codes = {p.code for p in plan_problems(plan)}
    assert "theme_tier" in codes


async def test_repeated_invalid_falls_back_to_the_sample(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _graph_problem(monkeypatch, 99)
    client, fake = fake_client(tmp_path, [_submit(draft_from_plan())] * 3)
    result = await generate_campaign("anything dark", PARTY, client)
    assert result.source is CampaignSource.FALLBACK
    assert result.plan == load_sample_campaign()
    assert result.attempts == 3 and len(fake.requests) == 3
    assert [p.code for p in result.problems] == ["softlock"]


async def test_unknown_name_reference_is_reported() -> None:
    draft = draft_from_plan()
    draft["npcs"][0]["home_place"] = "Nowhere Hollow"
    assembled = assemble_plan(CampaignDraft.model_validate(draft))
    assert isinstance(assembled, list)
    assert assembled[0].code == "unknown_reference"
    assert "Nowhere Hollow" in assembled[0].message


async def test_structural_error_becomes_a_problem() -> None:
    draft = draft_from_plan()
    draft["acts"][0]["region"]["arrival"]["encounter_themes"] = ["giant-rat"]
    assembled = assemble_plan(CampaignDraft.model_validate(draft))
    assert isinstance(assembled, list)
    assert assembled[0].code == "invalid_plan"
    assert "arrival" in assembled[0].message


async def test_llm_disabled_falls_back_without_a_call(tmp_path: Path) -> None:
    settings = LlmSettings(api_key=None, log_path=tmp_path / "llm.jsonl")
    fake = FakeLLM()
    client = LlmClient(fake, settings, LlmMode.DISABLED, LlmCallLog(settings.log_path))
    result = await generate_campaign(None, PARTY, client)
    assert result.source is CampaignSource.FALLBACK
    assert result.attempts == 0 and fake.requests == []
    assert result.plan == load_sample_campaign()


async def test_llm_failure_falls_back(tmp_path: Path) -> None:
    client, fake = fake_client(tmp_path)  # default script answers `{}`: always invalid
    result = await generate_campaign("frost", PARTY, client)
    assert result.source is CampaignSource.FALLBACK
    # M35.4: every plan attempt is tried; the bound is 3 attempts x 3 client tries = 9 calls.
    assert result.attempts == 3 and len(fake.requests) == 9
    assert [p.code for p in result.problems] == ["llm_failure"]


async def test_surprise_me_lets_the_model_pick(tmp_path: Path) -> None:
    for theme in (None, "", "Surprise me!", "surprise me"):
        assert is_surprise(theme)
    assert not is_surprise("pirates in the fog")
    client, fake = fake_client(tmp_path, [_submit(draft_from_plan())])
    result = await generate_campaign("Surprise me", PARTY, client)
    assert result.source is CampaignSource.MODEL
    user = str(fake.requests[0].messages[1]["content"])
    assert "Choose an original theme yourself" in user
    assert PARTY in user


def test_prompt_lists_candidates_per_tier_and_quotes_the_theme() -> None:
    user = str(campaign_messages("ghost ships", PARTY)[1]["content"])
    assert "THEME (from the host" in user and "ghost ships" in user
    for line in ("tier 1:", "tier 2:", "tier 3:", "## NPC ARCHETYPES", "## TERRAINS"):
        assert line in user
    assert "giant-rat" in user and "commoner" in user


def test_every_boss_keeps_its_defeat_path() -> None:
    plan = assemble_plan(CampaignDraft.model_validate(draft_from_plan()))
    assert isinstance(plan, CampaignPlan)
    assert all(
        r.boss.defeat_always and r.boss.lair_node == r.gateway.id for r in plan.all_regions()
    )
    assert json.loads(plan.model_dump_json())["acts"][0]["region"]["tier"] == 1
