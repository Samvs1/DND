"""M31.1d tougher masters (owner 2026-10-24; round 4: an 11-HP hobgoblin, a 22-HP ghoul that never
acted, a wight at 26 of its 45 SRD hit points).

- Cause: the M29.6 small-party scale compared a lone master with the boss cap x
  `boss_budget_scale`, below one CR 3 monster for four level-3 heroes, so full parties fought
  scaled masters. A party of three or more now gets a share of its hit points per tier (M31.1g,
  never below that scale); a solo or duo keeps the scale (owner rule).
- The master template (data/bg3/master_template.json): hit points towards the hit dice maximum, a
  master's turn (one-point legendary attacks) and a trait, for parties of `party_min` or more.
- A master is never weaker than the region's strongest spoke fight; the offer word follows.
SRD 5.1 numbers: wight CR 3, 700 XP, 45 HP (6d8+18, max 66); bugbear CR 1, 200 XP, 27 HP
(5d8+5, max 45); kobold CR 1/8, 25 XP, 5 HP (2d6-2, max 10).
"""

from __future__ import annotations

import random
from dataclasses import replace

from aidm.data.encounter_tables import encounter_tables
from aidm.data.feature_defs import load_feature_defs
from aidm.data.master_template import MasterTemplate, master_template
from aidm.models.abilities import Ability
from aidm.models.campaign import CampaignPlan
from aidm.models.campaign_state import EncounterOffer, OfferChoice
from aidm.models.encounter import Difficulty
from aidm.models.state import Creature, GameState
from aidm.models.world_events import PartyMoved
from aidm.rules.campaign_install import install_campaign
from aidm.rules.encounter_budget import adjusted_xp
from aidm.rules.encounter_offer import arrival_offer_events
from aidm.rules.features import save_advantage_sources
from aidm.rules.master_boost import boss_hp_scale, hit_dice_ratio, master_boost
from aidm.rules.monster_actions import monster_catalog_of
from aidm.rules.monster_keys import LEGENDARY_KEY
from aidm.rules.monster_legendary import legendary_ready
from aidm.rules.offer_answer import answer_offer
from aidm.rules.offer_spokes import OfferData, spoke_strength
from aidm.rules.plan_ids import boss_npc_id
from aidm.session.reducer import apply
from tests.session.progression_fixtures import DATA, REGS, SEED, plan
from tests.sim.sim_setup import build_party

TEMPLATE = MasterTemplate(
    party_min=3,
    hit_dice_share=1.0,
    legendary_points=1,
    trait="masters-resolve",
    floor_hp_scale_max=2.0,
)
ON = replace(DATA, master=TEMPLATE)
OFF = replace(DATA, master=MasterTemplate())
R1 = plan().acts[0].region


def _with_boss(monster: str) -> CampaignPlan:
    sample = plan()
    act = sample.acts[0]
    region = act.region.model_copy(
        update={"boss": act.region.boss.model_copy(update={"monster_id": monster})}
    )
    return sample.model_copy(
        update={"acts": (act.model_copy(update={"region": region}), *sample.acts[1:])}
    )


def _state(level: int, size: int, shaped: CampaignPlan | None = None) -> GameState:
    state = GameState(campaign_id="masters", seed=SEED)
    ids = build_party(state, level)
    for dropped in ids[size:]:
        del state.creatures[dropped]
    for event in install_campaign(state, shaped or plan(), SEED):
        apply(state, event)
    return state


def _offer(state: GameState, data: OfferData) -> EncounterOffer:
    apply(state, PartyMoved(from_node=None, to_node=R1.gateway.id, scene_index=1))
    (event,) = arrival_offer_events(state, data, None)
    apply(state, event)
    offer = getattr(event, "offer", None)
    assert isinstance(offer, EncounterOffer) and offer.boss_npc_id is not None
    return offer


def _fight_master(state: GameState, data: OfferData) -> Creature:
    _offer(state, data)
    for event in answer_offer(state, OfferChoice.FIGHT, data, random.Random(1)):
        apply(state, event)
    return next(c for c in state.creatures.values() if c.npc_id == boss_npc_id(R1))


def test_v1_m31_full_party_wight_never_meets_round_4_scaling() -> None:
    # Round 4 (r4-typed 1098): four level-3 heroes met the act-2 wight with 26 HP, 45 x 0.577
    # (boss cap 0.45 x 899 = 404 against its 700 XP). M31.1g: a party of three or more gets its
    # tier's `full_party_hp_share` of the template's hit points (a tier not listed: 1.0), never
    # below that M29.6 scale.
    state = GameState(campaign_id="masters", seed=SEED)
    build_party(state, 3)
    state.world.region_tier = 2
    assert boss_hp_scale(state, OFF, "wight") == 1.0
    assert boss_hp_scale(state, ON, "wight") == 66 / 45
    shared = replace(DATA, master=MasterTemplate(full_party_hp_share={2: 0.8}))
    assert boss_hp_scale(state, shared, "wight") == 0.8
    low = replace(DATA, master=MasterTemplate(full_party_hp_share={2: 0.3}))
    assert boss_hp_scale(state, low, "wight") == 404 / 700


