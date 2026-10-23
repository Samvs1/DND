"""Play styles of the M29.2 campaign bots (docs/next/GOAL_BALANCE.md "Layer 1").

A style changes only the bots' CHOICES, never the engine: how an encounter offer is answered
(fight, surprise = sneak in, parley = talk), how hurt the party may get before a short rest or
a night in camp, whether it camps before a boss, what it buys at the hub, whether it searches
the places it visits, and whether it follows the region's Peace way (find the main quest's
item and hand it to the master instead of fighting).

`balanced` is the reference style (the GOAL's "balanced play style" for the clean-win target).

Public API: `Style`, `STYLES`, `style_of(name)`.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Style:
    name: str
    offer: str  # the answer to a spoke's encounter offer: fight | surprise | parley
    boss: str  # the answer to the boss: fight | surprise | parley (parley only with the item)
    short_below: float  # short rest when the most hurt hero is below this share of its HP
    long_below: float  # make camp when the most hurt hero is below this share of its HP
    camp_before_boss: bool  # make camp at the hub before walking to the boss, if anyone is hurt
    shop: str  # none: camp food only when out | basic: a healer's kit too | spender: potions
    search: bool  # search every place visited (finds hidden quest items)
    peace: bool  # follow the Peace way: carry the hidden item to the master and parley
    talk: bool = False  # talk to the people of every place visited (an exploration round)


STYLES: dict[str, Style] = {
    s.name: s
    for s in (
        Style("balanced", "fight", "fight", 0.8, 0.6, True, "basic", False, False),
        Style("aggressive", "fight", "fight", 0.35, 0.2, False, "basic", False, False),
        Style("cautious", "fight", "fight", 0.95, 0.8, True, "basic", True, False),
        Style("talker", "parley", "parley", 0.8, 0.6, True, "basic", True, True, True),
        Style("cunning", "surprise", "surprise", 0.8, 0.6, True, "basic", True, False),
        Style("spender", "fight", "fight", 0.8, 0.6, True, "spender", False, False),
        Style("hoarder", "fight", "fight", 0.8, 0.6, True, "none", False, False),
    )
}


def style_of(name: str) -> Style:
    if name not in STYLES:
        raise ValueError(f"unknown style {name!r} (one of {', '.join(STYLES)})")
    return STYLES[name]
