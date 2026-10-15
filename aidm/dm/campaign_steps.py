"""Quest step drafts and their resolution against one act (M23.6, GOAL "Plan generator and checks").

The model writes a step by names (places, NPCs, items); code resolves them against the act that
owns the quest: the act region's places, the NPCs living there and its boss. Repair over reject:
a step whose reference does not resolve inside that act becomes a `free` step with the step's own
text (the storyteller judges it, M23.5), except an `obtain` whose place does not resolve, which is
placed at the act's first spoke. Every repair is a note (`Problem(code="quest_repair")`), so it
shows in the generator log. `deliver` steps whose item is never obtained by the same quest get an
`obtain` inserted before them (at the first spoke) while the quest has room, else become `free`.

Public API:
- `StepDraft` (the schema part), `ActNames.build(plan, act)` (what an act's steps may name).
- `resolve_steps(names, owner, drafts, notes) -> list[QuestStep]`.
- `fix_delivers(names, owner, routes, notes) -> list[list[QuestStep]]`: the deliver repair over
  the step lists of ONE quest (a side quest: one list; a main quest: its routes).
- `repair_note(owner, message) -> Problem`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import Field, ValidationError, field_validator

from aidm.dm.campaign_draft_base import Draft, name_key, resolve_name
from aidm.models.campaign import Act, CampaignPlan
from aidm.models.dm_tiers import AttitudeBand
from aidm.models.problem import Problem
from aidm.models.quests import MAX_STEP_COUNT, MAX_STEPS, QuestStep, StepKind
from aidm.rules.plan_ids import boss_npc_id
from aidm.rules.quest_check import learnable_words
from aidm.rules.quest_items import same_item
from aidm.rules.quest_plan import short_text
from aidm.rules.secrets import fact_words, item_key

MAX_STEP_PLACES = 3
_TARGET_BANDS = (AttitudeBand.FRIENDLY, AttitudeBand.ALLY)


class StepDraft(Draft):
    """One quest step: `kind` decides which of places / npc / item / tag it needs."""

    kind: StepKind
    text: str = Field(min_length=1, max_length=100, description="what the players read")
    places: list[str] = Field(default_factory=list[str], max_length=MAX_STEP_PLACES)
    npc: str | None = Field(default=None, max_length=40)
    item: str | None = Field(default=None, max_length=40)
    count: int = Field(default=1, description="obtain only: copies to gather, 1-5")
    hidden: bool = Field(default=False, description="obtain only: must be searched for")
    band: AttitudeBand | None = Field(default=None, description="win_over: friendly or ally")
    tag: str | None = Field(default=None, max_length=24, description="learn: one word")

    @field_validator("kind", mode="before")
    @classmethod
    def _known_kind(cls, value: Any) -> Any:
        known = {k.value for k in StepKind}
        return value if not isinstance(value, str) or value in known else StepKind.FREE.value

    @field_validator("band", mode="before")
    @classmethod
    def _known_band(cls, value: Any) -> Any:
        known = {b.value for b in AttitudeBand}
        return value if not isinstance(value, str) or value in known else None


@dataclass(frozen=True)
class ActNames:
    """What the steps of one act may name: name key -> id indexes and the learnable words."""

    act: Act
    places: dict[str, str]
    npcs: dict[str, str]
    words: frozenset[str]

    @classmethod
    def build(cls, plan: CampaignPlan, act: Act) -> ActNames:
        region = act.region
        places = {name_key(n.name): n.id for n in region.nodes()}
        homes = set(places.values())
        npcs = {name_key(n.name): n.id for n in plan.npcs if n.home_node in homes}
        npcs.setdefault(name_key(region.boss.name), boss_npc_id(region))
        return cls(act, places, npcs, learnable_words(plan, act))

    @property
    def first_spoke(self) -> str:
        return self.act.region.spokes[0].id

    def place(self, written: str) -> str | None:
        return resolve_name(self.places, written)

    def npc(self, written: str | None) -> str | None:
        return resolve_name(self.npcs, written) if written else None

    def place_name(self, node_id: str) -> str:
        return next((n.name for n in self.act.region.nodes() if n.id == node_id), node_id)


def repair_note(owner: str, message: str) -> Problem:
    return Problem(code="quest_repair", message=f"{owner}: {message}", subject=owner)


class _Unresolved(Exception):
    """A step reference that does not resolve inside the act (the step becomes `free`)."""


type _Resolved = tuple[dict[str, Any], str | None]


def _places(names: ActNames, draft: StepDraft) -> list[str]:
    found = [names.place(p) for p in draft.places]
    return list(dict.fromkeys(n for n in found if n is not None))


def _npc(names: ActNames, draft: StepDraft) -> str:
    npc = names.npc(draft.npc)
    if npc is None:
        raise _Unresolved(f"{draft.npc!r} is no NPC of act {names.act.index} nor its boss")
    return npc


def _visit(names: ActNames, draft: StepDraft) -> _Resolved:
    nodes = _places(names, draft)
    if not nodes:
        raise _Unresolved(f"{draft.places} names no place of act {names.act.index}")
    dropped = len(nodes) < len(draft.places)
    return {"nodes": tuple(nodes)}, "dropped places outside the act" if dropped else None


def _clear(names: ActNames, draft: StepDraft) -> _Resolved:
    nodes = _places(names, draft)
    if not nodes:
        raise _Unresolved(f"{draft.places} names no place of act {names.act.index}")
    if nodes[0] == names.act.region.arrival.id:
        raise _Unresolved("the arrival is safe, there is nothing to clear")
    return {"nodes": (nodes[0],)}, None


def _item(draft: StepDraft) -> str:
    if not draft.item or not draft.item.strip():
        raise _Unresolved("it names no item")
    return draft.item.strip()


def _obtain(names: ActNames, draft: StepDraft) -> _Resolved:
    count = min(max(draft.count, 1), MAX_STEP_COUNT)
    nodes, note = _places(names, draft)[:count], None
    if not nodes:
        nodes = [names.first_spoke]
        note = f"the item is placed at {names.place_name(names.first_spoke)}"
    fields = {"item": _item(draft), "nodes": tuple(nodes), "count": count}
    return fields | {"hidden": draft.hidden}, note


def _deliver(names: ActNames, draft: StepDraft) -> _Resolved:
    return {"item": _item(draft), "npc": _npc(names, draft)}, None


def _npc_only(names: ActNames, draft: StepDraft) -> _Resolved:
    return {"npc": _npc(names, draft)}, None


def _win_over(names: ActNames, draft: StepDraft) -> _Resolved:
    band = draft.band if draft.band in _TARGET_BANDS else AttitudeBand.FRIENDLY
    note = None if band is draft.band else "the attitude aimed at became friendly"
    return {"npc": _npc(names, draft), "band": band}, note


def _learn(names: ActNames, draft: StepDraft) -> _Resolved:
    tag = (draft.tag or "").strip().lower()
    words = fact_words(tag)
    if not words or not words <= names.words:
        raise _Unresolved(f"tag {draft.tag!r} can never be learned in act {names.act.index}")
    return {"tag": tag}, None


def _free(names: ActNames, draft: StepDraft) -> _Resolved:
    return {}, None


_RESOLVERS: dict[StepKind, Callable[[ActNames, StepDraft], _Resolved]] = {
    StepKind.VISIT: _visit,
    StepKind.CLEAR: _clear,
    StepKind.DEFEAT: _npc_only,
    StepKind.OBTAIN: _obtain,
    StepKind.DELIVER: _deliver,
    StepKind.MEET: _npc_only,
    StepKind.WIN_OVER: _win_over,
    StepKind.LEARN: _learn,
    StepKind.FREE: _free,
}


def _resolve(names: ActNames, draft: StepDraft) -> tuple[QuestStep, str | None]:
    try:
        fields, note = _RESOLVERS[draft.kind](names, draft)
        return QuestStep(kind=draft.kind, text=draft.text, **fields), note
    except _Unresolved as why:
        reason = str(why)
    except ValidationError as exc:
        reason = exc.errors()[0]["msg"]
    free = QuestStep(kind=StepKind.FREE, text=draft.text)
    return free, f"became a free step ({reason})"


def resolve_steps(
    names: ActNames, owner: str, drafts: list[StepDraft], notes: list[Problem]
) -> list[QuestStep]:
    out: list[QuestStep] = []
    for n, draft in enumerate(drafts[:MAX_STEPS], start=1):
        step, note = _resolve(names, draft)
        if note is not None:
            notes.append(repair_note(owner, f"step {n} {draft.text!r} {note}"))
        out.append(step)
    return out


def _obtained(routes: list[list[QuestStep]], item: str) -> str | None:
    """The obtained item name matching `item` (exact key first, then a lookalike)."""
    names = [s.item for steps in routes for s in steps if s.kind is StepKind.OBTAIN and s.item]
    exact = next((n for n in names if item_key(n) == item_key(item)), None)
    return exact or next((n for n in names if same_item(n, item)), None)


def _fix_deliver(
    names: ActNames, owner: str, routes: list[list[QuestStep]], steps: list[QuestStep], i: int
) -> list[Problem]:
    step = steps[i]
    found = _obtained(routes, step.item or "")
    if found is not None:
        if found != step.item:
            steps[i] = step.model_copy(update={"item": found})
        return []
    if len(steps) < MAX_STEPS:
        text = short_text(f"Find the {step.item}")
        get = QuestStep(kind=StepKind.OBTAIN, text=text, item=step.item, nodes=(names.first_spoke,))
        steps.insert(i, get)
        where = names.place_name(names.first_spoke)
        return [repair_note(owner, f"{step.item!r} was never obtained; it now lies at {where}")]
    steps[i] = QuestStep(kind=StepKind.FREE, text=step.text)
    return [repair_note(owner, f"{step.item!r} was never obtained; the step became free")]


def fix_delivers(
    names: ActNames, owner: str, routes: list[list[QuestStep]], notes: list[Problem]
) -> list[list[QuestStep]]:
    out = [list(steps) for steps in routes]
    for steps in out:
        i = 0
        while i < len(steps):
            if steps[i].kind is StepKind.DELIVER:
                notes += _fix_deliver(names, owner, out, steps, i)
                i += 2 if steps[i].kind is StepKind.OBTAIN else 1
            else:
                i += 1
    return out
