"""Ending checks of the prose guard (M31.1c V20, docs/playtests/M31_round4.md full 1643).

Round 4's ending told the Grieving Spark "won over" and also "laid low": the finale question,
written before the party chose a road, said so, and the model copied it. An NPC who sided with
the party and lives (`allies`: a region won by alliance whose boss still lives and did not turn,
or an NPC whose attitude ended as ally) is never told defeated in prose about the past:
`ally_defeated` flags a defeat word (`ally_defeat_claims`: "laid low", "slain", "fell") within
`CLAIM_REACH` characters after the ally's name, unless negated or hedged; a skip phrase ("fell
silent", `ally_defeat_skips`) is not a defeat. Vocabulary is data (data/bg3/guard_lexicon.json).

M32.1b X15 (round 5, full 1443: "ended where it began, in the Flooded Chapel" while it began in
Tidefall and ended in Caulmere): `wrong_ends` flags a full-circle phrase (`full_circle_claims`)
when the tale began and ended in different places, and a begin word (`began_words`) or an end
word (`ended_words`) followed by "in/at <place>" naming another place than the state's.

Public API: `allies(state) -> dict[str, str]` (term -> name), `ally_defeated(text, terms, lex)
-> list[Violation]` (every sentence of `text`), `TaleEnds`, `tale_ends(state, began, ended)`,
`wrong_ends(text, ends, lex) -> list[Violation]`.
"""

import re
from dataclasses import dataclass

from aidm.data.guard_lexicon import GuardLexicon
from aidm.dm.guard_alive import living_declared_dead
from aidm.dm.guard_text import find_phrases, plain, tokenize
from aidm.dm.guard_turn import hero_terms
from aidm.dm.guard_types import Violation, ViolationKind
from aidm.dm.sentence_chunker import split_sentences
from aidm.models.campaign_state import RegionResolution
from aidm.models.dm_tiers import AttitudeBand
from aidm.models.state import GameState
from aidm.rules.progression import boss_npc
from aidm.rules.social import public_npc_view


def allies(state: GameState, lex: GuardLexicon) -> dict[str, str]:
    campaign = state.campaign
    names: set[str] = set()
    if campaign is not None:
        for act in campaign.plan.acts:
            npc = boss_npc(state, act.region)
            won = campaign.resolved.get(act.region.id) is RegionResolution.ALLIANCE
            if won and npc is not None and not npc.dead and not npc.hostile:
                names.add(npc.name)
    for npc in state.world.npcs.values():
        if not npc.dead and public_npc_view(npc).attitude is AttitudeBand.ALLY:
            names.add(npc.name)
    return hero_terms(names, lex)


@dataclass(frozen=True)
class TaleEnds:
    began: str
    ended: str
    places: tuple[str, ...]  # every place name, longest first


def tale_ends(state: GameState, began: str, ended: str) -> TaleEnds:
    names = {n for n in state.world.node_names.values() if n}
    if state.campaign is not None:
        names |= {n.name for n in state.campaign.plan.all_nodes()}
    return TaleEnds(began, ended, tuple(sorted(names, key=len, reverse=True)))


_PLACE_REACH = 40  # characters between the begin/end word and "in/at <place>"


def _named_after(sentence: str, words: frozenset[str], ends: TaleEnds) -> list[str]:
    if not words or not ends.places:
        return []
    verbs = "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True))
    places = "|".join(re.escape(p) for p in ends.places)
    pattern = rf"\b(?:{verbs})\b[^.;]{{0,{_PLACE_REACH}}}?\b(?:in|at)\s+(?:the\s+)?({places})"
    return [m.group(1) for m in re.finditer(pattern, sentence, re.IGNORECASE)]


def _same(a: str, b: str) -> bool:
    def norm(s: str) -> str:
        return re.sub(r"^the\s+", "", s.strip().casefold())

    return norm(a) == norm(b)


def wrong_ends(text: str, ends: TaleEnds, lex: GuardLexicon) -> list[Violation]:
    if not ends.began or not ends.ended:
        return []
    found: list[Violation] = []
    told = f"the tale began at {ends.began} and ended at {ends.ended}"
    for sentence in split_sentences(plain(text)):
        circle = find_phrases(sentence, lex.full_circle_claims)
        if circle and not _same(ends.began, ends.ended):
            found.append(Violation(ViolationKind.EPILOGUE_PLACE, circle[0].group(0), told))
        for place in _named_after(sentence, lex.began_words, ends):
            if not _same(place, ends.began):
                found.append(Violation(ViolationKind.EPILOGUE_PLACE, place, told))
        for place in _named_after(sentence, lex.ended_words, ends):
            if not _same(place, ends.ended):
                found.append(Violation(ViolationKind.EPILOGUE_PLACE, place, told))
    return found


def _unskipped(sentence: str, lex: GuardLexicon) -> str:
    out = sentence
    for m in find_phrases(sentence, lex.ally_defeat_skips):
        out = out[: m.start()] + " " * (m.end() - m.start()) + out[m.end() :]
    return out


def ally_defeated(text: str, terms: dict[str, str], lex: GuardLexicon) -> list[Violation]:
    if not terms:
        return []
    words = lex.model_copy(
        update={"death_claims": lex.ally_defeat_claims, "death_soft_claims": frozenset[str]()}
    )
    found: list[Violation] = []
    for sentence in split_sentences(plain(text)):
        kept = _unskipped(sentence, lex)
        for v in living_declared_dead(kept, tokenize(kept), terms, words):
            name = terms.get(v.span.casefold(), v.span)
            detail = f"{name} sided with the party and lives: never tell them defeated or laid low"
            found.append(Violation(ViolationKind.ALLY_DEFEATED, v.span, detail))
    return found
