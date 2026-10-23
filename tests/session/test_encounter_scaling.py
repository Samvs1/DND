"""M29.6 tuning: world-pulled fights scale with the party's size and level (encounter_budget.json).

- A spoke's budget is its rating cap x `spoke_budget_scale[tier]`.
- A spoke whose theme monsters are all too costly for the party gets terrain-matched stand-ins
  within the budget (`spoke_stand_ins`), not the cheapest theme monster over budget.
- The boss's company is capped per hero (`boss_company_max_per_pc`) and by the boss rating cap;
  a boss too strong alone for the party spawns with scaled hit points (`boss_hp_scale_floor`).
XP values in the goldens are the SRD 5.1 stat blocks' (CR 1/8 = 25, CR 1/4 = 50, CR 1/2 = 100,
CR 1 = 200, CR 2 = 450, CR 4 = 1100, CR 5 = 1800); thresholds are encounter_budget.json's.
"""

from __future__ import annotations

import random
from dataclasses import replace

from aidm.models.campaign_state import EncounterOffer, OfferChoice
from aidm.models.encounter import Difficulty
from aidm.models.state import GameState
from aidm.models.world_events import PartyMoved
from aidm.rules.campaign_install import install_campaign
from aidm.rules.dm_tiers import party_levels
from aidm.rules.encounter_budget import adjusted_xp, rating_cap_xp
from aidm.rules.encounter_offer import OfferData, arrival_offer_events, boss_hp_scale
from aidm.rules.offer_answer import answer_offer
from aidm.rules.plan_ids import boss_npc_id
from aidm.session.reducer import apply
from tests.session.progression_fixtures import DATA, SEED, plan
from tests.sim.sim_setup import build_party

R1, R2, R3 = (act.region for act in plan().acts)


def _state(level: int, size: int) -> GameState:
    """The sample campaign for the first `size` heroes of the sim party (fighter first)."""
    state = GameState(campaign_id="scale", seed=SEED)
    ids = build_party(state, level)
    for dropped in ids[size:]:
        del state.creatures[dropped]
    for event in install_campaign(state, plan(), SEED):
        apply(state, event)
    return state


def _offer_at(level: int, size: int, node: str, data: OfferData = DATA) -> EncounterOffer:
    state = _state(level, size)
    apply(state, PartyMoved(from_node=None, to_node=node, scene_index=1))
    events = arrival_offer_events(state, data, None)
    assert len(events) == 1
    offer = getattr(events[0], "offer", None)
    assert isinstance(offer, EncounterOffer)
    return offer


def _xps(offer: EncounterOffer) -> list[int]:
    return [DATA.monsters.get(m).xp for m in offer.monster_ids]


def _spoke(region_index: int, monster: str) -> str:
    region = (R1, R2, R3)[region_index]
    return next(s.id for s in region.spokes if monster in s.encounter_themes)


def test_golden_solo_level_one_gets_a_smaller_spoke_fight_than_a_classic_four() -> None:
    # Level 1 easy cap x the tier-1 budget scale 0.6: four heroes (4 x 50 - 1) x 0.6 = 119
    # adjusted XP; one hero (50 - 1) x 0.6 = 29, which not even one CR 1/8 fits (25 x 1.5 = 37),
    # so the cheapest theme monster comes alone.
    node = _spoke(0, "crocodile")
    solo, four = _offer_at(1, 1, node), _offer_at(1, 4, node)
    assert sum(_xps(solo)) < sum(_xps(four))
    assert _xps(solo) == [25]
    assert adjusted_xp(_xps(four), 4, DATA.tables) <= 119


def test_golden_duo_gets_stand_ins_within_budget_at_an_act_two_spoke() -> None:
    # Duo level 3: easy cap 2 x 150 - 1 = 299, x the tier-2 budget scale 0.5 = 149. A CR 2
    # theme monster alone is 450 x 1.5 (small party: one step up) = 675, over budget -> one
    # CR 1/4 stand-in (50 x 1.5 = 75; a CR 1/2 is 150, two CR 1/4 are 100 x 2.0 = 200).
    node = _spoke(1, "bandit-captain")
    offer = _offer_at(3, 2, node)
    assert len(offer.monster_ids) == 1
    assert DATA.monsters.get(offer.monster_ids[0]).xp == 50
    assert adjusted_xp(_xps(offer), 2, DATA.tables) <= 149


