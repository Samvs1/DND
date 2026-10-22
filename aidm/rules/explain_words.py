"""Tooltip text for combat words and roll words, keyed `word:<id>` and `dc:<tier>` (M28.1).

The wording follows docs/PLAYER_MANUAL.md ("Your turn", "How a fight is laid out"). Every number
is read from the rules constants (cover AC, range bands, DC ladder), never retyped. Pure.

Public API: `word_tips() -> dict[str, Tip]`.
"""

from aidm.models.tips import Tip
from aidm.models.zones import CoverLevel
from aidm.rules.checks import DC_BY_TIER
from aidm.rules.zones import COVER_AC, MELEE_RANGE_FEET, NEAR_RANGE_FEET


def _t(title: str, *lines: str) -> Tip:
    return Tip(title=title, lines=lines)


def _combat() -> dict[str, Tip]:
    half, three = COVER_AC[CoverLevel.HALF], COVER_AC[CoverLevel.THREE_QUARTERS]
    both = "Advantage and disadvantage cancel out."
    cover_end = "Melee and same-zone attacks ignore cover."
    return {
        "advantage": _t("Advantage", "Roll two d20 and keep the higher.", both),
        "disadvantage": _t("Disadvantage", "Roll two d20 and keep the lower.", both),
        "half-cover": _t(
            "Half cover",
            f"A ranged attack from another zone at someone here has to beat +{half} AC.",
            cover_end,
        ),
        "three-quarters-cover": _t(
            "Three-quarters cover",
            f"A ranged attack from another zone at someone here has to beat +{three} AC.",
            cover_end,
        ),
        "high-ground": _t(
            "High ground",
            "Attacking from high ground at a target that is not on it gives you advantage.",
            "A ranged attacker below a target on high ground has disadvantage.",
            "In the same zone, nothing changes.",
        ),
        "rough-ground": _t(
            "Rough ground",
            "Entering this zone costs twice the movement.",
            "Grease, ice and webs make a zone rough.",
        ),
        "dark": _t(
            "Dark",
            "Heroes without darkvision attack into a dark zone at disadvantage.",
            "Monsters see in the dark. A carried light lights the places it reaches.",
        ),
        "lit": _t("Lit", "A light reaches this zone, so the dark does not hinder attacks here."),
        "healthy": _t("Unhurt", "More than half of its hit points are left."),
        "wounded": _t("Wounded", "Half of its hit points or fewer are left."),
        "bloodied": _t("Bloodied", "A quarter of its hit points or fewer are left."),
        "fallen": _t("Fallen", "It is dead or down and out of the fight."),
        "fled": _t(
            "Fled",
            "It left the fight. If everyone else falls the party counts as fled, not beaten.",
        ),
    }


def _actions() -> dict[str, Tip]:
    return {
        "action": _t(
            "Action", "One per turn: attack, cast a spell, Dash, Dodge, Help, Hide or use an item."
        ),
        "bonus-action": _t(
            "Bonus action",
            "One per turn, only for things that say so: an off-hand attack, a potion, some spells.",
        ),
        "reaction": _t(
            "Reaction", "One per round. Shown for completeness; no reaction abilities work yet."
        ),
        "movement": _t(
            "Movement",
            "Up to your speed each turn, split as you like.",
            "Moving inside a zone is free; entering another costs the edge's distance.",
        ),
        "dash": _t("Dash", "Adds your speed again to your movement this turn."),
        "dodge": _t(
            "Dodge", "Attacks against you have disadvantage until the start of your next turn."
        ),
        "disengage": _t(
            "Disengage",
            "Lets you flee a fight from an enemy's zone. Leaving never provokes a free attack.",
        ),
        "help": _t(
            "Help",
            "An ally in your zone gets advantage on their next attack or check.",
            "Helping a fallen ally gets them back up with 1 hit point.",
        ),
        "hide": _t(
            "Hide",
            "Roll Stealth against the best Perception of the standing enemies.",
            "You stay hidden until you attack.",
        ),
        "flee": _t(
            "Flee",
            "Leave the fight using the rest of your movement.",
            "With an enemy in your zone, Disengage first.",
        ),
        "range": _t(
            "Range",
            f"{MELEE_RANGE_FEET} ft or less (melee, touch, self) is your own zone.",
            f"Up to {NEAR_RANGE_FEET} ft reaches one zone away; longer reaches two.",
            "Shooting beyond a weapon's normal range is at disadvantage.",
        ),
    }


def _dc() -> dict[str, Tip]:
    return {
        f"dc:{tier.value}": _t(
            tier.value.replace("_", " ").capitalize(), f"The roll has to reach {dc} or more."
        )
        for tier, dc in DC_BY_TIER.items()
    }


def word_tips() -> dict[str, Tip]:
    out = {f"word:{k}": v for k, v in {**_combat(), **_actions()}.items()}
    out.update(_dc())
    return out
