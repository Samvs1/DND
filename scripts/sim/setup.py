"""Seat the three bots and build their heroes through the protocol.

Join order matters: the first player is the host, so the fighter joins first. Races are drawn
with the seed (any legal race x subrace), the classes are fighter, cleric-or-wizard and rogue.
The rogue uses the rolled-abilities path (`roll_abilities` -> `ability_rolls` -> assignment).

Public API: `Party`, `seat_party`.
"""

import random
from dataclasses import dataclass

from aidm.data.character_data import character_registries
from aidm.models.abilities import ABILITIES
from aidm.rules.creation_checks import class_spell_indexes
from scripts.sim.bot import Bot
from scripts.sim.client import Conn, Msg
from scripts.sim.report import Report
from tests.unit.rules.creation_fixtures import default_choices, race_combos

NAMES = {"fighter": "Brienne", "explorer": "Elowen", "chaos": "Rook"}


@dataclass
class Party:
    fighter: Bot
    explorer: Bot
    chaos: Bot

    @property
    def bots(self) -> list[Bot]:
        return [self.fighter, self.explorer, self.chaos]


# Attack cantrips first, so the caster's first cantrip is one that hurts (guidance is a buff).
CANTRIPS = {
    "cleric": ["sacred-flame", "guidance", "resistance"],
    "wizard": ["fire-bolt", "ray-of-frost", "acid-splash"],
}


def _choices(class_index: str, name: str, rng: random.Random) -> Msg:
    race, sub = rng.choice(race_combos())
    made = default_choices(class_index, race, sub).model_copy(update={"name": name})
    picks = CANTRIPS.get(class_index)
    if picks is not None:
        regs = character_registries()
        race_obj = regs.races.get(race)
        sub_obj = next((x for x in race_obj.subraces if x.index == sub), None)
        source = race_obj.cantrip_class or (sub_obj.cantrip_class if sub_obj else None)
        extra: list[str] = []
        if source:
            pool = sorted(class_spell_indexes(regs.spells, source, 0, 0))
            extra = [c for c in pool if c not in picks][: len(made.race_cantrips)]
        made = made.model_copy(update={"cantrips": picks, "race_cantrips": extra})
    return made.model_dump(mode="json")


async def _rolled(bot: Bot, choices: Msg) -> Msg:
    """Switch `choices` to the rolled method with the scores this table rolled for the bot."""
    conn = bot.conn
    mark = conn.mark()
    await conn.send({"type": "roll_abilities"})
    rolled = await conn.wait_for(lambda m: m["type"] == "ability_rolls", 15.0, mark)
    totals = sorted((r["total"] for r in rolled["rolls"]), reverse=True)
    scores = dict(zip((a.value for a in ABILITIES), totals, strict=True))
    return {
        **choices,
        "ability_method": "roll_4d6",
        "rolls": rolled["rolls"],
        "base_scores": scores,
    }


async def seat_party(url: str, seed: int, report: Report) -> Party:
    explorer_class = "cleric" if seed % 2 else "wizard"
    plan = (
        ("fighter", "fighter"),
        ("explorer", explorer_class),
        ("chaos", "rogue"),
    )
    bots: list[Bot] = []
    for role, class_index in plan:
        conn = Conn(NAMES[role], url)
        await conn.open()
        await conn.hello()
        rng = random.Random(seed * 1000 + len(bots))
        bot = Bot(conn, role, class_index, rng, report)
        choices = _choices(class_index, NAMES[role], rng)
        if role == "chaos":
            choices = await _rolled(bot, choices)
        result = await bot.create_hero(choices)
        if not result["ok"]:
            report.fail(f"creation of {role} {class_index} refused: {result['errors']}")
        report.say(f"{role}: {class_index} {choices['race']}/{choices['subrace']} seated")
        bots.append(bot)
    return Party(*bots)
