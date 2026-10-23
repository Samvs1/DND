"""Rest asked for in a wordy sentence (M29.5b G17: "We make camp among the thorns and take a short
rest, so Rook can bind his wounds", "The party sets watches and rests for the night" went to the
storyteller, which has no rest tool, so nothing happened). A deterministic precheck like
`aidm.dm.heal_intent`: the sentence becomes the SAME rest proposal (a party vote) the short
commands make; the rules then rest or refuse with their reason.

`wordy_rest(clean)` reads the precheck's normalised sentence and searches it (the short commands
are whole-sentence matches in `aidm.dm.precheck`):
- "take / have a short rest" or "... a long rest" decides (both: None, the sentence is unclear;
  a rest only talked about, "ask about a long rest", is not taken);
- else a short phrase ("catch his breath", "take a breather", "rest for an hour") or a long one
  ("rest(s) for the night", "make / set up / pitch camp", "bed down", "sleep until dawn") decides,
  the long one winning a tie (making camp is the long rest's own word);
- a sentence with a refusal word ("not", "don't", "without", "instead of", "no time") is None:
  it goes on to the storyteller as before.

Public API: `wordy_rest(clean) -> "short" | "long" | None` (the `precheck.RestKind` values).
"""

import re
from typing import Literal

type Rest = Literal["short", "long"]

_TAKE = r"\b(?:take|takes|taking|have|has|having|get|gets) (?:a |an |our |their |his |her )?"
_SHORT_NAMED = re.compile(_TAKE + r"short rest\b")
_LONG_NAMED = re.compile(_TAKE + r"long rest\b")
_SHORT = re.compile(
    r"\b(?:catch(?:es|ing)? (?:his|her|their|our|my|its) breath|take a breather|"
    r"rests? (?:for )?(?:an|one|a) hour)\b"
)
_LONG = re.compile(
    r"\b(?:rest(?:s|ing)? (?:for the night|until (?:morning|dawn))|"
    r"(?:make|makes|making|set up|sets up|pitch|pitches) camp|camp for the night|"
    r"beds? down|sleeps? (?:for the night|until (?:morning|dawn)))\b"
)
_REFUSED = re.compile(r"\b(?:not|don't|do not|won't|without|instead of|no time|can't|cannot)\b")


def wordy_rest(clean: str) -> Rest | None:
    if _REFUSED.search(clean):
        return None
    short, long = bool(_SHORT_NAMED.search(clean)), bool(_LONG_NAMED.search(clean))
    if short != long:
        return "short" if short else "long"
    if short and long:
        return None
    if _LONG.search(clean):
        return "long"
    return "short" if _SHORT.search(clean) else None
