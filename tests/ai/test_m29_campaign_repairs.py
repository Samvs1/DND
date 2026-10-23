"""M29.5b generator repairs from playtest round 1 (docs/playtests/M29_round1.md, p3 save):
G30 a cast member with a boss's name was a second record (gives went to the wrong one), G34 a
plan with no trader in any region. Repair over reject: both are fixed while assembling."""

from typing import Any

from aidm.dm.campaign_draft import CampaignDraft, assemble_plan
from aidm.dm.campaign_shops import PEDDLER_ROLE, region_has_trader
from aidm.models.campaign import CampaignPlan
from aidm.models.problem import Problem
from aidm.models.state import GameState
from aidm.models.world_events import NpcIntroduced
from aidm.rules.campaign_install import install_campaign
from aidm.rules.plan_ids import boss_npc_id
from tests.ai.campaign_fixtures import draft_from_plan


def _plan(draft: dict[str, Any], notes: list[Problem] | None = None) -> CampaignPlan:
    plan = assemble_plan(CampaignDraft.model_validate(draft), notes)
    assert isinstance(plan, CampaignPlan), plan
    return plan


def _boss_twin(draft: dict[str, Any]) -> dict[str, Any]:
    """The p3 shape: the first act's boss is also written as a cast member at the gateway (in
    place of the sample's one unreferenced cast member: the cast is capped at 10)."""
    region = draft["acts"][0]["region"]
    draft["npcs"] = [n for n in draft["npcs"] if n["name"] != "Sister Wren Calloway"]
    draft["npcs"].append(
        {
            "name": region["boss"]["name"],
            "role": "Poisoner of the wells",
            "archetype_id": "cultist",
            "demeanor": "Grief-hardened, courteous to the point of menace.",
            "motive": "Wants the village to taste its own salt.",
            "home_place": region["gateway"]["name"],
            "voice_tag": "measured, wet",
            "secrets": [
                {
                    "text": "She only wants to be mourned.",
                    "reveal_kind": "attitude",
                    "band": "friendly",
                }
            ],
        }
    )
    draft["quests"][0]["against"] = region["boss"]["name"]
    return draft


def test_m29_boss_named_cast_member_is_the_boss_record() -> None:
    notes: list[Problem] = []
    plan = _plan(_boss_twin(draft_from_plan()), notes)
    region = plan.acts[0].region
    boss_id = boss_npc_id(region)
    twins = [n for n in plan.npcs if n.name == region.boss.name]
    assert [n.id for n in twins] == [boss_id]
    assert any(boss_id in p.message and "one record" in p.message for p in notes)
    events = install_campaign(GameState(campaign_id="c-test", seed=1), plan, seed=1)
    named = [
        e.npc for e in events if isinstance(e, NpcIntroduced) and e.npc.name == region.boss.name
    ]
    assert len(named) == 1, "one person, one record"
    boss = named[0]
    assert boss.id == boss_id and boss.role == "boss" and boss.node_id == region.gateway.id
    assert boss.demeanor.startswith("Grief-hardened") and len(boss.secrets) == 1


def test_m29_every_region_gets_a_trader() -> None:
    draft = draft_from_plan()
    for npc in draft["npcs"]:
        npc["role"] = "wandering storyteller"  # the p3 shape: no shopkeeper anywhere
    notes: list[Problem] = []
    plan = _plan(draft, notes)
    assert all(region_has_trader(plan, r) for r in plan.all_regions())
    peddlers = [n for n in plan.npcs if n.role == PEDDLER_ROLE]
    assert [n.home_node for n in peddlers] == [r.arrival.id for r in plan.all_regions()]
    assert sum("no trader lived here" in p.message for p in notes) == 3


def test_m29_a_plan_with_traders_is_not_changed() -> None:
    notes: list[Problem] = []
    plan = _plan(draft_from_plan(), notes)
    assert not any(n.role == PEDDLER_ROLE for n in plan.npcs)
    assert not any("no trader" in p.message for p in notes)
