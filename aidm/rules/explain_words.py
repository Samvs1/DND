"""Tooltip text for combat words and roll words, keyed `word:<id>` and `dc:<tier>` (M28.1).

The wording follows docs/PLAYER_MANUAL.md ("Your turn", "How a fight is laid out"). Every number
is read from the rules constants (cover AC, range bands, DC ladder), never retyped. Pure.

Public API: `word_tips() -> dict[str, Tip]`.
"""

from aidm.models.tips import Tip
from aidm.models.zones import CoverLevel
from aidm.rules.attack_profiles import IMPROVISED_THROW
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
        "tooltips": _t(
            "Tooltips", "Tap a ? to see what a thing means.", "Turn them off in Settings."
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


def _moves() -> dict[str, Tip]:
    return {
        "attack": _t(
            "Attack",
            "Pick a foe in reach: melee needs the same zone, ranged needs the weapon's range.",
            "With no weapon in hand you strike unarmed.",
        ),
        "throw": _t(
            "Throw",
            "An action: hurl a carried object at a foe in throw range.",
            f"A thrown weapon uses its own numbers; else {IMPROVISED_THROW} improvised.",
            "The object leaves your pack, hit or miss.",
        ),
        "shove-prone": _t(
            "Shove prone",
            "A bonus action on a foe in your zone, at most one size larger.",
            "It rolls Athletics or Acrobatics, you roll Athletics, and you must beat its total.",
            "On a win it falls prone.",
        ),
        "shove-push": _t(
            "Shove away",
            "A bonus action on a foe in your zone, at most one size larger.",
            "It rolls Athletics or Acrobatics, you roll Athletics, and you must beat its total.",
            "On a win it is pushed into a neighbouring zone you pick.",
        ),
        "jump": _t(
            "Jump",
            "A bonus action: leap to a neighbouring zone, paying the edge's distance.",
            "Rough ground does not slow a jump. You cannot jump while prone.",
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


def _play() -> dict[str, Tip]:
    """Words of the Play tab: the Now card, the quest offer and finale cards, roll results."""
    return {
        "boon": _t(
            "Gear boon",
            "Something you carry helps you with the skills or saves listed.",
            "It gives advantage on them until it ends: leaving the place or a long rest.",
        ),
        "light-note": _t(
            "Light and noise",
            "A light in a dark place shows you to anything waiting, so it cannot be surprised.",
            "Noise can wake a place too. The note fades after a little while.",
        ),
        "quest-offer": _t(
            "A quest offer",
            "Someone asks for help. Accept to take the task on, or Not now to decide later.",
            "The offer stays and returns when you are next where they are.",
        ),
        "finale": _t(
            "The ending",
            "The last region is done. The party picks how the story closes.",
            "You are asked to confirm, because the choice ends the story.",
        ),
        "nat20": _t(
            "Natural 20",
            "The d20 showed 20. A check always succeeds and an attack always hits, and hits hard.",
        ),
        "nat1": _t(
            "Natural 1", "The d20 showed 1. A check always fails and an attack always misses."
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
    out = {f"word:{k}": v for k, v in {**_combat(), **_actions(), **_moves(), **_play()}.items()}
    out.update(_dc())
    return out
