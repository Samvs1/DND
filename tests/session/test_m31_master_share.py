"""M31.1g masters tuned to the cap (owner 2026-10-24: "Tune HP to the cap").

A full party's (3+ heroes) master spawns with `full_party_hp_share[region tier]` of its template
hit points (data/bg3/master_template.json), never below the M29.6 small-party scale computed for
the same party (what round 4 met: the wight at 26 of its 45 hit points). The spoke floor still
lifts it; solo and duo keep the M29.6 scale. SRD 5.1 numbers: wight CR 3, 700 XP, 45 HP;
gladiator CR 5, 1800 XP, 112 HP; bugbear CR 1, 200 XP, 27 HP.
"""

from __future__ import annotations

from dataclasses import replace

from aidm.data.master_template import MasterTemplate, master_template
from aidm.models.state import GameState
from aidm.rules.dm_tiers import party_levels
from aidm.rules.master_boost import boss_hp_scale, master_boost, small_party_scale
from tests.session.progression_fixtures import DATA, SEED
from tests.sim.sim_setup import build_party

LOW = replace(DATA, master=MasterTemplate(full_party_hp_share={1: 0.05, 2: 0.05, 3: 0.05}))
MASTERS = ("bugbear", "hobgoblin", "wight", "gladiator", "ogre")


def _party(level: int, size: int = 4) -> GameState:
    state = GameState(campaign_id="share", seed=SEED)
    ids = build_party(state, level)
    for dropped in ids[size:]:
        del state.creatures[dropped]
    return state


def test_m31g_full_party_master_never_below_the_old_scaled_hp() -> None:
    # The guard: whatever the share, a full party's master keeps at least the hit point scale the
    # M29.6 rule gave it (round 4 met the act-2 wight at that scale, 26 HP).
    for level in range(1, 6):
        state = _party(level)
        levels = party_levels(state)
        for tier in (1, 2, 3):
            state.world.region_tier = tier
            for monster in MASTERS:
                old = small_party_scale(levels, DATA, monster, tier)
                assert boss_hp_scale(state, LOW, monster) >= old
                assert boss_hp_scale(state, DATA, monster) >= old


def test_m31g_share_scales_hit_points_and_rating() -> None:
    # No master's turn: the offer rates the master at SRD XP x its hit point scale, so the danger
    # word follows the share.
    state = _party(3)
    state.world.region_tier = 2
    shared = replace(DATA, master=MasterTemplate(full_party_hp_share={2: 0.8}))
    boost = master_boost(state, shared, "wight", None)
    assert boost.hp_scale == 0.8 and round(boost.rating_factor, 9) == 0.8


def test_m31g_small_parties_ignore_the_share() -> None:
    for size in (1, 2):
        state = _party(3, size)
        state.world.region_tier = 2
        assert boss_hp_scale(state, LOW, "wight") == boss_hp_scale(state, DATA, "wight") == 0.5


def test_m31g_shipped_shares_cover_every_tier() -> None:
    shares = master_template().full_party_hp_share
    assert set(shares) == {1, 2, 3}
    assert all(0 < share <= 1.0 for share in shares.values())


def test_golden_m31g_tier_two_share() -> None:
    # Shipped tier 2 share (M32.1c, owner 'Full HP again'): 1.0. Four level-3 heroes meet the wight
    # (SRD 45 HP, 700 XP) with its full 45 HP (the M31.1g 0.8 gave 36), rated at 700 XP.
    # The 0.8 share stays testable through the template object.
    state = _party(3)
    state.world.region_tier = 2
    boost = master_boost(state, DATA, "wight", None)
    assert boost.hp_scale == 1.0 and round(45 * boost.hp_scale) == 45
    assert round(700 * boost.rating_factor) == 700


def test_golden_m31g_tier_three_guard() -> None:
    # Shipped tier 3 share 1.0 (M32.1c): the gladiator (SRD CR 5, 1800 XP, 112 HP) keeps its full
    # 112 HP against four level-4 and four level-5 heroes. The guard (never below the old M29.6
    # scale, 0.5 at level 4, 1799 / 1800 at level 5) is tested with an explicit 0.5 share.
    half = replace(DATA, master=MasterTemplate(full_party_hp_share={3: 0.5}))
    for level, guard in ((4, 0.5), (5, 1799 / 1800)):
        state = _party(level)
        state.world.region_tier = 3
        assert boss_hp_scale(state, DATA, "gladiator") == 1.0
        assert boss_hp_scale(state, half, "gladiator") == max(0.5, guard)


def test_v1_m32_full_party_master_spawns_at_full_srd_hit_points() -> None:
    # SRD 5.1 hit points: bugbear 27, wight 45, gladiator 112. Four heroes at the level each region
    # meets its master at: the scale is 1.0 (the spoke floor may only raise it).
    for tier, level, monster, srd in ((2, 3, "wight", 45), (3, 4, "gladiator", 112)):
        state = _party(level)
        state.world.region_tier = tier
        scale = boss_hp_scale(state, DATA, monster)
        assert scale >= 1.0 and round(srd * scale) >= srd
        assert master_boost(state, DATA, monster, None).hp_scale == 1.0
