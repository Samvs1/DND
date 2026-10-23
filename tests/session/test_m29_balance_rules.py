"""M29.6b balance from the live playtests (docs/playtests/M29_round1.md "Balance" notes).

- Gifts: one candle given five times made a master an ally (p3 431-449): a repeat gift and a
  minor gift past `gift_deeds_per_npc` earn no deed.
- Act 1 asked a DC 20 Athletics check of level-1 heroes 6 times (p2 155-733): a requested check
  and a new lock are capped at the region tier's `check_dc_tier_cap`.
- Shops: region 1's only shop sold no weapon or armour, healing cost 50 gp (p2): a general store
  has a weapon, an armour and healing for 25 gp or less; a region without such a trader gets a
  peddler.
- Dragons: a wyrmling was "trivial" and a young black dragon "medium" (p3 1136, 1533): a
  breath weapon counts in the rating, spokes do not field one above their cap, and such a master
  is refused by the plan check.
XP values are the SRD 5.1 stat blocks' (green dragon wyrmling CR 2 = 450 XP, Poison Breath 6d6 =
21 average; young black dragon CR 7 = 2900 XP, Acid Breath 11d8 = 49.5 average).
"""

from __future__ import annotations

import random

from aidm.data.dm_tiers import dm_tiers
from aidm.data.item_catalogue import item_catalogue
from aidm.data.shop_defs import shop_table
from aidm.dm.campaign_shops import PEDDLER_ROLE, region_has_trader, with_traders
from aidm.models.campaign import CampaignPlan
from aidm.models.campaign_state import EncounterOffer
from aidm.models.encounter import Difficulty
from aidm.models.events import CheckResolved, InventoryChanged
from aidm.models.problem import Problem
from aidm.models.state import GameState
from aidm.models.world_events import AttitudeChanged, PartyMoved
from aidm.rules.campaign_check import check_plan_refs
from aidm.rules.campaign_install import install_campaign
from aidm.rules.encounter_budget import rate_encounter
from aidm.rules.encounter_danger import area_damage, area_rating
from aidm.rules.encounter_offer import arrival_offer_events
from aidm.rules.shop import shop_stock
from aidm.rules.social_deeds import gift_events
from aidm.session.reducer import apply
from tests.ai.tool_fixtures import party_state, run_tool
from tests.session.progression_fixtures import DATA, SEED, apply_all, campaign_state, plan
from tests.sim.sim_setup import build_party

TIERS = dm_tiers()
WYRMLING = "green-dragon-wyrmling"
YOUNG_BLACK = "young-black-dragon"


def _carry(state: GameState, item: str) -> None:
    apply_all(state, [InventoryChanged(creature_id="fighter", item=item, delta=1, qty=1)])


def _gift(state: GameState, item: str) -> list[AttitudeChanged]:
    _carry(state, item)
    events = gift_events(state, "fighter", "odalys-prend", item, TIERS)
    apply_all(state, events)
    assert isinstance(events[0], InventoryChanged) and events[0].delta == -1
    return [e for e in events if isinstance(e, AttitudeChanged)]


def test_m29_repeat_gift_earns_no_deed() -> None:
    _, state, _ = campaign_state()
    (first,) = _gift(state, "candle")
    assert first.deeds == TIERS.deed_points["minor"] and first.gift == "candle"
    for _ in range(4):  # p3: the same candle four more times
        assert _gift(state, "candle") == []
    npc = state.world.npcs["odalys-prend"]
    assert npc.deeds == TIERS.deed_points["minor"] and npc.gifts == ["candle"]


def test_m29_gifts_past_the_limit_earn_no_deed() -> None:
    _, state, _ = campaign_state()
    assert TIERS.gift_deeds_per_npc == 2
    paid = [_gift(state, item) for item in ("candle", "dagger", "torch")]
    assert [len(p) for p in paid] == [1, 1, 0]
    assert state.world.npcs["odalys-prend"].deeds == 2 * TIERS.deed_points["minor"]


def _check_dc(region_tier: int, tier: str) -> CheckResolved:
    state = party_state()
    state.world.region_tier = region_tier
    result = run_tool(
        state, "request_check", actor="fighter", ability_or_skill="athletics", dc_tier=tier
    )
    (event,) = result.events
    assert isinstance(event, CheckResolved)
    return event


