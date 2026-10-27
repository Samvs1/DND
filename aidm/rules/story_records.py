"""Story records are past records: the ONE rule for showing them again (M40.4, SPEC 6.4). Pure.

Round 7 showed model-written text stored once and later shown as if present ("two stirges
hover; no blow struck" beside two dead stirges, "has not yet accepted" beside "accepted").
Every reader of a stored story record (the prompts through `aidm.dm.context`, the players'
journal `aidm.session.views`, the epilogue `aidm.dm.epilogue_facts`, the scene view's place
description `aidm.rules.scene`) asks `shown_when(state, record)`:
- None: leave it out. A FACT or a place DESCRIPTION is a present-tense note, so it is left out
  once a later engine event changed a thing it names (`superseded`: a foe died, went down or
  left, a quest or its offer changed state, an item changed holder; `aidm.rules.story_keys`
  marks them in `World.changed`). The live state (manifest, quests, party) tells the present.
- else the date to show it with: "Earlier this scene" / "Earlier, scene N" / "Earlier" (no
  stamp). A SUMMARY or a NARRATION line is history by nature: it always stays, dated as past
  (the prompts say that only the engine's lines are the present).
A record names a thing by its entity ids or by a registered name its text spells out
(`aidm.rules.story_names`; a name the change ledger holds still counts after the thing left
the state); a record with an offer word (`aidm.rules.story_claims.ClaimKind.OFFER`) also names
the quests its giver gives. A record without a stamp counts as made before every change.

Public API: `RecordStore`, `StoryRecord(store, text, ids, made)`, `when_label(state, scene)`,
`superseded(state, record) -> bool`, `shown_when(state, record) -> str | None`,
`fact_record(fact)`, `summary_record(summary)`, `live_facts(state) -> list[Fact]`,
`dated_facts(state, facts)`, `narration_records(state) -> list[StoryRecord]`,
`description_shown(state, node_id) -> str`.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum

from aidm.models.memory import SceneSummary
from aidm.models.state import GameState
from aidm.models.story import StoryStamp
from aidm.models.world import Fact
from aidm.rules.story_claims import ClaimKind, claim_kinds
from aidm.rules.story_keys import CARRIED, STATUS, story_name
from aidm.rules.story_names import mentions, text_slug

_STATUS_NAME = f"{STATUS}:name:"
_NAMED = (_STATUS_NAME, f"{STATUS}:{CARRIED}")


class RecordStore(StrEnum):
    FACT = "fact"
    SUMMARY = "summary"
    NARRATION = "narration"
    DESCRIPTION = "description"


HISTORY = frozenset({RecordStore.SUMMARY, RecordStore.NARRATION})


@dataclass(frozen=True)
class StoryRecord:
    store: RecordStore
    text: str
    ids: tuple[str, ...] = ()
    made: StoryStamp | None = None


def when_label(state: GameState, scene: int | None) -> str:
    if scene is None:
        return "Earlier"
    if scene == state.world.scene_index:
        return "Earlier this scene"
    return f"Earlier, scene {scene}"


def _offer_quests(state: GameState, text: str, ids: Iterable[str]) -> list[str]:
    if ClaimKind.OFFER not in claim_kinds(text):
        return []
    named, slugged, out = set(ids), text_slug(text), list[str]()
    for qid, quest in state.world.quests.items():
        npc = state.world.npcs.get(quest.giver_npc_id or "")
        if npc is not None and (
            npc.id in named or mentions(slugged, story_name(npc.name).removeprefix("name:"))
        ):
            out.append(qid)
    return out


def _changed_since(state: GameState, record: StoryRecord, made: int) -> bool:
    """Whether an engine event after seq `made` changed a thing the record names."""
    changed = state.world.changed
    ids = [*record.ids, *_offer_quests(state, record.text, record.ids)]
    if any(changed.get(f"{STATUS}:{i}", -1) > made for i in ids):
        return True
    # a place description tells the place, not what the heroes carry
    kinds = (_STATUS_NAME,) if record.store is RecordStore.DESCRIPTION else _NAMED
    slugged = ""
    for key, seq in changed.items():
        if seq <= made:
            continue
        kind = next((k for k in kinds if key.startswith(k)), None)
        if kind is None:
            continue
        slugged = slugged or text_slug(record.text)
        if mentions(slugged, key.removeprefix(kind)):
            return True
    return False


def superseded(state: GameState, record: StoryRecord) -> bool:
    """A later engine event changed a thing the record names."""
    made = record.made.seq if record.made is not None else -1
    return _changed_since(state, record, made)


def shown_when(state: GameState, record: StoryRecord) -> str | None:
    """The date to show the record with, or None to leave it out (see the module doc)."""
    if record.store not in HISTORY and superseded(state, record):
        return None
    return when_label(state, record.made.scene if record.made is not None else None)


def fact_record(fact: Fact) -> StoryRecord:
    return StoryRecord(RecordStore.FACT, fact.text, fact.entity_ids, fact.made)


def summary_record(summary: SceneSummary) -> StoryRecord:
    """Dated by the scene it summarises (`scene_index`), not the scene it was written in."""
    seq = summary.made.seq if summary.made is not None else 0
    made = StoryStamp(seq=seq, scene=summary.scene_index)
    return StoryRecord(RecordStore.SUMMARY, summary.text, summary.entity_ids, made)


def live_facts(state: GameState) -> list[Fact]:
    """The ledger facts nothing has superseded, oldest first."""
    return [f for f in state.world.facts if not superseded(state, fact_record(f))]


def dated_facts(state: GameState, facts: Sequence[Fact]) -> list[str]:
    """Each fact still shown, as "<date>: <text>"."""
    out: list[str] = []
    for fact in facts:
        when = shown_when(state, fact_record(fact))
        if when is not None:
            out.append(f"{when}: {fact.text}")
    return out


def narration_records(state: GameState) -> list[StoryRecord]:
    """The narrated turns with their stamps (lined up from the end; older lines unstamped)."""
    memory = state.memory
    if not memory.narration:
        return []
    stamps: list[StoryStamp | None] = [*memory.narration_made[-len(memory.narration) :]]
    stamps = [None] * (len(memory.narration) - len(stamps)) + stamps
    return [
        StoryRecord(RecordStore.NARRATION, text, (), made)
        for text, made in zip(memory.narration, stamps, strict=True)
    ]


def description_shown(state: GameState, node_id: str | None) -> str:
    """The place's established description, or "" once a thing it names has changed."""
    text = state.world.descriptions.get(node_id or "", "")
    if not text or node_id is None:
        return text
    made = state.world.described.get(node_id)
    record = StoryRecord(RecordStore.DESCRIPTION, text, (node_id,), made)
    return text if shown_when(state, record) is not None else ""
