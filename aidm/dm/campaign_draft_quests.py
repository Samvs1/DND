"""The quest parts of the campaign draft and how they join the plan (M23.6, GOAL_QUESTS).

The model writes side quest steps, a Peace and an optional Cunning route per act and a finale,
all by names; `with_quests` turns them into plan parts on top of the assembled base plan
(`aidm.dm.campaign_draft.assemble_plan`). Repair over reject (M16.1), each repair a note:
- a side quest whose giver lives in another act's region moves to that act; an act with more
  than `MAX_SIDE_QUESTS` keeps its own quests first, the rest are dropped (a secret revealed by a
  dropped quest then reveals at a friendly attitude);
- steps resolve against the quest's act (`aidm.dm.campaign_steps`): unresolvable -> `free`;
- a route hint NPC who does not live in the act region -> no hint NPC (found by doing a step);
- a Cunning route without an effect -> `boss_alone`; a route without steps is dropped;
- a Peace route on a boss without an ally path gives the boss one (the route's title);
- no finale, or not two endings -> no finale (the campaign ends as before M23).
A quest without steps keeps none (`rules.quest_plan` derives them, as for old plans). If the
quest layer still fails validation, the base plan is returned with a note: quests never sink a
campaign.

Public API: `RouteDraft`, `FinaleEndingDraft`, `FinaleDraft` (schema parts), `QuestDrafts`,
`with_quests(plan, drafts, notes) -> CampaignPlan`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import Field, ValidationError, field_validator

from aidm.dm.campaign_draft_base import Draft, slug_id
from aidm.dm.campaign_steps import (
    ActNames,
    StepDraft,
    fix_delivers,
    repair_note,
    resolve_steps,
)
from aidm.models.campaign import Act, CampaignPlan, QuestPlan, RevealCondition, RevealKind
from aidm.models.dm_tiers import AttitudeBand
from aidm.models.problem import Problem
from aidm.models.quests import (
    FORCE_ROUTE_ID,
    FinaleOption,
    FinalePlan,
    MainQuestPlan,
    QuestStep,
    RouteEffect,
    RouteKind,
    RoutePlan,
)
from aidm.rules.plan_ids import boss_npc_id, main_quest_id
from aidm.rules.quest_check import MAX_SIDE_QUESTS
from aidm.rules.quest_contract import fit_side_quest

MAX_ROUTE_ID = 40
DEFAULT_EFFECT: RouteEffect = "boss_alone"
_EFFECTS = ("boss_alone", "boss_surprised")


class RouteDraft(Draft):
    """Another way to settle the act besides fighting: 1-4 steps."""

    title: str = Field(min_length=1, max_length=60)
    hint_npc: str | None = Field(default=None, max_length=40, description="an NPC who knows it")
    steps: list[StepDraft] = Field(default_factory=list[StepDraft], max_length=4)
    effect: RouteEffect | None = Field(default=None, description="cunning only")

    @field_validator("effect", mode="before")
    @classmethod
    def _known_effect(cls, value: Any) -> Any:
        return value if value in _EFFECTS else None


class FinaleEndingDraft(Draft):
    title: str = Field(min_length=1, max_length=60)
    text: str = Field(min_length=1, max_length=200)


class FinaleDraft(Draft):
    """The last choice of the story: one question, two different endings."""

    question: str = Field(min_length=1, max_length=200)
    endings: list[FinaleEndingDraft] = Field(default_factory=list[FinaleEndingDraft], max_length=2)


@dataclass(frozen=True)
class QuestDrafts:
    """The quest parts of one draft: steps per plan quest (plan order), routes per act."""

    side_steps: tuple[list[StepDraft], ...]
    peace: tuple[RouteDraft | None, ...]
    cunning: tuple[RouteDraft | None, ...]
    finale: FinaleDraft | None


def _home_acts(plan: CampaignPlan) -> dict[str, int]:
    acts = {n.id: a.index for a in plan.acts for n in a.region.nodes()}
    return {npc.id: acts[npc.home_node] for npc in plan.npcs if npc.home_node in acts}


def _placed(
    plan: CampaignPlan, drafts: QuestDrafts, notes: list[Problem]
) -> list[tuple[QuestPlan, list[StepDraft]]]:
    """Side quests moved to their giver's act, at most `MAX_SIDE_QUESTS` per act."""
    homes = _home_acts(plan)
    moved: list[tuple[bool, QuestPlan, list[StepDraft]]] = []
    for quest, steps in zip(plan.quests, drafts.side_steps, strict=True):
        act = homes.get(quest.giver_npc_id, quest.act)
        if act != quest.act:
            notes.append(repair_note(quest.id, f"the giver lives in act {act}; moved there"))
        moved.append((act != quest.act, quest.model_copy(update={"act": act}), steps))
    kept: list[tuple[QuestPlan, list[StepDraft]]] = []
    for _, quest, steps in sorted(moved, key=lambda m: m[0]):
        if sum(1 for q, _ in kept if q.act == quest.act) >= MAX_SIDE_QUESTS:
            msg = f"act {quest.act} already has {MAX_SIDE_QUESTS} side quests; dropped"
            notes.append(repair_note(quest.id, msg))
            continue
        kept.append((quest, steps))
    order = [q.id for q in plan.quests]
    return sorted(kept, key=lambda k: order.index(k[0].id))


