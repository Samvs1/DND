"""M5.3 campaign generator: one structured QUALITY call, validation, retry, fallback (FakeLLM)."""

import json
from pathlib import Path
from typing import Any

from aidm.dm.campaign_draft import CampaignDraft, assemble_plan
from aidm.dm.campaign_gen import (
    CampaignSource,
    campaign_messages,
    generate_campaign,
    is_surprise,
    plan_problems,
)
from aidm.dm.campaign_sample import load_sample_campaign
from aidm.dm.fake_llm import FakeLLM, FakeReply, fake_tool_call
from aidm.dm.llm_client import LlmClient
from aidm.dm.llm_log import LlmCallLog
from aidm.dm.llm_settings import LlmSettings
from aidm.dm.llm_types import LlmMode, LlmRole
from aidm.models.campaign import CampaignPlan
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


async def test_invalid_refs_are_fed_back_then_accepted(tmp_path: Path) -> None:
    good = draft_from_plan()
    client, fake = fake_client(tmp_path, [_submit(with_bad_theme(good)), _submit(good)])
    result = await generate_campaign("salt and storms", PARTY, client)
    assert result.source is CampaignSource.MODEL
    assert result.attempts == 2
    retry = fake.requests[1].messages
    feedback = str(retry[-1]["content"])
    assert "ENGINE VALIDATOR" in feedback and "tarrasque" in feedback
    assert retry[-2]["role"] == "assistant"


async def test_out_of_tier_theme_is_a_problem(tmp_path: Path) -> None:
    bad = with_bad_theme(draft_from_plan(), "shield-guardian")
    plan = assemble_plan(CampaignDraft.model_validate(bad))
    assert isinstance(plan, CampaignPlan)
    codes = {p.code for p in plan_problems(plan)}
    assert "theme_tier" in codes


async def test_repeated_invalid_falls_back_to_the_sample(tmp_path: Path) -> None:
    bad = with_bad_theme(draft_from_plan())
    client, fake = fake_client(tmp_path, [_submit(bad)] * 3)
    result = await generate_campaign("anything dark", PARTY, client)
    assert result.source is CampaignSource.FALLBACK
    assert result.plan == load_sample_campaign()
    assert result.attempts == 3 and len(fake.requests) == 3
    assert any(p.code == "unknown_monster" for p in result.problems)


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
    client, _ = fake_client(tmp_path)  # default script answers `{}`: always invalid
    result = await generate_campaign("frost", PARTY, client)
    assert result.source is CampaignSource.FALLBACK
    assert result.attempts == 1


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
