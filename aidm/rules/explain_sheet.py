"""Tooltip text for sheet terms and journal terms, keyed `sheet:<id>` and `journal:<id>` (M28.1).

Numbers come from the rules constants and data tables. Wording follows docs/PLAYER_MANUAL.md. Pure.

Public API: `sheet_tips() -> dict[str, Tip]`, `journal_tips() -> dict[str, Tip]`.
"""

from aidm.data.shop_defs import shop_table
from aidm.models.tips import Tip
from aidm.rules.checks import PASSIVE_BASE
from aidm.rules.death import DEATH_SAVE_DC
from aidm.rules.rests import CAMP_SUPPLY_PER_MEMBER, MAX_SHORT_RESTS


def _t(title: str, *lines: str) -> Tip:
    return Tip(title=title, lines=lines)


_ABILITIES = {
    "str": ("Strength", "Melee attacks and damage, Athletics, carrying."),
    "dex": ("Dexterity", "Armour class, initiative, ranged attacks, Stealth and Acrobatics."),
    "con": ("Constitution", "Hit points and concentration."),
    "int": ("Intelligence", "Wizard spells, Arcana, Investigation, History."),
    "wis": ("Wisdom", "Cleric and ranger spells, Perception, Insight, Survival."),
    "cha": ("Charisma", "Warlock spells, Persuasion, Deception, Intimidation."),
}


def _stats() -> dict[str, Tip]:
    trained = "A d20 plus the ability modifier, plus proficiency if trained."
    cost = f"{CAMP_SUPPLY_PER_MEMBER} camp supplies for each living hero"
    return {
        "abilities": _t(
            "Abilities",
            "Six scores. Each gives a modifier that is added to the rolls that use it.",
            "The small number under a score is your saving throw for it: a d20 plus that number,"
            " to resist spells and hazards.",
            "A saving throw you are trained in adds your proficiency bonus.",
        ),
        "training": _t(
            "Training",
            "Armour, weapons, tools and languages you know.",
            "Trained gear adds your proficiency bonus; untrained armour or weapons do not.",
        ),
        "saves": _t("Saving throws", trained, "Used to resist spells and hazards."),
        "skills": _t(
            "Skills", trained, "The Dungeon Master asks for one when the outcome is uncertain."
        ),
        "speed": _t("Speed", "How many feet you can move on your turn."),
        "initiative": _t(
            "Initiative",
            "Rolled at the start of a fight to set the turn order: a d4 plus Dexterity.",
        ),
        "proficiency": _t(
            "Proficiency bonus", "Added to attacks, saves and skills you are trained in."
        ),
        "passive-perception": _t(
            "Passive Perception",
            f"{PASSIVE_BASE} plus your Perception bonus.",
            "What you notice without trying.",
        ),
        "ac": _t("Armour class", "Attacks have to roll this or higher to hit you."),
        "hp": _t(
            "Hit points",
            "At 0 you fall and make death saves.",
            f"A death save is a d20 against {DEATH_SAVE_DC}.",
        ),
        "xp": _t("Experience", "Earned from victories and quests. Enough of it lets you level up."),
        "slots": _t(
            "Spell slots",
            "Leveled spells spend a slot of their level or higher.",
            "A long rest brings them all back; cantrips are free.",
        ),
        "supplies": _t("Camp supplies", f"A long rest costs {cost}.", "Shared by the whole party."),
        "short-rest": _t(
            "Short rest",
            "Every living hero regains half their hit points.",
            f"At most {MAX_SHORT_RESTS} between long rests.",
        ),
        "long-rest": _t(
            "Long rest", "Full hit points, spell slots and abilities.", f"Costs {cost}."
        ),
        "keepsake": _t(
            "Keepsake", "A thing from the story. It has no gear use, but you can give it away."
        ),
        "quest-item": _t("Quest item", "Needed for a task in the story. Keep it safe."),
    }


def sheet_tips() -> dict[str, Tip]:
    out = {
        f"sheet:{k}": _t(name, use, "The modifier is added to rolls that use it.")
        for k, (name, use) in _ABILITIES.items()
    }
    out.update({f"sheet:{k}": v for k, v in _stats().items()})
    return out


def journal_tips() -> dict[str, Tip]:
    shop = shop_table()
    buy, sell = round(shop.buy_markup * 100), round(shop.sell_fraction * 100)
    entries = {
        "main-quest": _t(
            "Main quest",
            "The task of this region, pinned at the top.",
            "It can be done by more than one way.",
        ),
        "ways": _t(
            "Ways",
            "Force, Peace or Cunning: different roads to the same goal.",
            "Each shows the steps you have done.",
        ),
        "leads": _t("Leads", "Rumours of people who may need help.", "Go there to hear them out."),
        "left-behind": _t(
            "Left behind",
            "Tasks you did not finish before crossing into a new region.",
            "No penalty; they stay in the journal.",
        ),
        "favours": _t(
            "Favours",
            "Small asks from people you meet.",
            "They earn goodwill, never gold or items.",
        ),
        "what-now": _t(
            "What now?", "Tells you the next step in a few short lines, from what you already know."
        ),
        "scribe": _t("The Scribe", "Rewrites a fallen hero for a price, when the table asks."),
        "buy-price": _t("Buying", f"You pay {buy}% of an item's value, rounded up, at least 1 gp."),
        "sell-price": _t("Selling", f"A shop pays {sell}% of an item's value, rounded down."),
    }
    return {f"journal:{k}": v for k, v in entries.items()}