def _stale(reveal: RevealCondition, kept: list[QuestPlan]) -> bool:
    """A reveal by a quest (or a quest's reward item) that is no longer in the plan."""
    if reveal.kind is RevealKind.QUEST_COMPLETED:
        return reveal.quest_id not in {q.id for q in kept}
    if reveal.kind is RevealKind.ITEM_SHOWN:
        return reveal.item not in {q.reward_item for q in kept}
    return False


def _without_quests(plan: CampaignPlan, kept: list[QuestPlan]) -> CampaignPlan:
    """`plan` with only the `kept` quests; secrets revealed by a dropped quest (or its reward
    item) reveal at a friendly attitude instead."""
    friendly = RevealCondition(kind=RevealKind.ATTITUDE, band=AttitudeBand.FRIENDLY)
    npcs = []
    for npc in plan.npcs:
        secrets = tuple(
            s.model_copy(update={"reveal": friendly}) if _stale(s.reveal, kept) else s
            for s in npc.secrets
        )
        npcs.append(npc.model_copy(update={"secrets": secrets}))
    return plan.model_copy(update={"npcs": tuple(npcs), "quests": tuple(kept)})


def _side_quests(
    plan: CampaignPlan, placed: list[tuple[QuestPlan, list[StepDraft]]], notes: list[Problem]
) -> tuple[QuestPlan, ...]:
    out: list[QuestPlan] = []
    for quest, drafts in placed:
        if not drafts:
            out.append(quest)
            continue
        names = ActNames.build(plan, plan.acts[quest.act - 1])
        steps = resolve_steps(names, quest.id, drafts, notes)
        (fixed,) = fix_delivers(names, quest.id, [steps], notes)
        out.append(quest.model_copy(update={"steps": tuple(fixed)}))
    return tuple(out)


def _contract_quests(
    plan: CampaignPlan, quests: tuple[QuestPlan, ...], notes: list[Problem]
) -> tuple[CampaignPlan, tuple[QuestPlan, ...]]:
    """M43.4 C1: a quest aimed at its own giver is repaired or left out (secrets it revealed
    reveal at a friendly attitude, as for any dropped quest)."""
    fitted = [fit_side_quest(q, notes) for q in quests]
    kept = tuple(q for q in fitted if q is not None)
    return (_without_quests(plan, list(kept)) if len(kept) < len(quests) else plan), kept


def _route_id(title: str, kind: RouteKind, taken: set[str]) -> str:
    base = slug_id(title, ())[:MAX_ROUTE_ID].strip("-") or kind.value
    if base in taken:
        base = f"{base[: MAX_ROUTE_ID - 9].strip('-')}-{kind.value}"
    taken.add(base)
    return base


