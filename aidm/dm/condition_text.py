"""Conditions in plain words for engine lines (M20.7, playtest 3: "Slendee is now true-strike.").

A condition is named by its display name from data/bg3/conditions.json ("True Strike",
"Hunter's Mark"); an unknown id reads in title case. A one-word state ("Prone", "Surprised",
"Blessed") reads as an adjective, anything else as a thing gained:
- "Slendee is surprised." / "Slendee is no longer surprised.";
- "Slendee gains True Strike." / "True Strike ends for Slendee.";
- a batch of the same condition on several creatures reads once: "2 Giant Rats are surprised."
  (same base name, the fight's letters dropped) or "Goblin A and Slendee gain Bane.".

Public API: `condition_label(name)`, `base_name(name)`, `applied_line(who, name)`,
`removed_line(who, name)`, `group_line(names, name)`.
"""

import re
from collections.abc import Sequence

from aidm.data.condition_defs import condition_defs
from aidm.dm.wording import plural

_STATES = frozenset({"prone", "invisible", "unconscious", "dodging", "hidden", "asleep"})
_LETTER = re.compile(r" [A-Z]$")


def condition_label(name: str) -> str:
    defs = condition_defs()
    if name in defs:
        return defs.get(name).name
    return name.replace("-", " ").replace("_", " ").title()


def _is_state(label: str) -> bool:
    low = label.lower()
    return " " not in low and (low.endswith("ed") or low in _STATES)


def base_name(name: str) -> str:
    """'Goblin' for 'Goblin B' (the letter a fight gives same-named foes)."""
    return _LETTER.sub("", name)


def applied_line(who: str, name: str) -> str:
    label = condition_label(name)
    return f"{who} is {label.lower()}." if _is_state(label) else f"{who} gains {label}."


def removed_line(who: str, name: str) -> str:
    label = condition_label(name)
    return (
        f"{who} is no longer {label.lower()}." if _is_state(label) else f"{label} ends for {who}."
    )


def _joined(names: Sequence[str]) -> str:
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} and {names[-1]}"


def group_line(names: Sequence[str], name: str) -> str:
    if len(names) == 1:
        return applied_line(names[0], name)
    bases = {base_name(n) for n in names}
    who = f"{len(names)} {plural(bases.pop())}" if len(bases) == 1 else _joined(names)
    label = condition_label(name)
    return f"{who} are {label.lower()}." if _is_state(label) else f"{who} gain {label}."
