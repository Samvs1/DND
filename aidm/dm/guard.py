"""THE prose guard (SPEC 2.2 closed world, 6.1 step 4, 6.5): every prose output passes here.

`check_prose(text, state, *, events, scene)` checks each sentence against the entity registry
and the current scene (`aidm.dm.guard_scene`):
- unknown person-like names, near misses of party names (`aidm.dm.guard_names.unknown_names`);
- wrong class or name for a party member (`wrong_identity`);
- absent NPCs acting or named in an empty scene, invented crowds, present people erased
  (`absent_people`, `crowds`, `erased_people`);
- dead creatures acting, intact items described as destroyed, unlisted doors, passages, levers,
  chests and traps (`aidm.dm.guard_world`);
- any NPC's UNREVEALED secret stated in prose (`aidm.dm.guard_secrets`, M4.7): a reveal is a
  `reveal_secret` tool call validated by the engine, never prose;
- a living creature, NPC or party member declared dead, by name (`aidm.dm.guard_alive`, M4.8)
  or by a pronoun resolved to the creatures named before it (`aidm.dm.guard_pronoun`, QA-03);
- gold or items handed over in prose when no event granted any (`aidm.dm.guard_rewards`, M4.8);
- arrival at another map node without travel, and an invented stranger walking in
  (`aidm.dm.guard_claims`, QA-10); with `prose_checker(..., voice_next=name)`, spoken words or
  that NPC's reply in the narration told right before their own voice (`spoken_for`, M20.7);
- a lock opened in prose when no `FeatureUnlocked` event opened it (`opened_locks`, M27.5);
- M29.9c: a foe's attempt or near miss with no attack, a saved spell told as a hit, a fled or
  standing foe told fallen (`aidm.dm.guard_blows`), a hand-over told refused, a quest told done,
  failed or undone against the events, an NPC told joining the party (`aidm.dm.guard_quests`).
- M30.1: an action the engine ruled impossible told as working (`aidm.dm.guard_impossible`).
- M30.2b: a spell told cast when the events cast no such spell (`aidm.dm.guard_cast`).
Vocabulary is data (data/bg3/guard_lexicon.json); matching uses word boundaries and negation
windows, so "unbroken" and "no hidden door" are not flagged.

`guarded_narration` runs the flow for any model prose (narration, NPC speech `aidm.dm.npc_voice`):
guard every sentence, ONE regeneration with a correction and the offending names scrubbed
from the context, then the safe template (`aidm.dm.guard_flow.GuardedSentences`).

Public API: `SCRUB_TOKEN`, `check_prose`, `prose_checker(state, events=(), *, voice_next=None)
-> ProseCheck`,
`scrub_messages(messages, terms)`, `retry_messages(messages, report, shown)`,
`guarded_narration(llm, messages, check, fallback_lines, *, role, max_tokens, player_text,
max_sentences, closing, record) -> GuardedSentences` (M31.1c V20: an ending passes no
`closing` filler and its engine-written `record`).
"""

import dataclasses
import re
from collections.abc import Sequence

