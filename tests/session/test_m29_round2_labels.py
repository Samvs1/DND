"""M29.7d danger labels: each foe's expected damage per round against the party's hit points, and a
shooter in three-quarters cover, raise the warning card's word (round 2: the worst fights were
labelled trivial or easy). Evidence from tests/fixtures/saves/m29-r2-*."""

from __future__ import annotations

import pytest

from aidm.data.combat_data import combat_registries
from aidm.data.encounter_tables import encounter_tables
from aidm.models.campaign_events import EncounterOffered
from aidm.models.encounter import Difficulty
from aidm.models.zones import CoverLevel
from aidm.rules.encounter_threat import round_damage, round_rating, stepped
from aidm.rules.monster_catalog import monster_catalog
from aidm.rules.offer_label import LabelContext, danger_label, heroes_ac
from aidm.rules.offer_spokes import hero_hp
from tests.session.playtest_saves import logged, replay_until

R = combat_registries()
TABLES = encounter_tables()


def _round(monster: str, ac: int) -> float:
    return round_damage(
        monster_catalog(R.monsters.get(monster), R.monster_overlay, R.spells), R.spells, ac
    )


def _label(
    run: str, seq: int, foes: list[str], cover: CoverLevel = CoverLevel.NONE
) -> Difficulty | None:
    state = replay_until(run, seq)
    ctx = LabelContext(TABLES, R.monster_overlay, R.spells, hero_hp(state), heroes_ac(state), cover)
    return danger_label(None, [R.monsters.get(m) for m in foes], ctx)


def test_golden_round_damage_brown_bear() -> None:
    # SRD 5.1 Brown Bear: Multiattack = Bite (+5, 1d8+4) and Claws (+5, 2d6+4). Against AC 13
    # each hits on 8+: 0.65. Bite 0.65 x 8.5 + 0.05 x 4.5 (crit dice) = 5.75; Claws 0.65 x 11
    # + 0.05 x 7 = 7.5; one round 13.25.
    assert _round("brown-bear", 13) == pytest.approx(13.25)


def test_golden_round_damage_cult_fanatic_counts_its_spells() -> None:
    # SRD 5.1 Cult Fanatic: Multiattack 2 daggers (+4, 1d4+2) or Inflict Wounds (+3 to hit with
    # spell attacks, 3d10). Against AC 15: daggers hit on 11+ (0.5): 2 x (0.5 x 4.5 + 0.05 x 2.5)
    # = 4.75; Inflict Wounds hits on 12+ (0.45): 0.45 x 16.5 = 7.425 (the better round).
    assert _round("cult-fanatic", 15) == pytest.approx(7.425)


def test_m29_brown_bear_is_no_longer_trivial_for_the_casters() -> None:
    # p8 1009: a brown bear rated "trivial" dropped 20-HP casters; the party at the end of the
    # fixture (seq 949) has the same heroes (average 24 HP, AC 13): 13.25 / 24 = 0.55 -> hard.
    assert _label("r2-p8", 949, ["brown-bear"]) is Difficulty.HARD


def test_m29_sahuagin_is_no_longer_easy_at_level_one() -> None:
    # p8 225: a sahuagin rated "easy" against four level-1 casters (10 HP average): medium.
    offered = logged("r2-p8", 225).event
    assert isinstance(offered, EncounterOffered) and offered.offer.difficulty == "easy"
    assert _label("r2-p8", 225, ["sahuagin"]) is Difficulty.MEDIUM


def test_m29_bugbear_in_three_quarters_cover_is_no_longer_trivial() -> None:
    # p4 743: a javelin-throwing bugbear behind three-quarters cover (AC 21 to the bows) was
    # "trivial"; a shooter in three-quarters cover adds one step (data) -> easy at least.
    assert _label("r2-p4", 743, ["bugbear"]) is None
    assert _label("r2-p4", 743, ["bugbear"], CoverLevel.THREE_QUARTERS) is Difficulty.EASY
    assert _label("r2-p4", 743, ["ghoul"], CoverLevel.THREE_QUARTERS) is None  # no ranged attack


def test_m29_round_rating_and_steps() -> None:
    assert round_rating(3.9, 10, TABLES) is None
    assert round_rating(4.0, 10, TABLES) is Difficulty.MEDIUM
    assert round_rating(8.0, 10, TABLES) is Difficulty.DEADLY
    assert stepped(None, 1) is Difficulty.EASY and stepped(Difficulty.HARD, 5) is Difficulty.DEADLY
