"""A hero who joins between scenes, for the synthetic eval scenes (M38.2).

No committed playtest fixture has a hero who knows the utility cantrips (Light, Mage Hand,
Mending) the keyword router's trap sentences name, so a scene seats one more hero the way the
lobby does (`session.lobby._seat_hero`): the creation rules build a level-1 hero from valid
choices (`rules.creation.build_character`) and one `CreatureAdded` event, applied through the
reducer, puts it in the state. Nothing is mutated by hand.

Public API: `JOINED_ID`, `join_cleric(state)`.
"""

from aidm.data.character_data import character_registries
from aidm.models.abilities import Ability
from aidm.models.creation import AbilityMethod, CreationChoices
from aidm.models.events import CreatureAdded
from aidm.models.state import GameState
from aidm.rules.creation import build_character, validate_creation
from aidm.session.reducer import apply

JOINED_ID = "pc-p10"

# A high-elf cleric: Light and Mending from the cleric list, Mage Hand from the high-elf cantrip
# (wizard list); the class's light crossbow (the "light" trap) and an explorer's pack (torches);
# the standard array, Wisdom first.
_CLERIC = CreationChoices(
    name="Corin",
    race="elf",
    subrace="high-elf",
    class_index="cleric",
    background="acolyte",
    ability_method=AbilityMethod.STANDARD_ARRAY,
    base_scores={
        Ability.STR: 12,
        Ability.DEX: 13,
        Ability.CON: 14,
        Ability.INT: 10,
        Ability.WIS: 15,
        Ability.CHA: 8,
    },
    class_skills=["medicine", "history"],
    language_picks=["dwarvish"],
    equipment_picks={"weapon": 0, "armor": 0, "ranged": 0, "pack": 1, "symbol": 0},
    cantrips=["light", "mending", "sacred-flame"],
    race_cantrips=["mage-hand"],
    prepared=["bless", "cure-wounds", "guiding-bolt"],
)


def join_cleric(state: GameState) -> str:
    """Seat Corin (`JOINED_ID`) at the party's place; returns the new hero's id."""
    regs = character_registries()
    errors = validate_creation(_CLERIC, regs)
    if errors:
        raise ValueError(f"joined cleric: {[e.detail or e.code for e in errors]}")
    hero = build_character(_CLERIC, regs, JOINED_ID)
    apply(state, CreatureAdded(creature=hero))
    return JOINED_ID