def test_golden_m31_hit_dice_maximum() -> None:
    wight, bugbear = DATA.monsters.get("wight"), DATA.monsters.get("bugbear")
    assert hit_dice_ratio(wight, 1.0) * wight.hit_points == 66  # 6 x 8 + 18
    assert hit_dice_ratio(bugbear, 1.0) * bugbear.hit_points == 45  # 5 x 8 + 5
    assert hit_dice_ratio(bugbear, 0.5) * bugbear.hit_points == 36  # halfway, 27 .. 45
    assert hit_dice_ratio(bugbear, 0.0) == 1.0


def test_m31_solo_and_duo_keep_the_small_party_scale() -> None:
    # The owner's rule: a solo or duo keeps the M29.6 scale and gets no template.
    for size in (1, 2):
        boost = master_boost(_state(2, size), ON, "bugbear", R1)
        assert boost.hp_scale == boss_hp_scale(_state(2, size), OFF, "bugbear", R1)
        assert boost.legendary_points == 0 and boost.traits == ()
    assert boss_hp_scale(_state(2, 1), ON, "bugbear", R1) == 0.5


def test_m31_full_party_master_gets_the_template_in_the_fight() -> None:
    boss = _fight_master(_state(2, 4), ON)
    assert boss.max_hp == boss.hp == 45
    assert boss.resources[LEGENDARY_KEY].maximum == 1
    assert "masters-resolve" in boss.traits
    catalog = monster_catalog_of(boss, REGS.combat)
    attacks = {o.key for o in catalog.options if o.shape == "attack" and o.resource is None}
    assert attacks and {o.key for o in catalog.legendary} == attacks
    assert all(o.cost == 1 for o in catalog.legendary)


def test_m31_masters_turn_comes_after_another_creatures_turn() -> None:
    state = _state(2, 4)
    boss = _fight_master(state, ON)
    enc = state.encounter
    assert enc is not None
    owner = enc.initiative[enc.active_index].creature_id
    assert (boss.id in legendary_ready(state)) is (owner != boss.id)


def test_m31_masters_turn_recharge_and_rating() -> None:
    # A Recharge 5-6 master's turn refills on 2 of 6 faces: one point -> 1/3 attack a round.
    template = TEMPLATE.model_copy(update={"legendary_recharge": 5})
    boss = _fight_master(_state(2, 4), replace(DATA, master=template))
    assert boss.resources[LEGENDARY_KEY].turn_recharge == 5
    boost = master_boost(_state(2, 4), replace(DATA, master=template), "bugbear", R1)
    assert boost.extra_attacks == 1 / 3
    always = master_boost(_state(2, 4), ON, "bugbear", R1)
    assert always.extra_attacks == 1.0 and always.rating_factor > boost.rating_factor


def test_m31_masters_resolve_gives_advantage_against_holds() -> None:
    boss = _fight_master(_state(2, 4), ON)
    feats = REGS.combat.chars.features
    assert save_advantage_sources(boss, feats, Ability.WIS, {"paralyzed"}) == ["masters-resolve"]
    assert save_advantage_sources(boss, feats, Ability.DEX, {"fire"}) == []


def test_m31_template_off_spawns_a_plain_master() -> None:
    boss = _fight_master(_state(2, 4), OFF)
    assert boss.max_hp == 27 and LEGENDARY_KEY not in boss.resources
    assert "masters-resolve" not in boss.traits


def test_m31_master_is_never_weaker_than_the_spoke_fights() -> None:
    # A hobgoblin master (100 XP) in a region whose spokes may field 239 adjusted XP for four
    # level-2 heroes (easy cap 4 x 100 - 1 = 399 x spoke_budget_scale 0.6): its hit points and
    # rated XP rise by 239 / 100. Only the floor is on here (no hit dice share, no turn).
    floor_only = replace(DATA, master=MasterTemplate(floor_hp_scale_max=4.0))
    shaped = _with_boss("hobgoblin")
    state = _state(2, 4, shaped)
    region = shaped.acts[0].region
    assert spoke_strength(state, floor_only, region) == 239
    boost = master_boost(state, floor_only, "hobgoblin", region)
    assert round(boost.hp_scale, 2) == 2.39
    assert adjusted_xp([round(100 * boost.rating_factor)], 4, DATA.tables) == 239


def test_m31_floor_lift_is_capped() -> None:
    # A kobold master (25 XP, 2d6-2 -> max 10 of 5 HP) with the template: hit points x 2, its
    # turn doubles its round damage -> rated 100 < 239, lifted at most x floor_hp_scale_max 2.0
    # -> hit points x 4 (MAX_SPAWN_HP_SCALE), rated 25 x 8 = 200.
    shaped = _with_boss("kobold")
    boost = master_boost(_state(2, 4, shaped), ON, "kobold", shaped.acts[0].region)
    assert boost.hp_scale == 4.0
    assert round(25 * boost.rating_factor) == 200


def test_m31_offer_word_follows_the_template() -> None:
    order = list(Difficulty)
    plain = Difficulty(_offer(_state(2, 4), OFF).difficulty)
    boosted = Difficulty(_offer(_state(2, 4), ON).difficulty)
    assert order.index(boosted) > order.index(plain)


def test_m31_master_template_data() -> None:
    template = master_template()
    assert template.party_min > encounter_tables().small_party_max
    assert template.trait is None or template.trait in load_feature_defs()
