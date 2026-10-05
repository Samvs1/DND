"""Difficulty multipliers: HP scaling at spawn and damage scaling for hostile monsters (M6.5)."""

from aidm.models.damage import DamagePacket, DamageType
from aidm.models.difficulty import Difficulty
from aidm.models.state import Creature, CreatureKind, GameState
from aidm.rules.difficulty import scale_damage, scale_spawn


def _goblin() -> Creature:
    return Creature(id="g", name="Goblin", kind=CreatureKind.MONSTER, max_hp=7, hp=7, ac=15)


def test_scale_spawn_rounds_half_up_and_keeps_one_at_least() -> None:
    assert scale_spawn(_goblin(), 1.0).max_hp == 7
    assert scale_spawn(_goblin(), 1.5).max_hp == 11  # 10.5 rounds up
    assert scale_spawn(_goblin(), 0.25).hp == 2  # 1.75 rounds to 2
    assert scale_spawn(_goblin().model_copy(update={"max_hp": 1, "hp": 1}), 0.25).max_hp == 1


def test_no_encounter_or_default_difficulty_leaves_damage_alone() -> None:
    state = GameState(campaign_id="d", seed=1, difficulty=Difficulty(monster_damage=2.0))
    state.creatures["g"] = _goblin()
    packet = DamagePacket(amount=5, damage_type=DamageType.FIRE)
    assert scale_damage(state, "g", [packet]) == [packet]
    assert scale_damage(GameState(campaign_id="d", seed=1), "g", [packet]) == [packet]
