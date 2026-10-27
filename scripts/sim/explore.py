"""Exploration texts per role (fighter, explorer, chaotic), chosen with the bot's seeded RNG.

Texts are plain player sentences built from what the public snapshot shows (present NPCs,
visible features), so they read like a table of real players. The chatty explorer talks to
NPCs, looks around, investigates, asks about secrets and proposes travel.

Public API: `explore_text`, `travel_text`, `scene_of`, `exit_names`.
"""

import random

from scripts.sim.chaos import chaos_text
from scripts.sim.client import Msg
from scripts.sim.menu_lines import travel_line

FIGHTER_LINES = (
    "I draw my sword and scan the crowd for trouble.",
    "I stretch, roll my shoulders and warm up with a few practice cuts.",
    "I stride to the front of the party and keep a hand on my sword.",
    "I check my gear and look for anyone who might attack.",  # M43.2: flavour names no item
)


def scene_of(state: Msg) -> Msg:
    return state.get("scene") or {}


def exit_names(state: Msg, *, unlocked_only: bool = True) -> list[str]:
    exits = scene_of(state).get("exits", [])
    return [e["name"] for e in exits if not (unlocked_only and e["locked"])]


def travel_text(state: Msg, rng: random.Random, prefer_new: bool = True) -> str | None:
    exits = [e for e in scene_of(state).get("exits", []) if not e["locked"]]
    fresh = [e for e in exits if not e["visited"]]
    pool = fresh if (prefer_new and fresh) else exits
    return travel_line(rng.choice(pool)["name"]) if pool else None


def _explorer(state: Msg, rng: random.Random) -> str:
    scene = scene_of(state)
    npcs = [n["name"] for n in scene.get("npcs", [])]
    features = [f["name"] for f in scene.get("features", [])]
    options = [
        "look around",
        "I search the area carefully for anything hidden or out of place.",
        "I listen at the edge of the crowd for rumours about the old beacon.",
    ]
    for npc in npcs:
        options += [
            f"I talk to {npc} and ask what they know about this place.",
            f"I ask {npc} whether they are keeping any secrets from us.",
            f"I greet {npc} warmly and offer to buy a drink.",
        ]
    options += [f"I investigate the {name} closely." for name in features]
    return rng.choice(options)


def explore_text(role: str, state: Msg, rng: random.Random) -> str:
    if role == "fighter":
        return rng.choice(FIGHTER_LINES)
    if role == "chaos":
        return chaos_text(rng)
    return _explorer(state, rng)  # the explorer, and the M29.2 rogue and caster roles
