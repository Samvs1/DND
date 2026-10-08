"""The defeat epilogue (M11.1): a short in-fiction ending when the whole party has fallen.

ONE streamed QUALITY call whose only input is `DefeatFacts.lines()` (where it happened, which
heroes are dead, which lie senseless, which foes still stand). Every sentence passes THE guard
(`epilogue.facts_checker`: closed-world names, dead creatures acting, living people declared
dead), then ONE retry, then the deterministic `template_defeat`; a disabled model (no key) or the
FakeLLM therefore always ends in readable text. The text never promises a retry mechanic by name:
the table offers the choices itself.

Public API: `DEFEAT_STYLE`, `DefeatFacts`, `defeat_facts(state)`, `template_defeat(facts)`,
`defeat_messages(facts)`, `begin_defeat(state, llm) -> NarrationStream`,
`defeat_event(stream, facts) -> PartyDefeated`.
"""

from dataclasses import dataclass

from aidm.dm.epilogue import facts_checker
from aidm.dm.guard import guarded_narration
from aidm.dm.llm_backend import Message
from aidm.dm.llm_client import LlmClient
from aidm.dm.llm_types import LlmRole
from aidm.dm.narration_stream import NarrationStream
from aidm.models.defeat import PartyDefeated
from aidm.models.narration import NarrationTone
from aidm.models.state import GameState
from aidm.rules.party_wipe import party_heroes, standing_foes

DEFEAT_MAX_TOKENS = 400
DEFEAT_MAX_SENTENCES = 5
DEFEAT_STYLE = (
    "You write the last lines of a fantasy adventure that ends in defeat: every hero of the party"
    " has fallen. Use ONLY the facts listed by the user. Heroes listed as senseless are NOT dead;"
    " never call them dead. Invent no names, places, rescuers or rewards. 2 to 4 sombre"
    " sentences of prose, past tense, no lists, no game terms, no numbers."
)


@dataclass(frozen=True)
class DefeatFacts:
    place: str
    dead: tuple[str, ...]
    downed: tuple[str, ...]
    foes: tuple[str, ...]

    def lines(self) -> list[str]:
        out = [f"The party fell at {self.place}."]
        out.extend(f"{name} is dead." for name in self.dead)
        out.extend(f"{name} lies senseless on the ground." for name in self.downed)
        out.extend(f"{name} still stands over the fallen." for name in self.foes)
        return out


def _names(names: tuple[str, ...]) -> str:
    if len(names) <= 1:
        return "".join(names)
    return f"{', '.join(names[:-1])} and {names[-1]}"


def defeat_facts(state: GameState) -> DefeatFacts:
    node = state.world.current_node or ""
    place = state.world.node_names.get(node, node.replace("-", " ")) or "the road"
    heroes = party_heroes(state)
    return DefeatFacts(
        place=place,
        dead=tuple(c.name for c in heroes if c.dead),
        downed=tuple(c.name for c in heroes if not c.dead),
        foes=tuple(standing_foes(state)),
    )


def template_defeat(facts: DefeatFacts) -> list[str]:
    lines = [f"At {facts.place}, the last of the party falls."]
    if facts.dead:
        lines.append(f"{_names(facts.dead)} will not rise again.")
    if facts.downed:
        verb = "lies" if len(facts.downed) == 1 else "lie"
        lines.append(f"{_names(facts.downed)} {verb} senseless in the dust.")
    if facts.foes:
        lines.append(f"{_names(facts.foes)} remain masters of the field.")
    lines.append("Darkness closes over the tale.")
    return lines


def defeat_messages(facts: DefeatFacts) -> list[Message]:
    listed = "\n".join(f"- {line}" for line in facts.lines())
    user = f"FACTS (the only things that happened):\n{listed}\n\nWrite the ending now."
    return [{"role": "system", "content": DEFEAT_STYLE}, {"role": "user", "content": user}]


def begin_defeat(state: GameState, llm: LlmClient) -> NarrationStream:
    facts = defeat_facts(state)
    sentences = guarded_narration(
        llm,
        defeat_messages(facts),
        facts_checker(state, facts.lines()),
        template_defeat(facts),
        role=LlmRole.QUALITY,
        max_tokens=DEFEAT_MAX_TOKENS,
        max_sentences=DEFEAT_MAX_SENTENCES,
    )
    return NarrationStream(NarrationTone.EXPLORATION, sentences)


def defeat_event(stream: NarrationStream, facts: DefeatFacts) -> PartyDefeated:
    text = stream.text.strip() or " ".join(template_defeat(facts))
    return PartyDefeated(text=text, source=stream.source.value, place=facts.place)
