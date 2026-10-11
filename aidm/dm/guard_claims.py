"""False travel and invented-stranger checks of the prose guard (QA-10, DECISIONS M9.5).

- Travel: the party moves only through `move_party` or a travel vote; the scene is built from the
  state AFTER this turn's events, so the current node is already the new one. A sentence with an
  arrival phrase (`arrival_phrases`: "arrive at", "step into", "you are now in") followed within
  `PLACE_REACH` characters by the name of ANOTHER map node is a false claim ("You step into the
  Sunken Vestry." after a refused move).
- Strangers: people exist only once registered. "A one-eyed sea captain steps out of the fog" is
  flagged when an indefinite article, at most three words, a person noun (`stranger_nouns`) and
  an entrance verb (`entrance_verbs`, within `ENTRANCE_REACH` characters) appear in that order,
  and the noun is not a role or name word of anyone present (so "a guard approaches" with Hobb
  the guard present is clean).

- Offer blows (M20.6, playtest 3: "the burst of eldritch light catches it mid-flight, sending it
  tumbling into the black water" was told while the party had not yet chosen to fight): while an
  encounter offer waits for the party's answer, a violent outcome (`blow_claims`) is flagged.

Public API: `PLACE_REACH`, `ENTRANCE_REACH`, `false_travel(sentence, scene)`,
`invented_strangers(sentence, scene)`, `offer_blows(sentence, scene)`.
"""

import re

from aidm.dm.guard_scene import GuardScene
from aidm.dm.guard_text import find_phrases
from aidm.dm.guard_types import Violation, ViolationKind

PLACE_REACH = 12
ENTRANCE_REACH = 30


def false_travel(sentence: str, scene: GuardScene) -> list[Violation]:
    if not scene.other_places:
        return []
    low = sentence.casefold()
    for m in find_phrases(low, scene.lexicon.arrival_phrases):
        for place in sorted(scene.other_places, key=len, reverse=True):
            at = re.search(rf"(?<![a-z]){re.escape(place)}(?![a-z])", low[m.end() :])
            if at is not None and at.start() <= PLACE_REACH:
                detail = f"the party is not at {scene.other_places[place]}; no travel happened"
                return [Violation(ViolationKind.FALSE_TRAVEL, place, detail)]
    return []


def invented_strangers(sentence: str, scene: GuardScene) -> list[Violation]:
    lex = scene.lexicon
    nouns = "|".join(re.escape(n) for n in sorted(lex.stranger_nouns, key=len, reverse=True))
    if not nouns:
        return []
    pattern = rf"(?<![a-z])(?:a|an)\s+(?:[a-z'-]+\s+){{0,3}}?({nouns})(?![a-z])"
    low = sentence.casefold()
    present = {w.casefold() for name in scene.present_npcs for w in name.split()}
    for m in re.finditer(pattern, low):
        noun = m.group(1)
        if noun in scene.present_roles or noun in present:
            continue
        verbs = find_phrases(low[m.end() : m.end() + ENTRANCE_REACH], lex.entrance_verbs)
        if verbs:
            detail = f"no {noun} is in this scene; only registered NPCs exist"
            return [Violation(ViolationKind.INVENTED_STRANGER, m.group(0), detail)]
    return []


def offer_blows(sentence: str, scene: GuardScene) -> list[Violation]:
    if not scene.offer_pending:
        return []
    hit = find_phrases(sentence, scene.lexicon.blow_claims)
    if not hit:
        return []
    detail = "nothing has happened yet: the party has not chosen to fight"
    return [Violation(ViolationKind.OFFER_BLOW, hit[0].group(0), detail)]