from aidm.dm.guard_alive import downed_rising, living_declared_dead, unhurt_declared_down
from aidm.dm.guard_blows import fight_truth
from aidm.dm.guard_cast import untold_cast
from aidm.dm.guard_claims import false_travel, invented_strangers, offer_blows, spoken_for
from aidm.dm.guard_flow import MAX_SENTENCES, GuardedSentences
from aidm.dm.guard_goods import claimed_items, unlit_light, unmade_handover, unpaid_coin
from aidm.dm.guard_impossible import told_possible
from aidm.dm.guard_leaks import instructions, placeholders
from aidm.dm.guard_light import light_state, short_travel, unmade_pickup
from aidm.dm.guard_names import absent_people, crowds, erased_people, unknown_names, wrong_identity
from aidm.dm.guard_party import (
    hurt_told_whole,
    identifiers,
    told_absent,
    wrong_count,
    wrong_race,
)
from aidm.dm.guard_pronoun import PronounContext, pronoun_declared_dead
from aidm.dm.guard_quests import denied_outcome, joined_party, refused_handover, unmade_outcome
from aidm.dm.guard_rewards import unearned_rewards
from aidm.dm.guard_scene import GuardScene, guard_scene
from aidm.dm.guard_secrets import leaked_secrets
from aidm.dm.guard_text import Token, plain, tokenize
from aidm.dm.guard_truth import (
    dead_alive,
    pronoun_down,
    unhurt_wounded,
    unresolved_blows,
    wrong_weapon,
)
from aidm.dm.guard_turn import TurnTruth
from aidm.dm.guard_types import GuardReport, ProseCheck, Violation
from aidm.dm.guard_world import dead_acting, destroyed_items, opened_locks, unlisted_features
from aidm.dm.llm_backend import Message
from aidm.dm.llm_client import LlmClient, TextStream
from aidm.dm.llm_types import LlmRole
from aidm.dm.narration_templates import CLOSING_LINE
from aidm.dm.sentence_chunker import split_sentences
from aidm.models.events import AnyEvent
from aidm.models.state import GameState

SCRUB_TOKEN = "[unlisted]"
CONTINUE_NOTE = (
    "Continue the narration right after that text with what happens NEXT; do not repeat, "
    "retell or rephrase any of it."
)


def _sentence_violations(
    sentence: str, scene: GuardScene, context: PronounContext
) -> list[Violation]:
    tokens = tokenize(sentence)
    return [
        *unknown_names(tokens, scene),
        *wrong_identity(sentence, scene),
        *absent_people(sentence, tokens, scene),
        *crowds(sentence, tokens, scene),
        *erased_people(sentence, scene),
        *dead_acting(sentence, scene),
        *destroyed_items(sentence, tokens, scene),
        *unlisted_features(sentence, tokens, scene),
        *leaked_secrets(sentence, scene.secrets),
        *living_declared_dead(sentence, tokens, scene.living_terms, scene.lexicon),
        *unhurt_declared_down(sentence, tokens, scene.standing_terms, scene.lexicon),
        *downed_rising(sentence, tokens, scene.downed_terms, scene.lexicon),
        *pronoun_declared_dead(sentence, tokens, scene, context),
        *unearned_rewards(sentence, scene.rewarded, scene.lexicon, scene.party),
        *false_travel(sentence, scene),
        *invented_strangers(sentence, scene),
        *offer_blows(sentence, scene),
        *spoken_for(sentence, scene),
        *opened_locks(sentence, tokens, scene),
        *_honest(sentence, tokens, scene, context),
    ]


def _honest(
    sentence: str, tokens: list[Token], scene: GuardScene, context: PronounContext
) -> list[Violation]:
    """M29.5c: nothing the engine did not resolve is told as done, and no machinery leaks."""
    return [
        *placeholders(sentence),
        *instructions(sentence, scene.lexicon),
        *unresolved_blows(sentence, tokens, scene),
        *wrong_weapon(sentence, scene),
        *unhurt_wounded(sentence, tokens, scene),
        *pronoun_down(sentence, tokens, scene, context),
        *dead_alive(sentence, tokens, scene),
        *unpaid_coin(sentence, tokens, scene),
        *claimed_items(sentence, tokens, scene),
        *unmade_handover(sentence, tokens, scene),
        *unlit_light(sentence, tokens, scene),
        *fight_truth(sentence, tokens, scene, context),
        *_round_two(sentence, tokens, scene),
    ]


