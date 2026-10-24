"""A typed search where something is hidden (M31.1a V9, round 4: "I search the ash-buried shelves
for a note about the depths ..., pick it up, and read it" went to the storyteller, which lit a
candle and asked for no check, so the hidden key was never found).

The `search` phrase row (data/bg3/intent_phrases.json, condition `hidden_here`: something is
hidden in this place) reads a search ("search", "rummage", "comb", "scour", "look for" ...) and
the resolver returns a `SearchIntent`: the session rolls ONE discovery check
(`rules.searching.search_events`, the skill from the row: Investigation, or Perception for
"look for") and tells it. What the line goes on to do after the search ("..., pick it up, and
read it") is `rest`, cut at the first follow-up verb of the lexicon's `search_follow_verbs` and
sent to the storyteller with the search's events. With nothing hidden here the row does not
match and the storyteller handles the search as before.

Public API: `SearchIntent(actor_id, skill, rest)`, `RESOLVERS` (`search`), `follow_up(text)`.
"""

import re
from dataclasses import dataclass

from aidm.data.intent_phrases import intent_phrases
from aidm.dm.intent_match import Found, Resolver
from aidm.models.abilities import Skill

_CUT = re.compile(r"(?:,? and then |,? then |; |, and |, | and )(?P<verb>[a-z']+)")


@dataclass(frozen=True)
class SearchIntent:
    actor_id: str
    skill: Skill
    rest: str | None = None


def follow_up(text: str) -> str | None:
    """The part after the search that does something else ("pick it up, and read it")."""
    follows = intent_phrases().lexicon["search_follow_verbs"]
    for m in _CUT.finditer(text):
        if m.group("verb") in follows:
            return text[m.start("verb") :].strip(" .") or None
    return None


def search(found: Found) -> SearchIntent:
    return SearchIntent(found.actor_id, Skill(str(found.params["skill"])), follow_up(found.text))


RESOLVERS: dict[str, Resolver] = {"search": search}
