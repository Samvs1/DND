"""M16.1 campaign writer repairs instead of rejecting: the three live probe failures (FakeLLM).

Probe (2026-10-09): attempt 1 lost a whole plan to over-long `npcs.N.role` / `voice_tag`;
attempt 2 sent one complete JSON object followed by extra data; a schema-valid plan failed
because a quest named the boss by a short form in `against`.
"""

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from aidm.dm.campaign_draft import CampaignDraft, NpcDraft, assemble_plan, fit_limits, trim_words
from aidm.dm.campaign_gen import CampaignSource, generate_campaign
from aidm.dm.fake_llm import fake_tool_call
from aidm.models.campaign import CampaignPlan, RevealKind
from tests.ai.campaign_fixtures import draft_from_plan
from tests.ai.fake_scripts import fake_client

PARTY = "four level-1 adventurers: fighter, rogue, cleric, wizard"
LONG_ROLE = "a wandering herbalist who knows every root and remedy of the marsh"
LONG_VOICE = "low and gravelly with a slow northern drawl"


def _plan(draft: dict[str, Any]) -> CampaignPlan:
    plan = assemble_plan(CampaignDraft.model_validate(draft))
    assert isinstance(plan, CampaignPlan), plan
    return plan


async def _first_try(tmp_path: Path, arguments: dict[str, Any] | str) -> CampaignPlan:
    client, fake = fake_client(tmp_path, [fake_tool_call("submit_result", arguments)])
    result = await generate_campaign("a drowned lighthouse", PARTY, client, seed=3)
    assert result.source is CampaignSource.MODEL, result.problems
    assert result.attempts == 1 and len(fake.requests) == 1
    return result.plan


async def test_v1_probe_overlong_role_and_voice_tag_are_trimmed(tmp_path: Path) -> None:
    draft = draft_from_plan()
    draft["npcs"][1]["role"] = LONG_ROLE
    draft["npcs"][1]["voice_tag"] = LONG_VOICE
    plan = await _first_try(tmp_path, draft)
    npc = plan.npcs[1]
    assert npc.role == "a wandering herbalist who knows every"
    assert npc.voice_tag == "low and gravelly with a slow"
    assert len(npc.role) <= 40 and len(npc.voice_tag) <= 30


async def test_v1_probe_trailing_extra_data_keeps_the_first_object(tmp_path: Path) -> None:
    raw = json.dumps(draft_from_plan()) + '\n{"title": "a second answer"}'
    plan = await _first_try(tmp_path, raw)
    assert plan.title == draft_from_plan()["title"]


async def test_v1_probe_quest_against_the_boss_short_name_is_dropped(tmp_path: Path) -> None:
    draft = draft_from_plan()
    boss = draft["acts"][0]["region"]["boss"]["name"]
    draft["quests"][1]["against"] = boss.split()[0]
    plan = await _first_try(tmp_path, draft)
    assert plan.quests[1].against_npc_id is None


def test_trim_words_cuts_at_a_word_boundary() -> None:
    assert trim_words("short", 10) == "short"
    assert trim_words("hello world, more words", 12) == "hello world"
    assert trim_words("x" * 50, 10) == "x" * 10
    assert trim_words("ab cd", 5) == "ab cd"
    assert trim_words("one two three", 7) == "one two"


def test_fit_limits_trims_strings_and_cuts_lists_only() -> None:
    data = {"name": "a b c d e", "tags": [1, 2, 3, 4], "n": 7, "keep": "long text here"}
    out = fit_limits(data, {"name": 4, "tags": 2, "n": 1})
    assert out == {"name": "a b", "tags": [1, 2], "n": 7, "keep": "long text here"}
    assert data["tags"] == [1, 2, 3, 4], "the input is not mutated"


def test_overlong_lists_are_cut_but_minimums_and_enums_still_reject() -> None:
    draft = draft_from_plan()
    draft["acts"][0]["region"]["terrain_tags"] = ["coast", "urban", "forest", "swamp", "hills"]
    draft["npcs"][0]["secrets"] = draft["npcs"][0]["secrets"] * 3
    parsed = CampaignDraft.model_validate(draft)
    assert len(parsed.acts[0].region.terrain_tags) == 4
    assert len(parsed.npcs[0].secrets) <= 2
    npc = dict(draft["npcs"][0])
    for field, value in (("role", ""), ("archetype_id", ""), ("name", "")):
        with pytest.raises(ValidationError):
            NpcDraft.model_validate({**npc, field: value})
    bad_enum = copy.deepcopy(draft)
    bad_enum["quests"][0]["reward_tier"] = "legendary-ish"
    with pytest.raises(ValidationError):
        CampaignDraft.model_validate(bad_enum)
    missing = {k: v for k, v in npc.items() if k != "motive"}
    with pytest.raises(ValidationError):
        NpcDraft.model_validate(missing)


def test_short_names_resolve_to_the_one_matching_npc() -> None:
    draft = draft_from_plan()
    draft["quests"][0]["giver"] = "tobin"
    draft["quests"][1]["against"] = "Fenwick"
    draft["npcs"][0]["home_place"] = draft["acts"][0]["region"]["arrival"]["name"].upper()
    draft["rival_name"] = "Dray"
    plan = _plan(draft)
    assert plan.quests[0].giver_npc_id == "tobin-marrow"
    assert plan.quests[1].against_npc_id == "fenwick-dray"
    assert plan.rival is not None and plan.rival.npc_id == "fenwick-dray"


def test_unresolved_optional_references_are_dropped() -> None:
    draft = draft_from_plan()
    draft["quests"][1]["against"] = "Nobody At All"
    draft["rival_name"] = "A Stranger"
    secret = draft["npcs"][0]["secrets"][0]
    draft["npcs"][0]["secrets"][0] = {
        "text": secret["text"],
        "reveal_kind": "quest_completed",
        "quest_title": "A Quest Nobody Wrote",
    }
    plan = _plan(draft)
    assert plan.quests[1].against_npc_id is None
    assert plan.rival is None
    reveal = plan.npcs[0].secrets[0].reveal
    assert reveal.kind is RevealKind.ATTITUDE and reveal.band is not None


def test_ambiguous_or_required_unresolved_names_still_report() -> None:
    draft = draft_from_plan()
    draft["quests"][0]["giver"] = "Nobody At All"
    problems = assemble_plan(CampaignDraft.model_validate(draft))
    assert isinstance(problems, list)
    assert [p.code for p in problems] == ["unknown_reference"]
    assert "quest giver" in problems[0].message
    boss_giver = draft_from_plan()
    boss_giver["quests"][0]["giver"] = boss_giver["acts"][0]["region"]["boss"]["name"]
    assert isinstance(assemble_plan(CampaignDraft.model_validate(boss_giver)), list)


def test_secret_item_and_quest_titles_resolve_leniently() -> None:
    draft = draft_from_plan()
    reward = next(q["reward_item"] for q in draft["quests"] if q["reward_item"])
    title = draft["quests"][0]["title"]
    draft["npcs"][0]["secrets"] = [
        {"text": "one", "reveal_kind": "item_shown", "item": reward.lower()},
        {"text": "two", "reveal_kind": "quest_completed", "quest_title": title.upper()},
    ]
    plan = _plan(draft)
    first, second = (s.reveal for s in plan.npcs[0].secrets)
    assert first.kind is RevealKind.ITEM_SHOWN and first.item == reward
    assert second.kind is RevealKind.QUEST_COMPLETED and second.quest_id == plan.quests[0].id