def _round_two(sentence: str, tokens: list[Token], scene: GuardScene) -> list[Violation]:
    """M29.7b: light state, the place reached, pick-ups, the party's count and health, races,
    present people told absent, engine ids; M29.9c: hand-overs and quest outcomes both ways, an
    NPC told joining the party (`aidm.dm.guard_quests`); M30.1: an impossible action told as
    working (`aidm.dm.guard_impossible`); M30.2b: a spell told cast that was never cast."""
    return [
        *light_state(sentence, tokens, scene),
        *short_travel(sentence, scene),
        *unmade_pickup(sentence, tokens, scene),
        *wrong_count(sentence, scene),
        *hurt_told_whole(sentence, tokens, scene),
        *wrong_race(sentence, scene),
        *told_absent(sentence, scene),
        *identifiers(sentence, scene),
        *refused_handover(sentence, tokens, scene),
        *unmade_outcome(sentence, tokens, scene),
        *denied_outcome(sentence, tokens, scene),
        *joined_party(sentence, tokens, scene),
        *told_possible(sentence, tokens, scene.turn.impossible, scene.lexicon),
        *untold_cast(sentence, tokens, scene.turn.cast, scene.lexicon),
    ]


def check_prose(
    text: str,
    state: GameState,
    *,
    events: Sequence[AnyEvent] = (),
    scene: GuardScene | None = None,
    context: PronounContext | None = None,
) -> GuardReport:
    frozen = scene if scene is not None else guard_scene(state, events)
    told = context if context is not None else PronounContext()
    found: list[Violation] = []
    for sentence in split_sentences(plain(text)):
        found.extend(v for v in _sentence_violations(sentence, frozen, told) if v not in found)
    return GuardReport(tuple(found))


def prose_checker(
    state: GameState,
    events: Sequence[AnyEvent] = (),
    *,
    voice_next: str | None = None,
    actor_id: str | None = None,
    player_text: str | None = None,
    speech: bool = False,
) -> ProseCheck:
    """One checker per narration: it remembers who earlier sentences named (pronouns, QA-03).
    `actor_id` and `player_text` let it know what the player claimed (M29.5c); an NPC's own
    `speech` is not judged by this turn's blows, payments and hand-overs."""
    base = guard_scene(state, events, actor_id=actor_id, player_text=player_text)
    turn = TurnTruth() if speech else base.turn
    scene = dataclasses.replace(base, voice_next=voice_next or "", turn=turn)
    context = PronounContext()
    return lambda text: check_prose(text, state, scene=scene, context=context)


def scrub_messages(messages: Sequence[Message], terms: Sequence[str]) -> list[Message]:
    if not terms:
        return [dict(m) for m in messages]
    ordered = sorted(terms, key=len, reverse=True)
    pattern = re.compile(
        "|".join(rf"(?<![A-Za-z]){re.escape(t)}(?![A-Za-z])" for t in ordered), re.IGNORECASE
    )
    out: list[Message] = []
    for message in messages:
        copy = dict(message)
        content = copy.get("content")
        if message.get("role") != "system" and isinstance(content, str):
            copy["content"] = pattern.sub(SCRUB_TOKEN, plain(content))
        out.append(copy)
    return out


def retry_messages(messages: Sequence[Message], report: GuardReport, shown: str) -> list[Message]:
    out = scrub_messages(messages, report.scrub_terms)
    note = report.correction()
    if shown:
        out.append({"role": "assistant", "content": shown})
        note = f'{note} The players already heard: "{shown}" {CONTINUE_NOTE}'
    out.append({"role": "user", "content": note})
    return out


def guarded_narration(
    llm: LlmClient,
    messages: Sequence[Message],
    check: ProseCheck,
    fallback_lines: Sequence[str],
    *,
    role: LlmRole = LlmRole.QUALITY,
    max_tokens: int = 700,
    player_text: str | None = None,
    max_sentences: int = MAX_SENTENCES,
    closing: Sequence[str] = (CLOSING_LINE,),
    record: Sequence[str] = (),
) -> GuardedSentences:
    base = list(messages)

    def attempt(report: GuardReport | None, shown: str) -> TextStream:
        sent = base if report is None else retry_messages(base, report, shown)
        return llm.stream_text(sent, role, max_tokens=max_tokens, player_text=player_text)

    return GuardedSentences(
        attempt, check, fallback_lines, max_sentences=max_sentences, closing=closing, record=record
    )