def test_m29_act_one_check_never_asks_dc_twenty() -> None:
    # p2 155-733: "hard" (DC 20, SRD Typical DCs) is capped at medium (DC 15) in act 1 only.
    assert _check_dc(1, "hard").result.dc == 15
    assert _check_dc(1, "hard").result.tier == "medium"
    assert _check_dc(1, "easy").result.dc == 10
    assert _check_dc(2, "hard").result.dc == 20
    assert _check_dc(2, "very_hard").result.dc == 20
    assert _check_dc(3, "very_hard").result.dc == 25


def test_m29_act_one_lock_is_at_most_medium() -> None:
    state = party_state()
    result = run_tool(state, "introduce_feature", kind="cache", name="Iron chest", lock_tier="hard")
    assert result.ok and "(locked, medium)" in result.summary


def test_m29_general_store_has_weapon_armour_and_cheap_healing() -> None:
    catalogue, table = item_catalogue(), shop_table()
    for seed in range(20):
        stock = shop_stock(catalogue, table, "general", 1, random.Random(seed))
        kinds = {catalogue.get(e.item).category.value for e in stock}
        assert {"weapon", "armor", "potion"} <= kinds
        cheap = [e for e in stock if catalogue.get(e.item).heal and e.price_gp <= 25]
        assert cheap, stock
    # SRD price kept: a Potion of Healing still costs 50 gp.
    assert catalogue.get("potion-of-healing").value_gp == 50


def test_m29_region_without_a_full_trader_gets_a_peddler() -> None:
    data = plan().model_dump()
    for npc in data["npcs"]:
        if npc["role"] == "quartermaster and trader":
            npc["role"] = "quartermaster"
    shaped = CampaignPlan.model_validate(data)
    last = shaped.acts[2].region
    assert not region_has_trader(shaped, last)  # a provisioner sells no weapon or armour
    notes: list[Problem] = []
    fixed = with_traders(shaped, notes)
    assert region_has_trader(fixed, last) and len(notes) == 1
    assert any(n.role == PEDDLER_ROLE for n in fixed.npcs)
    assert all(region_has_trader(plan(), r) for r in plan().all_regions())


def test_m29_breath_weapon_counts_in_the_rating() -> None:
    wyrmling, young = DATA.monsters.get(WYRMLING), DATA.monsters.get(YOUNG_BLACK)
    assert area_damage(wyrmling) == 21.0 and area_damage(young) == 49.5
    # Four level-4 heroes: easy threshold 4 x 125 = 500 > 450 XP, so the XP rating is trivial...
    assert rate_encounter([wyrmling.xp], [4, 4, 4, 4], DATA.tables) is None
    # ...but one breath is 21 / 30 = 0.7 of a hero's hit points: hard (share 0.6).
    assert area_rating(wyrmling, 30, DATA.tables) is Difficulty.HARD
    assert area_rating(young, 38, DATA.tables) is Difficulty.DEADLY
    assert area_rating(DATA.monsters.get("bandit"), 10, DATA.tables) is None


def _plan_with(spoke_theme: str, boss: str) -> CampaignPlan:
    data = plan().model_dump()
    region = data["acts"][2]["region"]
    region["spokes"][0]["encounter_themes"] = [spoke_theme]
    region["boss"]["monster_id"] = boss
    return CampaignPlan.model_validate(data)


def _offer(shaped: CampaignPlan, node: str, level: int) -> EncounterOffer:
    state = GameState(campaign_id="danger", seed=SEED)
    build_party(state, level)
    for event in install_campaign(state, shaped, SEED):
        apply(state, event)
    state.world.region_tier = 3
    apply(state, PartyMoved(from_node=None, to_node=node, scene_index=1))
    (event,) = arrival_offer_events(state, DATA, None)
    offer = getattr(event, "offer", None)
    assert isinstance(offer, EncounterOffer)
    return offer


def test_m29_spoke_never_fields_a_breath_over_its_cap() -> None:
    shaped = _plan_with(WYRMLING, YOUNG_BLACK)
    offer = _offer(shaped, shaped.acts[2].region.spokes[0].id, 4)
    assert WYRMLING not in offer.monster_ids and offer.monster_ids


def test_m29_breathing_master_is_told_deadly_and_comes_alone() -> None:
    shaped = _plan_with("bandit", YOUNG_BLACK)
    offer = _offer(shaped, shaped.acts[2].region.gateway.id, 5)
    assert offer.boss_npc_id is not None
    assert offer.difficulty == "deadly" and offer.monster_ids == ()
    assert "boss_area" in [p.code for p in check_plan_refs(shaped)]
    assert check_plan_refs(plan()) == []  # the sample's masters (no breath) stay
