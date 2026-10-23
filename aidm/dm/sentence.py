"""Plain readings of a typed sentence for the deterministic pre-checks (M29.7a).

The pre-checks (`aidm.dm.precheck` and the typed fight paths) match whole sentences. Players
also write in the third person ("Elowen wields the new warhammer instead") and join two acts
in one sentence ("I light a candle to see, then look around"). These helpers give the readers
one shared, conservative way to see such sentences:
- `normalise(text)`: lower case, plain quotes, single spaces, no closing punctuation or
  "please", and no leading subject ("i", "we", "i'll", "let's" ...);
- `own_reading(name, clean)`: a sentence that starts with the hero's own name (full or first)
  reads as the hero's own command, its verb in the plain form ("elowen wields the hammer" ->
  "wield the hammer"); any other sentence is returned unchanged;
- `split_clause(clean) -> (head, rest) | None`: the first act and the rest of a compound
  sentence, cut at ", then", " then", " and then", ", and", " and", ";" (the first cut that
  leaves words on both sides); None when there is no such cut.

Public API: `normalise`, `own_reading`, `split_clause`, `plain_verb`.
"""

import re

_SUBJECT = re.compile(
    r"^(?:please |ok |okay )?(?:(?:i|we)(?: will| shall|'ll| want to| would like to)?|let'?s|"
    r"let us)\s+"
)
_CUTS = (", and then ", ", then ", " and then ", " then ", "; ", ", and ", " and ")
_KEEP_ES = ("shes", "ches", "xes", "sses", "zzes", "oes")


def normalise(text: str) -> str:
    clean = " ".join(text.lower().replace("’", "'").split())
    clean = clean.rstrip(".!?").removesuffix(" please").strip()
    return _SUBJECT.sub("", clean, count=1).strip()


def plain_verb(verb: str) -> str:
    """The plain form of a third-person verb ("wields" -> "wield", "pinches" -> "pinch",
    "carries" -> "carry"); a word without the ending is returned unchanged."""
    if len(verb) > 4 and verb.endswith("ies"):
        return verb[:-3] + "y"
    if verb.endswith(_KEEP_ES):
        return verb[:-2]
    if len(verb) > 3 and verb.endswith("s") and not verb.endswith("ss"):
        return verb[:-1]
    return verb


def own_reading(name: str, clean: str) -> str:
    low = name.lower().strip()
    for prefix in dict.fromkeys((low, low.split()[0] if low else "")):
        if prefix and clean.startswith(f"{prefix} "):
            verb, _, rest = clean[len(prefix) + 1 :].partition(" ")
            return f"{plain_verb(verb)} {rest}".strip()
    return clean


def split_clause(clean: str) -> tuple[str, str] | None:
    for cut in _CUTS:
        head, found, rest = clean.partition(cut)
        if found and head.strip() and rest.strip():
            return head.strip(" ,"), rest.strip(" ,")
    return None
