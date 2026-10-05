"""M5.5 social: structured reveal conditions, deeds from events, the public NPC projection."""

import json

import pytest

from aidm.data.dm_tiers import dm_tiers
from aidm.dm.campaign_draft import CampaignDraft, assemble_plan
from aidm.models.campaign import CampaignPlan, RevealCondition, RevealKind
from aidm.models.encounter import EncounterStatus
from aidm.models.events import InventoryChanged
from aidm.models.state import GameState
from aidm.models.world import Fact, NpcSecret, Quest, QuestState, WorldNpc
from aidm.models.world_events import AttitudeChanged, FactRecorded, NpcIntroduced
from aidm.rules.secrets import party_has_item, reveal_refusal
from aidm.rules.social import ALLY_BAR, SOCIAL_CAP, attitude_score, public_npc_view
from aidm.rules.social_deeds import (
    GiftRefused,
    combat_help_deed_events,
    gift_events,
    quest_deed_events,
)
from tests.ai.campaign_fixtures import draft_from_plan
from tests.ai.tool_fixtures import run_tool
from tests.session.progression_fixtures import apply_all, campaign_state

TIERS = dm_tiers()


def _give(state: GameState, item: str) -> None:
    apply_all(state, [InventoryChanged(creature_id="fighter", item=item, delta=1, qty=1)])


def test_attitude_condition_needs_the_band() -> None:
    _, state, _ = campaign_state()
    refused = run_tool(state, "reveal_secret", npc="odalys-prend", secret_id="odalys-debt")
    assert refused.error is not None and "trust" in refused.error
    odalys = state.world.npcs["odalys-prend"]
    apply_all(state, [AttitudeChanged(npc_id=odalys.id, social=0, deeds=20)])
    assert run_tool(state, "reveal_secret", npc="odalys-prend", secret_id="odalys-debt").ok


def test_quest_condition_and_quest_deed() -> None:
    _, state, _ = campaign_state()
    assert run_tool(state, "reveal_secret", npc="tobin-marrow", secret_id="tobin-lights").error
    done = run_tool(state, "update_quest", quest_id="missing-ledger", state="completed")
    assert done.ok
    apply_all(state, list(done.events))
    assert state.world.npcs["tobin-marrow"].deeds == TIERS.deed_points["moderate"]
    assert run_tool(state, "reveal_secret", npc="tobin-marrow", secret_id="tobin-lights").ok


def test_item_shown_condition_needs_the_item_carried() -> None:
    _, state, _ = campaign_state()
    wren = state.world.npcs["wren-calloway"]
    assert reveal_refusal(state, wren, "wren-hum") is not None
    _give(state, "harbour-ledger")
    assert party_has_item(state, "Harbour ledger")
    assert reveal_refusal(state, wren, "wren-hum") is None


def test_fact_condition_and_hostile_refusal() -> None:
    _, state, _ = campaign_state()
    cond = RevealCondition(kind=RevealKind.FACT_KNOWN, fact_tag="smugglers")
    npc = WorldNpc(
        id="npc-ivo",
        name="Ivo",
        archetype_id="commoner",
        node_id=state.world.current_node,
        secrets=[NpcSecret(id="s1", text="The crates hold powder.", reveal=cond)],
    )
    apply_all(state, [NpcIntroduced(npc=npc)])
    assert reveal_refusal(state, state.world.npcs["npc-ivo"], "s1") is not None
    fact = Fact(id="fact-1", text="The smugglers use the quay.", tags=("smugglers",))
    apply_all(state, [FactRecorded(fact=fact)])
    assert reveal_refusal(state, state.world.npcs["npc-ivo"], "s1") is None
    apply_all(state, [AttitudeChanged(npc_id="npc-ivo", social=0, deeds=0, hostile=True)])
    refusal = reveal_refusal(state, state.world.npcs["npc-ivo"], "s1")
    assert refusal is not None and "hostile" in refusal