def test_stand_ins_share_a_terrain_with_the_themes() -> None:
    node = _spoke(2, "earth-elemental")
    offer = _offer_at(4, 1, node)
    tags = {t for m in ("earth-elemental", "xorn") for t in DATA.encounter.get(m).tags}
    for monster in offer.monster_ids:
        assert tags & set(DATA.encounter.get(monster).tags), monster


def test_without_stand_ins_the_cheapest_theme_monster_still_comes() -> None:
    tables = DATA.tables.model_copy(update={"spoke_stand_ins": False})
    offer = _offer_at(3, 2, _spoke(1, "bandit-captain"), replace(DATA, tables=tables))
    assert len(offer.monster_ids) == 1
    assert offer.monster_ids[0] in ("bandit-captain", "berserker")


def test_classic_four_keeps_its_theme_monster_when_it_fits() -> None:
    # Four level-4 heroes at an act-2 spoke: (4 x 250 - 1) x 0.5 = 499 >= one CR 2 (450).
    offer = _offer_at(4, 4, _spoke(1, "ankheg"))
    assert len(offer.monster_ids) == 1
    assert set(offer.monster_ids) <= {"ankheg", "ogre"}


def test_golden_budget_scale_shrinks_an_act_three_spoke() -> None:
    # Four level-5 heroes: the full easy cap 4 x 500 - 1 = 1999 takes a CR 5 theme (1800); the
    # tier-3 scale 0.5 leaves 999, so a CR 3 stand-in (700) comes instead (CR 4 is 1100).
    node = _spoke(2, "earth-elemental")
    whole = DATA.tables.model_copy(update={"spoke_budget_scale": {}})
    assert set(_offer_at(5, 4, node, replace(DATA, tables=whole)).monster_ids) <= {
        "earth-elemental",
        "xorn",
    }
    assert _xps(_offer_at(5, 4, node)) == [700]


def test_master_company_scales_with_party_size() -> None:
    gateway = R1.gateway.id
    solo, four = _offer_at(2, 1, gateway), _offer_at(2, 4, gateway)
    assert solo.boss_npc_id and four.boss_npc_id
    per_pc = DATA.tables.boss_company_max_per_pc
    assert per_pc is not None
    assert len(solo.monster_ids) <= per_pc * 1 < len(four.monster_ids) <= per_pc * 4
    state = _state(2, 4)
    cap = rating_cap_xp(party_levels(state), Difficulty(DATA.tables.boss_rating_cap), DATA.tables)
    boss_xp = DATA.monsters.get(R1.boss.monster_id).xp
    assert adjusted_xp([boss_xp, *_xps(four)], 4, DATA.tables) <= cap


def test_golden_lone_boss_hit_points_scale_for_a_solo_hero() -> None:
    # Solo level 2, medium cap 150 - 1 = 149; the bugbear (SRD: CR 1, 200 XP, 27 hit points)
    # alone is 200 x 1.5 = 300 -> scale max(0.5, 149 / 300) = 0.5 -> 27 x 0.5 = 13.5 -> 14 HP.
    # Four level-2 heroes: 200 <= 599, no scaling.
    monster = R1.boss.monster_id
    assert boss_hp_scale(_state(2, 1), DATA, monster) == 0.5
    assert boss_hp_scale(_state(2, 4), DATA, monster) == 1.0
    state = _state(2, 1)
    apply(state, PartyMoved(from_node=None, to_node=R1.gateway.id, scene_index=1))
    for event in arrival_offer_events(state, DATA, None):
        apply(state, event)
    for event in answer_offer(state, OfferChoice.FIGHT, DATA, random.Random(1)):
        apply(state, event)
    boss = next(c for c in state.creatures.values() if c.npc_id == boss_npc_id(R1))
    assert boss.max_hp == boss.hp == 14


def test_without_a_floor_the_boss_keeps_its_hit_points() -> None:
    tables = DATA.tables.model_copy(update={"boss_hp_scale_floor": None})
    assert boss_hp_scale(_state(2, 1), replace(DATA, tables=tables), R1.boss.monster_id) == 1.0
