"""M35.4 (Y20): campaign generation retries a broken reply and repairs small plan defects.

Round 6 fell back to the sample campaign twice: three malformed JSON replies inside one attempt
(the generator gave up at once), and a whole plan thrown away for one wrong-tier monster. FakeLLM
only, no network.
"""

import copy
from pathlib import Path
from typing import Any

from aidm.data.encounter_monsters import encounter_monsters
from aidm.data.srd import srd
from aidm.dm.campaign_draft import CampaignDraft, assemble_plan
from aidm.dm.campaign_gen import CampaignSource, generate_campaign, plan_problems
from aidm.dm.campaign_refs import repair_draft_refs
from aidm.dm.campaign_sample import load_sample_campaign
from aidm.dm.fake_llm import FakeReply, fake_malformed, fake_tool_call
from aidm.models.campaign import CampaignPlan
from aidm.models.problem import Problem
from aidm.rules.campaign_check import check_plan_refs, master_too_dangerous
from tests.ai.campaign_fixtures import draft_from_plan
from tests.ai.fake_scripts import fake_client

PARTY = "four level-1 adventurers: fighter, rogue, cleric, wizard"


def _submit(draft: dict[str, Any]) -> FakeReply:
    return fake_tool_call("submit_result", draft)


def _broken() -> FakeReply:
    return fake_malformed("submit_result")


def _repaired(draft: dict[str, Any]) -> tuple[CampaignPlan, list[Problem]]:
    notes: list[Problem] = []
    fixed = repair_draft_refs(CampaignDraft.model_validate(draft), notes)
    plan = assemble_plan(fixed, notes)
    assert isinstance(plan, CampaignPlan)
    return plan, notes


async def test_y20_broken_json_then_a_good_plan_is_generated(tmp_path: Path) -> None:
    script = [_broken(), _broken(), _broken(), _submit(draft_from_plan())]
    client, fake = fake_client(tmp_path, script)
    result = await generate_campaign("salt", PARTY, client)
    assert result.source is CampaignSource.MODEL and result.attempts == 2
    assert len(fake.requests) == 4
    # The second attempt asks afresh: the system prompt and the request, no broken reply.
    assert len(fake.requests[3].messages) == 2


async def test_y20_one_wrong_tier_monster_is_repaired_without_a_fallback(tmp_path: Path) -> None:
    draft = draft_from_plan()
    spoke = draft["acts"][1]["region"]["spokes"][0]
    spoke["encounter_themes"] = ["lizardfolk", *spoke["encounter_themes"][1:]]
    client, fake = fake_client(tmp_path, [_submit(draft)])
    result = await generate_campaign("salt", PARTY, client)
    assert result.source is CampaignSource.MODEL and result.attempts == 1
    assert len(fake.requests) == 1
    themes = result.plan.acts[1].region.spokes[0].encounter_themes
    assert "lizardfolk" not in themes
    assert all(encounter_monsters().get(m).tier == 2 for m in themes)
    assert any(p.code == "plan_repair" and "lizardfolk" in p.message for p in result.problems)
    assert plan_problems(result.plan) == []


async def test_y20_every_attempt_broken_falls_back_to_the_sample(tmp_path: Path) -> None:
    client, fake = fake_client(tmp_path, [_broken()] * 9)
    result = await generate_campaign("salt", PARTY, client)
    assert result.source is CampaignSource.FALLBACK
    assert result.plan == load_sample_campaign()
    assert result.attempts == 3 and len(fake.requests) == 9
    assert result.problems[0].code == "llm_failure"


def test_repair_keeps_the_same_role_and_terrain_when_it_can() -> None:
    draft = draft_from_plan()
    spoke = draft["acts"][1]["region"]["spokes"][0]
    spoke["encounter_themes"] = ["lizardfolk"]
    plan, _ = _repaired(draft)
    swap = encounter_monsters().get(plan.acts[1].region.spokes[0].encounter_themes[0])
    assert swap.role == "brute" and swap.tier == 2
    assert set(swap.tags) & set(spoke["terrain_tags"])


def test_repair_is_deterministic() -> None:
    draft = draft_from_plan()
    draft["acts"][2]["region"]["boss"]["monster_id"] = "giant-rat"
    draft["acts"][0]["region"]["spokes"][1]["encounter_themes"] = ["tarrasque", "nonsense"]
    first, notes_a = _repaired(copy.deepcopy(draft))
    second, notes_b = _repaired(copy.deepcopy(draft))
    assert first == second and notes_a == notes_b


def test_a_wrong_boss_becomes_a_fitting_master_of_its_tier() -> None:
    draft = draft_from_plan()
    draft["acts"][2]["region"]["boss"]["monster_id"] = "giant-rat"
    plan, notes = _repaired(draft)
    boss = plan.acts[2].region.boss
    entry = encounter_monsters().get(boss.monster_id)
    assert entry.tier == 3 and entry.role != "minion"
    assert not master_too_dangerous(boss.monster_id, 3)
    assert boss.name == draft["acts"][2]["region"]["boss"]["name"]
    assert any("giant-rat" in p.message for p in notes)
    assert check_plan_refs(plan) == []


def test_terrain_archetype_arrival_and_home_are_repaired() -> None:
    draft = draft_from_plan()
    region = draft["acts"][0]["region"]
    region["arrival"]["encounter_themes"] = ["giant-rat"]
    region["spokes"][0]["terrain_tags"] = ["moonscape"]
    draft["npcs"][0]["archetype_id"] = "Bandit Captain"
    draft["npcs"][1]["archetype_id"] = "harbour-pilot"
    draft["npcs"][2]["home_place"] = "Nowhere Hollow"
    plan, notes = _repaired(draft)
    act1 = plan.acts[0].region
    assert act1.arrival.encounter_themes == ()
    assert act1.spokes[0].terrain_tags == act1.terrain_tags[:3]
    assert [n.archetype_id for n in plan.npcs[:2]] == ["bandit-captain", "commoner"]
    assert all(n.archetype_id in srd().monsters for n in plan.npcs)
    homes = {n.id for r in plan.all_regions() for n in r.nodes()}
    assert plan.npcs[2].home_node in homes
    assert len(notes) >= 5 and plan_problems(plan) == []


def test_a_quest_without_a_giver_is_dropped_not_the_plan() -> None:
    draft = draft_from_plan()
    title = draft["quests"][0]["title"]
    draft["quests"][0]["giver"] = "Nobody At All"
    plan, notes = _repaired(draft)
    assert title not in {q.title for q in plan.quests}
    assert len(plan.quests) == len(draft["quests"]) - 1
    assert any("Nobody At All" in p.message for p in notes)


def test_a_valid_draft_needs_no_repair() -> None:
    draft = draft_from_plan()
    _, notes = _repaired(draft)
    assert [p for p in notes if p.code == "plan_repair"] == []