def test_quest_against_and_failed_quests_are_deeds() -> None:
    _, state, _ = campaign_state()
    quest = Quest(
        id="q-x",
        title="Sink the boat",
        state=QuestState.COMPLETED,
        giver_npc_id="odalys-prend",
        against_npc_id="tobin-marrow",
    )
    events = quest_deed_events(state, quest, TIERS)
    deltas = {e.npc_id: e.deeds for e in events if isinstance(e, AttitudeChanged)}
    assert deltas == {"odalys-prend": 20, "tobin-marrow": -20}
    failed = quest.model_copy(update={"state": QuestState.FAILED})
    events = quest_deed_events(state, failed, TIERS)
    assert [(e.npc_id, e.deeds) for e in events if isinstance(e, AttitudeChanged)] == [
        ("odalys-prend", -10)
    ]


def test_combat_help_is_a_deed_for_bystanders_only() -> None:
    _, state, _ = campaign_state()
    events = combat_help_deed_events(state, EncounterStatus.VICTORY, TIERS)
    helped = {e.npc_id for e in events if isinstance(e, AttitudeChanged)}
    present = {n.id for n in state.world.npcs.values() if n.node_id == state.world.current_node}
    assert helped == present and helped
    assert combat_help_deed_events(state, EncounterStatus.FLED, TIERS) == []


def test_gifts_plot_items_count_more() -> None:
    _, state, _ = campaign_state()
    with pytest.raises(GiftRefused):
        gift_events(state, "fighter", "odalys-prend", "Harbour ledger", TIERS)
    _give(state, "Harbour ledger")
    _give(state, "dagger")
    plot = gift_events(state, "fighter", "odalys-prend", "Harbour ledger", TIERS)
    assert isinstance(plot[0], InventoryChanged) and plot[0].delta == -1
    assert isinstance(plot[1], AttitudeChanged) and plot[1].deeds == 35
    small = gift_events(state, "fighter", "odalys-prend", "dagger", TIERS)
    assert isinstance(small[1], AttitudeChanged) and small[1].deeds == 10
    with pytest.raises(GiftRefused):
        gift_events(state, "fighter", "wren-calloway", "dagger", TIERS)  # not here


def test_deeds_alone_cross_the_ally_bar_for_a_campaign_npc() -> None:
    _, state, _ = campaign_state()
    odalys = state.world.npcs["odalys-prend"]
    apply_all(state, [AttitudeChanged(npc_id=odalys.id, social=40, deeds=0)])
    assert attitude_score(state.world.npcs[odalys.id]) == SOCIAL_CAP < ALLY_BAR  # talk maxed
    apply_all(state, [AttitudeChanged(npc_id=odalys.id, social=40, deeds=10)])
    assert attitude_score(state.world.npcs[odalys.id]) >= ALLY_BAR


def test_public_npc_view_hides_motive_and_unrevealed_secrets() -> None:
    _, state, _ = campaign_state()
    odalys = state.world.npcs["odalys-prend"]
    view = public_npc_view(odalys)
    dumped = view.model_dump_json()
    assert odalys.motive and odalys.motive not in dumped
    assert odalys.secrets[0].text not in dumped
    assert "motive" not in json.loads(dumped) and "secrets" not in json.loads(dumped)
    assert view.attitude.value == "indifferent" and view.revealed_secrets == ()
    apply_all(state, [AttitudeChanged(npc_id=odalys.id, social=0, deeds=20)])
    revealed = run_tool(state, "reveal_secret", npc="odalys-prend", secret_id="odalys-debt")
    apply_all(state, list(revealed.events))
    after = public_npc_view(state.world.npcs[odalys.id])
    assert after.revealed_secrets == (odalys.secrets[0].text,)
    assert after.attitude.value == "friendly"


def test_drafts_support_fact_conditions_and_quests_against() -> None:
    draft = draft_from_plan()
    draft["npcs"][0]["secrets"] = [
        {"text": "She paid the wreckers.", "reveal_kind": "fact_known", "fact_tag": "Wreckers"}
    ]
    draft["quests"][0]["against"] = draft["npcs"][1]["name"]
    plan = assemble_plan(CampaignDraft.model_validate(draft))
    assert isinstance(plan, CampaignPlan)
    assert plan.npcs[0].secrets[0].reveal.fact_tag == "wreckers"
    assert plan.quests[0].against_npc_id == plan.npcs[1].id
