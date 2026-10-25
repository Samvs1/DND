"""The typed lines the simulation sends where it means one engine action (M36.10b).

Since the menu interpreter is the default (SPEC 6.2), a line plays an act with no model call only
when it is exactly a label the game shows (`aidm.dm.chooser.exact_choice`). The fake model reads
nothing else (its unscripted pick is `other`, the storyteller's; DECISIONS M36.10a), so the bots
type the menu's own labels; flavour lines stay plain words.

Public API: `BROWSE`, `SHORT_REST`, `LONG_REST`, `PUT_OUT`, `LIGHT_TORCH`, `travel_line(name)`,
`pick_up_line(name)`.
"""

BROWSE = "Trade with a shopkeeper here"
SHORT_REST = "Short rest"
LONG_REST = "Long rest"
PUT_OUT = "Put out your light"
LIGHT_TORCH = "Light the torch"


def travel_line(name: str) -> str:
    return f"Travel to a place {name}"


def pick_up_line(name: str) -> str:
    return f"Pick up {name}"
