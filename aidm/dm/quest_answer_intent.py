"""Typed answers to a waiting quest offer (M31.1a V8, round 4: "Sure, we'll take the job, Merre"
and "Yes, we will go up to the sluice gate ..." did not accept the task; only `answer yes` did).

While a quest offer waits from a person standing here (`World.quest_ask`, condition
`quest_ask_here`), the `quest_accept` and `quest_decline` phrase rows of
data/bg3/intent_phrases.json read a plain yes or acceptance ("yes ...", "sure ...", "we'll take
the job", "count us in") or a plain no or refusal ("no, ...", "not now", "we'll pass", "we
decline") and the resolver returns a `QuestAnswerIntent` the session answers through the SAME
path as the card's buttons (`session.quest_people.answer_quest`).

Public API: `QuestAnswerIntent(actor_id, quest_id, accept)`, `RESOLVERS` (`quest_answer`).
"""

from dataclasses import dataclass

from aidm.dm.intent_match import Found, Resolver


@dataclass(frozen=True)
class QuestAnswerIntent:
    actor_id: str
    quest_id: str
    accept: bool


def quest_answer(found: Found) -> QuestAnswerIntent | None:
    ask = found.state.world.quest_ask
    if ask is None:
        return None
    return QuestAnswerIntent(found.actor_id, ask.quest_id, found.params.get("accept") is True)


RESOLVERS: dict[str, Resolver] = {"quest_answer": quest_answer}