def _hint(names: ActNames, owner: str, draft: RouteDraft, notes: list[Problem]) -> str | None:
    if not draft.hint_npc:
        return None
    npc = names.npc(draft.hint_npc)
    if npc is None or npc == boss_npc_id(names.act.region):
        msg = f"hint npc {draft.hint_npc!r} does not live in act {names.act.index}; none"
        notes.append(repair_note(owner, msg))
        return None
    return npc


def _route(
    names: ActNames, kind: RouteKind, draft: RouteDraft, taken: set[str], notes: list[Problem]
) -> tuple[RoutePlan, list[QuestStep]] | None:
    owner = f"{main_quest_id(names.act.region)}/{kind.value}"
    steps = resolve_steps(names, owner, draft.steps, notes)
    if not steps:
        notes.append(repair_note(owner, "the route has no steps; dropped"))
        return None
    effect = draft.effect if kind is RouteKind.CUNNING else None
    if kind is RouteKind.CUNNING and effect is None:
        effect = DEFAULT_EFFECT
        notes.append(repair_note(owner, f"no effect given; {DEFAULT_EFFECT}"))
    route = RoutePlan(
        id=_route_id(draft.title, kind, taken),
        kind=kind,
        title=draft.title,
        hint_npc_id=_hint(names, owner, draft, notes),
        steps=tuple(steps),
        effect=effect,
    )
    return route, steps


def _act(plan: CampaignPlan, act: Act, drafts: QuestDrafts, notes: list[Problem]) -> Act:
    names = ActNames.build(plan, act)
    pairs = [(RouteKind.PEACE, drafts.peace[act.index - 1])]
    pairs.append((RouteKind.CUNNING, drafts.cunning[act.index - 1]))
    taken = {FORCE_ROUTE_ID}
    built = [_route(names, k, d, taken, notes) for k, d in pairs if d is not None]
    routes = [r for r, _ in (b for b in built if b is not None)]
    if not routes:
        return act
    owner = main_quest_id(act.region)
    fixed = fix_delivers(names, owner, [list(r.steps) for r in routes], notes)
    routes = [r.model_copy(update={"steps": tuple(s)}) for r, s in zip(routes, fixed, strict=True)]
    region, boss = act.region, act.region.boss
    if boss.ally_path is None and any(r.kind is RouteKind.PEACE for r in routes):
        peace = next(r for r in routes if r.kind is RouteKind.PEACE)
        notes.append(repair_note(owner, "the boss had no ally path; the Peace route gives one"))
        region = region.model_copy(
            update={"boss": boss.model_copy(update={"ally_path": peace.title})}
        )
    return act.model_copy(update={"main": MainQuestPlan(routes=tuple(routes)), "region": region})


def _finale(draft: FinaleDraft | None, notes: list[Problem]) -> FinalePlan | None:
    if draft is None or len(draft.endings) != 2:
        notes.append(repair_note("finale", "no finale with two endings; the story ends as before"))
        return None
    taken: set[str] = set()
    options: list[FinaleOption] = []
    for ending in draft.endings:
        option_id = slug_id(ending.title, taken)[:MAX_ROUTE_ID].strip("-") or "ending"
        taken.add(option_id)
        options.append(FinaleOption(id=option_id, title=ending.title, text=ending.text))
    return FinalePlan(question=draft.question, options=(options[0], options[1]))


def with_quests(plan: CampaignPlan, drafts: QuestDrafts, notes: list[Problem]) -> CampaignPlan:
    """`plan` (assembled without quest steps) with the drafted quests, routes and finale."""
    placed = _placed(plan, drafts, notes)
    mid = _without_quests(plan, [q for q, _ in placed])
    try:
        mid, quests = _contract_quests(mid, _side_quests(mid, placed, notes), notes)
        update = {
            "quests": quests,
            "acts": tuple(_act(mid, a, drafts, notes) for a in mid.acts),
            "finale": _finale(drafts.finale, notes),
        }
        return CampaignPlan.model_validate(mid.model_copy(update=update).model_dump())
    except ValidationError as exc:
        why = "; ".join(e["msg"] for e in exc.errors()[:3])
        notes.append(repair_note("quests", f"the quest layer did not validate ({why})"))
    try:
        return CampaignPlan.model_validate(mid.model_dump())
    except ValidationError:
        return plan
