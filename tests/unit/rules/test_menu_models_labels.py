"""Action menu models (validators only) and menu labels (M36.2, SPEC 6.2)."""

import pytest
from pydantic import ValidationError

from aidm.data.combat_data import combat_registries
from aidm.models.action_menu import (
    ActionKind,
    ActionMenu,
    MenuChoice,
    MenuEntry,
    MenuScope,
    MenuStep,
    MenuTarget,
)
from aidm.models.sheet import FeatureActionLine, SpellLine
from aidm.models.state import Creature
from aidm.rules.menu_labels import (
    distance_text,
    feature_label,
    item_label,
    spell_label,
    state_word,
    strike_label,
)
from aidm.rules.menu_view import slug

KOBOLD = MenuTarget(id="kobold-1", label="Kobold A, 15 ft, unhurt", kind="foe")


def _sword(**extra: object) -> MenuEntry:
    data: dict[str, object] = {
        "id": "attack:longsword",
        "kind": ActionKind.ATTACK,
        "label": "Longsword (melee, 1d8+3)",
        "target_ids": ("kobold-1",),
        "max_targets": 1,
    }
    data.update(extra)
    return MenuEntry.model_validate(data)


def test_menu_entry_ids_follow_the_pattern() -> None:
    assert _sword().id == "attack:longsword"
    with pytest.raises(ValidationError):
        _sword(id="Attack Longsword")


def test_menu_entry_notes_only_for_listed_targets() -> None:
    with pytest.raises(ValidationError):
        _sword(approach={"kobold-2": 15})
    with pytest.raises(ValidationError):
        _sword(far=("kobold-2",))
    with pytest.raises(ValidationError):
        _sword(max_targets=0)


def test_action_menu_rejects_duplicates_and_unknown_targets() -> None:
    ok = ActionMenu(scope=MenuScope.FIGHT, actor_id="pc-p2", entries=(_sword(),), targets=(KOBOLD,))
    assert ok.entries[0].target_ids == ("kobold-1",)
    with pytest.raises(ValidationError):
        ActionMenu(
            scope=MenuScope.FIGHT, actor_id="pc-p2", entries=(_sword(), _sword()), targets=(KOBOLD,)
        )
    with pytest.raises(ValidationError):
        ActionMenu(scope=MenuScope.FIGHT, actor_id="pc-p2", entries=(_sword(),))


def test_menu_choice_is_steps_other_or_both() -> None:
    step = MenuStep(entry="attack:longsword", targets=("kobold-1",))
    assert MenuChoice(steps=(step,)).other is False
    assert MenuChoice(other=True).steps == ()
    both = MenuChoice(steps=(step,), other=True, other_text="leap onto the table", other_first=True)
    assert both.other_first and both.steps == (step,)  # M36.5: a stunt and an attack
    with pytest.raises(ValidationError):
        MenuChoice()
    with pytest.raises(ValidationError):
        MenuChoice(steps=(step,), other_first=True)
    with pytest.raises(ValidationError):
        MenuChoice(steps=(step,) * 5)


def _creature(hp: int, dead: bool = False) -> Creature:
    return Creature.model_validate(
        {
            "id": "k",
            "name": "Kobold",
            "kind": "monster",
            "hp": hp,
            "max_hp": 20,
            "ac": 12,
            "dead": dead,
        }
    )


def test_menu_state_words() -> None:
    words = [state_word(_creature(hp)) for hp in (20, 11, 10, 5, 0)]
    assert words == ["unhurt", "hurt", "wounded", "bloodied", "down"]
    assert state_word(_creature(0, dead=True)) == "dead"
    assert distance_text(0) == "here" and distance_text(25) == "25 ft"


def test_menu_strike_labels() -> None:
    assert strike_label("Longbow", "ranged", "1d8+3", "73% vs Kobold") == (
        "Longbow (ranged, 1d8+3, 73% vs Kobold)"
    )
    assert strike_label("Unarmed Strike", "melee", "4") == "Unarmed Strike (melee, 4 damage)"
    assert (
        strike_label("Rapier", "melee", "1d8+2", draw=True) == "Rapier (melee, 1d8+2, draws first)"
    )


def test_golden_menu_spell_labels_from_data() -> None:
    spells = combat_registries().spells
    hands = SpellLine(index="burning-hands", name="Burning Hands", level=1, prepared=True)
    # SRD 5.1 Burning Hands: 1st level, 15-foot cone, DEX save, fire damage.
    assert spell_label(spells.get("burning-hands"), hands, 2) == (
        "Burning Hands (level 1, DEX save, fire, 15 ft cone, 2 slots left)"
    )
    word = SpellLine(index="healing-word", name="Healing Word", level=1, prepared=True)
    # SRD 5.1 Healing Word: 1st level, bonus action, range 60 feet, heals.
    assert spell_label(spells.get("healing-word"), word, 1) == (
        "Healing Word (level 1, healing, 60 ft, bonus action, 1 slot left)"
    )


def test_menu_feature_and_item_labels() -> None:
    wind = FeatureActionLine(
        feature="second-wind",
        name="Second Wind",
        economy="bonus_action",
        available=True,
        resource="second-wind",
        uses_left=1,
        uses_max=1,
        heal="1d10+2",
    )
    assert feature_label(wind) == "Second Wind (bonus action, heals 1d10+2, 1 left)"
    assert item_label("Potion of Healing", "2d4+2", 3) == (
        "Potion of Healing (bonus action, heals 2d4+2, 3 left)"
    )
    assert slug("Turn Undead") == "turn-undead"
