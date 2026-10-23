"""M29.2: play styles, party shapes and the campaign bots' spell and potion choices (pure)."""

import random

import pytest

from aidm.data.character_data import character_registries
from aidm.models.creation import CreationChoices
from aidm.rules.creation import validate_creation
from scripts.sim.client import Msg
from scripts.sim.combat import Plan
from scripts.sim.shapes import SHAPES, smart_choices
from scripts.sim.spells import castable, prefer, spell_command
from scripts.sim.styles import STYLES, style_of

GOAL_STYLES = {"aggressive", "cautious", "talker", "cunning", "spender", "hoarder"}


def test_m29_every_goal_style_and_shape_exists() -> None:
    assert GOAL_STYLES | {"balanced"} == set(STYLES)
    assert set(SHAPES) == {"classic", "martial", "casters", "solo", "duo"}
    assert [len(SHAPES[s]) for s in ("classic", "solo", "duo")] == [4, 1, 2]
    assert style_of("talker").peace and style_of("talker").offer == "parley"
    assert style_of("cunning").offer == "surprise"
    assert style_of("hoarder").shop == "none" and style_of("spender").shop == "spender"
    with pytest.raises(ValueError):
        style_of("berserker")


def test_m29_shape_heroes_are_legal_for_every_seed() -> None:
    regs = character_registries()
    classes = {cls for shape in SHAPES.values() for _, cls in shape}
    for cls in sorted(classes):
        for seed in range(12):
            made = CreationChoices.model_validate(smart_choices(cls, "Hero", random.Random(seed)))
            assert validate_creation(made, regs) == [], (cls, seed)
    cleric = smart_choices("cleric", "Hero", random.Random(1))
    assert cleric["prepared"] == ["healing-word", "cure-wounds", "guiding-bolt"]
    assert max(cleric["base_scores"], key=cleric["base_scores"].get) == "wis"


def _sheet(slots: int, potion: bool = False) -> Msg:
    spells = [
        {"index": "guiding-bolt", "level": 1, "prepared": True},
        {"index": "healing-word", "level": 1, "prepared": True},
    ]
    group = {"level": 1, "slots": [{"kind": "standard", "current": slots, "maximum": 2}]}
    inventory = [{"item": "potion-of-healing", "qty": 1}] if potion else []
    return {"spellcasting": {"levels": [{**group, "spells": spells}]}, "inventory": inventory}


def _combat(my_hp: int) -> Msg:
    tokens = [
        {"creature_id": "pc-1", "side": "party", "zone_id": "a", "hp": my_hp, "max_hp": 20},
        {"creature_id": "pc-2", "side": "party", "zone_id": "a", "hp": 9, "max_hp": 10},
        {"creature_id": "m-1", "side": "foes", "zone_id": "b", "hp": 7, "max_hp": 7},
    ]
    eco = {"action": True, "bonus_action": True, "movement_left": 30}
    return {"tokens": tokens, "economy": eco}


def _party(ally_dying: bool) -> list[Msg]:
    ally = {"id": "pc-2", "hp": 0 if ally_dying else 9, "max_hp": 10, "dead": False}
    return [{"id": "pc-1", "hp": 20, "max_hp": 20, "dead": False}, {**ally, "dying": ally_dying}]


def test_m29_campaign_bot_spells_and_potions() -> None:
    plan = Plan(role="caster", hero_id="pc-1", rng=random.Random(1), smart=True)
    foe = {"creature_id": "m-1", "zone_id": "b"}
    assert castable(_sheet(2)) == {"guiding-bolt": 1, "healing-word": 1}
    assert castable(_sheet(0)) == {}
    damage = spell_command(plan, _combat(20), _party(False), _sheet(2), foe)
    assert damage is not None and damage["spell_id"] == "guiding-bolt"
    heal = spell_command(plan, _combat(20), _party(True), _sheet(2), foe)
    assert heal is not None and heal["spell_id"] == "healing-word"
    assert heal["target_ids"] == ["pc-2"]
    potion = spell_command(plan, _combat(5), _party(False), _sheet(0, potion=True), foe)
    assert potion == {"type": "use_item", "actor_id": "pc-1", "item": "potion-of-healing"}
    assert spell_command(plan, _combat(20), _party(False), _sheet(0), foe) is None
    dumb = Plan(role="caster", hero_id="pc-1", rng=random.Random(1))
    assert spell_command(dumb, _combat(5), _party(True), _sheet(2, potion=True), foe) is None
    assert prefer(["sleep", "bless", "magic-missile"]) == ["magic-missile", "sleep", "bless"]
