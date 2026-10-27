"""Quest contract C1, C2 and C4 where a quest is registered (M43.4). Pure.

One validator for the two doors a generated quest comes through: the campaign install
(`plan_repair.repair_plan`, which both plan producers pass) and the favour tool (`favours`).
Repair when plain, reject only when no repair keeps the quest followable
(docs/next/M43_CONTRACT.md):
- `target_refusal`: C1, why a quest's target cannot be that person (`FRIEND_TARGET`);
- `fit_side_quest`, `fit_quests`: C1 at install; `without_quests`: a plan without the dropped
  quests;
- `fit_steps`: C2 (a repeated step is dropped) and C4 (one count for a find and its hand-over);
- `step_key`: what makes two steps the same step.

Public API: `FRIEND_TARGET`, `target_refusal`, `fit_side_quest(quest, notes)`,
`fit_quests(plan, notes)`, `without_quests(plan, kept)`, `step_key(step)`,
`fit_steps(owner, steps, notes)`.
"""

from aidm.models.campaign import CampaignPlan, NpcPlan, QuestPlan, RevealCondition, RevealKind
from aidm.models.dm_tiers import AttitudeBand
from aidm.models.problem import Problem
from aidm.models.quests import QuestStep, StepKind
from aidm.rules.plan_steps import note
from aidm.rules.quest_items import same_item
from aidm.rules.secrets import item_key

FRIEND_TARGET = "the target is a friend of the party"


def target_refusal(giver: str, npc: str | None, friend: bool) -> str | None:
    """C1: why `npc` cannot be the target of a quest `giver` asks, else None."""
    if npc is not None and npc == giver:
        return "the target is the one who asks"
    if npc is not None and friend:
        return FRIEND_TARGET
    return None


def fit_side_quest(quest: QuestPlan, notes: list[Problem]) -> QuestPlan | None:
    """C1 at install: the quest (a giver target cleared), or None when its defeat step aims at
    the giver (a note says why). A friend is not known at install: `quest_targets.asked_quest`
    turns that step into a meet when the card is asked."""
    giver = quest.giver_npc_id
    for step in quest.steps:
        if step.kind is StepKind.DEFEAT and target_refusal(giver, step.npc, False):
            notes.append(note(quest.id, "its defeat step aims at the giver; the quest is left out"))
            return None
    if quest.against_npc_id and target_refusal(giver, quest.against_npc_id, False):
        notes.append(note(quest.id, "the giver was the target; it is no longer"))
        return quest.model_copy(update={"against_npc_id": None})
    return quest


def _stale(reveal: RevealCondition, kept: list[QuestPlan]) -> bool:
    """A reveal by a quest (or a quest's reward item) that is no longer in the plan."""
    if reveal.kind is RevealKind.QUEST_COMPLETED:
        return reveal.quest_id not in {q.id for q in kept}
    if reveal.kind is RevealKind.ITEM_SHOWN:
        return reveal.item not in {q.reward_item for q in kept}
    return False


def without_quests(plan: CampaignPlan, kept: list[QuestPlan]) -> CampaignPlan:
    """`plan` with only the `kept` quests; secrets revealed by a dropped quest (or its reward
    item) reveal at a friendly attitude instead."""
    friendly = RevealCondition(kind=RevealKind.ATTITUDE, band=AttitudeBand.FRIENDLY)
    npcs: list[NpcPlan] = []
    for npc in plan.npcs:
        secrets = tuple(
            s.model_copy(update={"reveal": friendly}) if _stale(s.reveal, kept) else s
            for s in npc.secrets
        )
        npcs.append(npc.model_copy(update={"secrets": secrets}))
    return plan.model_copy(update={"npcs": tuple(npcs), "quests": tuple(kept)})


def fit_quests(plan: CampaignPlan, notes: list[Problem]) -> CampaignPlan:
    """C1 over every side quest of the plan: repaired, or left out as any dropped quest is."""
    fitted = [fit_side_quest(q, notes) for q in plan.quests]
    kept = [q for q in fitted if q is not None]
    if len(kept) < len(fitted):
        return without_quests(plan, kept)
    return plan.model_copy(update={"quests": tuple(kept)})


def step_key(step: QuestStep) -> tuple[object, ...]:
    return (step.kind, step.nodes, step.npc, item_key(step.item or ""), step.tag, step.band)


def _counted(steps: list[QuestStep], owner: str, notes: list[Problem]) -> list[QuestStep]:
    """C4: a counted find of an item a deliver step hands over asks for as many as it hands
    (a deliver step has no count); its places are cut to fit."""
    hands = [s for s in steps if s.kind is StepKind.DELIVER]
    out: list[QuestStep] = []
    for step in steps:
        hand = next((h for h in hands if same_item(h.item or "", step.item or "")), None)
        if step.kind is StepKind.OBTAIN and hand is not None and hand.count != step.count:
            notes.append(note(owner, f"find {step.count} but hand over {hand.count}: one count"))
            step = step.model_copy(update={"count": hand.count, "nodes": step.nodes[: hand.count]})
        out.append(step)
    return out


def fit_steps(
    owner: str, steps: tuple[QuestStep, ...], notes: list[Problem]
) -> tuple[QuestStep, ...]:
    """C2 and C4 over one step list (`owner` names it in the notes). A `free` step never gets
    here: `plan_satisfy` drops it earlier in the same repair (V16)."""
    kept: list[QuestStep] = []
    seen: set[tuple[object, ...]] = set()
    for step in steps:
        if step_key(step) in seen:
            notes.append(note(owner, f"{step.text!r} dropped (a step that repeats an earlier one)"))
            continue
        seen.add(step_key(step))
        kept.append(step)
    return tuple(_counted(kept, owner, notes))
