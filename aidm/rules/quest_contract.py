"""Quest contract C1, C2 and C4 where a quest is registered (M43.4). Pure.

One validator for the two doors a generated quest comes through: the campaign install
(`plan_repair.repair_plan`, `dm.campaign_draft_quests.with_quests`) and the favour tool
(`favours._check_npc`). Repair when the repair is plain, reject when no repair keeps the quest
followable (docs/next/M43_CONTRACT.md):
- C1 `target_refusal`: a target is never the one who asks, nor a friend of the party. At install
  `fit_side_quest` clears `against_npc_id` when it is the giver (the quest stays, it only loses
  the deed against the giver) and rejects a quest whose defeat step aims at the giver. A friend
  cannot be told at install (no party yet); `quest_targets.asked_quest` turns that step into a
  meet when the card is asked.
- C2 `fit_steps`: a step that repeats an earlier one is dropped; a `free` step (the engine cannot
  check it) is dropped while a checked step remains.
- C4 `fit_steps`: a hand-over takes one item (a deliver step has no count), so a counted find of
  the same item asks for one too (its places cut to fit). The reward is never the asked item:
  `plan_repair._fit_rewards`.

Public API: `target_refusal`, `fit_side_quest(quest, notes) -> QuestPlan | None`,
`fit_steps(owner, steps, notes) -> tuple[QuestStep, ...]`.
"""

from aidm.models.campaign import QuestPlan
from aidm.models.problem import Problem
from aidm.models.quests import QuestStep, StepKind
from aidm.rules.quest_items import same_item
from aidm.rules.secrets import item_key


def _note(owner: str, message: str) -> Problem:
    return Problem(code="quest_repair", message=f"{owner}: {message}", subject=owner)


def target_refusal(giver: str, npc: str | None, friend: bool) -> str | None:
    """C1: why `npc` cannot be the target of a quest `giver` asks, else None."""
    if npc is not None and npc == giver:
        return "the target is the one who asks"
    if npc is not None and friend:
        return "the target is a friend of the party"
    return None


def fit_side_quest(quest: QuestPlan, notes: list[Problem]) -> QuestPlan | None:
    """C1 at install: the quest (repaired), or None when it is rejected (a note says why)."""
    giver = quest.giver_npc_id
    for step in quest.steps:
        if step.kind is StepKind.DEFEAT and target_refusal(giver, step.npc, False):
            notes.append(
                _note(quest.id, "its defeat step aims at the giver; the quest is left out")
            )
            return None
    if quest.against_npc_id and target_refusal(giver, quest.against_npc_id, False):
        notes.append(_note(quest.id, "the giver was the target; it is no longer"))
        return quest.model_copy(update={"against_npc_id": None})
    return quest


def _key(step: QuestStep) -> tuple[object, ...]:
    return (step.kind, step.nodes, step.npc, item_key(step.item or ""), step.tag, step.band)


def _counted(steps: list[QuestStep], owner: str, notes: list[Problem]) -> list[QuestStep]:
    """C4: a counted find of an item a deliver step hands over asks for as many as it hands."""
    hands = [s for s in steps if s.kind is StepKind.DELIVER]
    out: list[QuestStep] = []
    for step in steps:
        hand = next((h for h in hands if same_item(h.item or "", step.item or "")), None)
        if step.kind is StepKind.OBTAIN and hand is not None and hand.count != step.count:
            notes.append(_note(owner, f"find {step.count} but hand over {hand.count}: one count"))
            step = step.model_copy(update={"count": hand.count, "nodes": step.nodes[: hand.count]})
        out.append(step)
    return out


def fit_steps(
    owner: str, steps: tuple[QuestStep, ...], notes: list[Problem]
) -> tuple[QuestStep, ...]:
    """C2 and C4 over the step list of one quest (`owner` names it in the notes)."""
    checked = any(s.kind is not StepKind.FREE for s in steps)
    kept: list[QuestStep] = []
    seen: set[tuple[object, ...]] = set()
    for step in steps:
        free = step.kind is StepKind.FREE
        if (free and checked) or (not free and _key(step) in seen):
            why = "a step the engine cannot check" if free else "a step that repeats an earlier one"
            notes.append(_note(owner, f"{step.text!r} dropped ({why})"))
            continue
        seen.add(_key(step))
        kept.append(step)
    return tuple(_counted(kept, owner, notes))
