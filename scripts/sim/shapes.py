"""Party shapes of the M29.2 campaign runs (docs/next/GOAL_BALANCE.md "Layer 1").

A shape is the list of (bot role, class) seated in join order (the first is the host); the
classes are the six the data ships (fighter, ranger, rogue, cleric, wizard, warlock). Roles
pick the bot's habits (`scripts.sim.bot.PLAN_ROLE`: fighters close in, casters use spells,
rogues dodge when hurt; the `explorer` is the party's talker and searcher). There is no chaotic
player in a shape: these runs measure balance, the M9.1 run keeps the chaos.

Heroes are built like a plain player would: the standard array with the best scores in the
class's main abilities (`PRIORITY`) and the spells of `scripts.sim.spells.PREFERRED` first.

Public API: `SHAPES`, `PRIORITY`, `smart_choices(class_index, name, rng)`, `seat_shape(url, seed,
shape, report)`, `main_ability(class_index)`.
"""

import random

from aidm.data.character_data import character_registries
from aidm.rules.creation_checks import class_spell_indexes
from scripts.sim.bot import Bot
from scripts.sim.client import Conn, Msg
from scripts.sim.report import Report
from scripts.sim.setup import Party, choices_for
from scripts.sim.spells import prefer

SHAPES: dict[str, tuple[tuple[str, str], ...]] = {
    "classic": (
        ("fighter", "fighter"),
        ("explorer", "cleric"),
        ("rogue", "rogue"),
        ("caster", "wizard"),
    ),
    "martial": (
        ("fighter", "fighter"),
        ("fighter", "ranger"),
        ("rogue", "rogue"),
        ("fighter", "fighter"),
    ),
    "casters": (
        ("caster", "wizard"),
        ("explorer", "cleric"),
        ("caster", "warlock"),
        ("caster", "wizard"),
    ),
    "solo": (("fighter", "fighter"),),
    "duo": (("fighter", "fighter"), ("explorer", "cleric")),
}
NAMES = ("Brienne", "Elowen", "Rook", "Tamsin")
PRIORITY: dict[str, tuple[str, ...]] = {
    "fighter": ("str", "con", "dex", "wis", "cha", "int"),
    "ranger": ("dex", "con", "wis", "str", "int", "cha"),
    "rogue": ("dex", "con", "wis", "int", "cha", "str"),
    "wizard": ("int", "con", "dex", "wis", "cha", "str"),
    "cleric": ("wis", "con", "str", "dex", "cha", "int"),
    "warlock": ("cha", "con", "dex", "wis", "int", "str"),
}
PREPARED_AT_START = 3  # main ability 15+ -> modifier 2+, plus level 1: the limit is at least 3


def main_ability(class_index: str) -> str:
    return PRIORITY.get(class_index, ("con",))[0]


def smart_choices(class_index: str, name: str, rng: random.Random) -> Msg:
    """`choices_for` with the scores placed by `PRIORITY` and the preferred level-1 spells."""
    made = choices_for(class_index, name, rng)
    order = PRIORITY.get(class_index)
    if order is not None:
        scores = sorted(made["base_scores"].values(), reverse=True)
        made["base_scores"] = dict(zip(order, scores, strict=True))
    pool = sorted(class_spell_indexes(character_registries().spells, class_index, 1, 1))
    if made["spells"]:
        made["spells"] = prefer(pool)[: len(made["spells"])]
    if made["prepared"]:
        made["prepared"] = prefer(made["spells"] or pool)[:PREPARED_AT_START]
    return made


async def seat_shape(url: str, seed: int, shape: str, report: Report) -> Party:
    bots: list[Bot] = []
    for index, (role, class_index) in enumerate(SHAPES[shape]):
        conn = Conn(NAMES[index], url)
        await conn.open()
        await conn.hello()
        rng = random.Random(seed * 1000 + index)
        bot = Bot(conn, role, class_index, rng, report)
        bot.plan.smart = True
        choices = smart_choices(class_index, NAMES[index], rng)
        result = await bot.create_hero(choices)
        if not result["ok"]:
            report.fail(f"creation of {role} {class_index} refused: {result['errors']}")
        report.say(f"{role}: {class_index} {choices['race']}/{choices['subrace']} seated")
        bots.append(bot)
    return Party(bots)
