"""The hotbar's gear uses (M27.6, GOAL_ITEMS "What players see"), the improvised throw profile and
burning as condition data."""

from aidm.data.condition_defs import condition_defs
from aidm.data.item_uses import DamageUse, uses_for_item
from aidm.models.conditions import ConditionDuration
from aidm.models.damage import DamageType
from aidm.models.events import ConditionRemoved
from aidm.rules.condition_timing import combat_end_events, new_condition
from aidm.rules.gear_menu import fight_gear_lines
from aidm.rules.item_throw import throw_profile_for
from tests.unit.rules.item_fixtures import DOCKS, at, hero

COMBAT_GEAR = [
    "alchemists-fire-flask",
    "acid-vial",
    "holy-water-flask",
    ("oil-flask", 2),
    "caltrops",
    "ball-bearings-bag-of-1000",
    "torch",
    "healers-kit",
    "rope-hempen-50-feet",
]


def _rows(light: str | None = None) -> dict[str, tuple[str, str, int]]:
    lines = fight_gear_lines(hero(gear=COMBAT_GEAR), light)
    return {line.use_id: (line.cost, line.target, line.qty) for line in lines}


def test_fight_gear_lines_list_each_combat_use_with_its_cost_and_target() -> None:
    assert _rows() == {
        "alchemists-fire-throw": ("action", "creature", 1),
        "acid-vial-throw": ("action", "creature", 1),
        "holy-water-throw": ("action", "creature", 1),
        "oil-flask-throw": ("action", "zone", 2),
        "caltrops-scatter": ("action", "zone", 1),
        "ball-bearings-scatter": ("action", "zone", 1),
        "torch-light": ("bonus", "none", 1),
        "healers-kit-stabilize": ("action", "ally", 1),
    }  # the rope has no fight use: not listed


def test_a_lit_torch_can_be_thrown_and_another_light_is_not_offered() -> None:
    rows = _rows(light="torch")
    assert rows["torch-throw"] == ("action", "zone", 1)
    assert "torch-light" not in rows
    lantern = fight_gear_lines(hero(gear=["lantern-hooded"]), "lantern-hooded")
    assert lantern == []  # a lit lantern has no throw use and cannot be lit twice


def test_golden_thrown_gear_is_an_improvised_ranged_attack() -> None:
    # SRD 5.1 Improvised Weapons: no proficiency, thrown 20/60 ft; STR 16 -> +3 to hit; the
    # damage is the item's own (SRD 5.1 Acid: 2d6 acid), with no ability modifier.
    acid = uses_for_item("acid-vial")[0].effect
    assert isinstance(acid, DamageUse)
    profile = throw_profile_for(hero(), "acid", acid)
    assert (profile.attack_bonus, profile.damage, profile.damage_type) == (
        3,
        "2d6",
        DamageType.ACID,
    )
    assert (profile.ranged, profile.range_normal, profile.range_long) == (True, 20, 60)


def test_golden_burning_is_condition_data_and_ends_with_the_fight() -> None:
    # SRD 5.1 Alchemist's Fire: 1d4 fire at the start of each of its turns; an action and a
    # DC 10 Dexterity check put it out. Capped at 10 rounds (1 minute; RULES_DECISIONS M27.6).
    burning = condition_defs().get("burning")
    assert (burning.turn_start_damage, burning.turn_start_damage_type) == ("1d4", "fire")
    assert burning.end_check is not None
    assert (burning.end_check.ability, burning.end_check.dc) == ("dex", 10)
    mark = new_condition("burning", source_id="hero")
    assert (mark.duration, mark.rounds_left) == (ConditionDuration.ROUNDS, 10)
    state = at(DOCKS, hero())
    state.creatures["hero"].conditions.append(mark)
    ended = [e.name for e in combat_end_events(state) if isinstance(e, ConditionRemoved)]
    assert ended == ["burning"]
