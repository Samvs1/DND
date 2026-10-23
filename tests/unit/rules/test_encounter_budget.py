"""Encounter XP budget goldens and the seeded monster picker."""

from __future__ import annotations

import random

import pytest

from aidm.data.encounter_tables import encounter_tables
from aidm.data.srd import srd
from aidm.models.encounter import Difficulty
from aidm.rules.encounter_budget import (
    adjusted_xp,
    check_encounter_budget,
    group_multiplier,
    party_budget,
    party_thresholds,
    pick_monsters,
    rate_encounter,
    rating_cap_xp,
)

T = encounter_tables()


def test_golden_monster_xp_from_srd() -> None:
    # SRD 5.1 Experience Points by Challenge Rating: CR 1/4 = 50, CR 1/2 = 100, CR 1 = 200,
    # CR 2 = 450.
    m = srd().monsters
    assert (m.get("goblin").cr, m.get("goblin").xp) == (0.25, 50)
    assert (m.get("orc").cr, m.get("orc").xp) == (0.5, 100)
    assert (m.get("bugbear").cr, m.get("bugbear").xp) == (1, 200)
    assert (m.get("ogre").cr, m.get("ogre").xp) == (2, 450)


def test_golden_party_budgets() -> None:
    # Standard 5e thresholds: level 1 = 25/50/75/100, level 3 = 75/150/225/400,
    # level 5 = 250/500/750/1100 (easy/medium/hard/deadly).
    assert party_budget([1, 1, 1, 1], Difficulty.MEDIUM, T) == 200
    assert party_thresholds([3, 3, 3, 3], T) == {
        Difficulty.EASY: 300,
        Difficulty.MEDIUM: 600,
        Difficulty.HARD: 900,
        Difficulty.DEADLY: 1600,
    }
    assert party_budget([5, 4], Difficulty.DEADLY, T) == 1600
    with pytest.raises(ValueError, match="level 13"):
        party_budget([13], Difficulty.EASY, T)
    with pytest.raises(ValueError, match="at least one"):
        party_budget([], Difficulty.EASY, T)


def test_golden_group_multiplier() -> None:
    assert [group_multiplier(n, 4, T) for n in (1, 2, 3, 6, 7, 10, 11, 15)] == [
        1.0,
        1.5,
        2.0,
        2.0,
        2.5,
        2.5,
        3.0,
        4.0,
    ]
    assert group_multiplier(1, 2, T) == 1.5  # small party: one step up
    assert group_multiplier(15, 1, T) == 5.0
    assert group_multiplier(1, 6, T) == 0.5  # large party: one step down
    assert group_multiplier(3, 6, T) == 1.5


def test_golden_adjusted_xp_and_rating() -> None:
    goblins = [50, 50, 50, 50]
    assert adjusted_xp(goblins, 4, T) == 400  # 200 XP x2 for 3-6 monsters
    assert adjusted_xp([50], 4, T) == 50
    assert rate_encounter([50], [1, 1, 1, 1], T) is None  # below easy (100)
    assert rate_encounter([50, 50], [1, 1, 1, 1], T) is Difficulty.EASY  # 150
    assert rate_encounter([100, 50], [1, 1, 1, 1], T) is Difficulty.MEDIUM  # 225
    assert rate_encounter(goblins, [1, 1, 1, 1], T) is Difficulty.DEADLY  # 400


def test_budget_check_rejects_over_deadly() -> None:
    over = check_encounter_budget([450], [1, 1, 1, 1], T)
    assert (over.adjusted_xp, over.deadly_budget, over.allowed) == (450, 400, False)
    fine = check_encounter_budget([50, 50, 50], [1, 1, 1, 1], T)
    assert (fine.adjusted_xp, fine.allowed, fine.difficulty) == (300, True, Difficulty.HARD)


def test_pick_monsters_stays_within_budget_and_is_seeded() -> None:
    candidates = {"goblin": 50, "orc": 100, "bugbear": 200, "ogre": 450, "rat": 0}
    picks = [pick_monsters(random.Random(s), 200, candidates, 4, T) for s in range(30)]
    for picked in picks:
        assert picked
        assert "rat" not in picked and "ogre" not in picked
        xps = [candidates[p] for p in picked]
        assert adjusted_xp(xps, 4, T) <= 200
    assert len({tuple(p) for p in picks}) > 1
    again = pick_monsters(random.Random(3), 200, candidates, 4, T)
    assert again == pick_monsters(random.Random(3), 200, candidates, 4, T)
    assert pick_monsters(random.Random(1), 10, candidates, 4, T) == []


def test_pick_monsters_respects_max_monsters() -> None:
    picked = pick_monsters(random.Random(5), 100_000, {"rat": 10}, 4, T)
    assert len(picked) == T.max_monsters


def test_golden_rating_caps() -> None:
    # Three level-1 PCs: thresholds 75/150/225/300. "At most easy" = below medium (149),
    # "at most hard" = below deadly (299), "at most deadly" = the deadly threshold itself.
    levels = [1, 1, 1]
    assert rating_cap_xp(levels, Difficulty.EASY, T) == 149
    assert rating_cap_xp(levels, Difficulty.HARD, T) == 299
    assert rating_cap_xp(levels, Difficulty.DEADLY, T) == 300
    # Three giant rats (25 XP, x2 for three monsters) = 150: rated medium, over the easy cap.
    assert rate_encounter([25, 25, 25], levels, T) is Difficulty.MEDIUM
    assert rate_encounter([25, 25], levels, T) is Difficulty.EASY


def test_world_encounter_caps_are_data() -> None:
    # RULES_DECISIONS M9.2, retuned in M29.6 (DECISIONS): every spoke easy, bosses medium with at
    # most one companion per hero, stand-ins for over-budget spokes, a lone boss too strong for
    # a small party scaled down to at most half its hit points.
    assert T.spoke_rating_cap == {1: "easy", 2: "easy", 3: "easy"}
    assert T.spoke_budget_scale == {1: 0.6, 2: 0.5, 3: 0.5}
    assert T.spoke_max_monsters_per_pc == {1: 1, 2: 2, 3: 2}
    assert T.boss_rating_cap == "medium"
    assert T.boss_company_max_per_pc == 1
    assert T.spoke_stand_ins is True
    assert T.boss_hp_scale_floor == 0.5
