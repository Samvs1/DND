"""Step repairs of an assembled plan that keep every step honest (M29.9b T2 T3 T14). Pure.

Run by `aidm.rules.plan_repair.repair_plan`, each repair a `quest_repair` note:
- `master_meets`: a side quest never asks to `meet` a region's master (r3-full 1649: "Bring
  Piper to her mother" was a meet with the master and paid 1600 XP for walking into her fight
  offer, which only the main quest answers, M29.9a T15). The step meets the quest's giver
  instead ("Meet <giver>": the party comes back to tell them); as the FIRST step (the giver
  stands there at acceptance) it is dropped (M31.1b V16: never a `free` step).
- `home_visits`: a side quest's `visit` never names its giver's home (the quest is asked there,
  and only arrivals after acceptance count, `aidm.rules.quest_steps`): that place is dropped
  from the step, and a step left without places is dropped (M31.1b V15: a step never moves to
  a place it does not name; a quest left without steps meets its giver, `rules.plan_satisfy`).
- `engine_texts`: the text of every checked step is the engine's (`rules.step_text`), last.

Public API: `master_meets(plan, notes)`, `home_visits(plan, notes)`, `engine_texts(plan)`,
`map_steps(plan, fix)` (one `fix(act, owner, steps) -> steps` over every route and side quest).
"""

from collections.abc import Callable

from aidm.models.campaign import Act, CampaignPlan, QuestPlan
from aidm.models.problem import Problem
from aidm.models.quests import MainQuestPlan, QuestStep, StepKind
from aidm.rules.plan_ids import boss_npc_id, main_quest_id
from aidm.rules.step_text import StepNames, plan_names, step_text

type StepFix = Callable[[Act, str, tuple[QuestStep, ...]], tuple[QuestStep, ...]]


def note(owner: str, message: str) -> Problem:
    return Problem(code="quest_repair", message=f"{owner}: {message}", subject=owner)


def map_steps(plan: CampaignPlan, fix: StepFix) -> CampaignPlan:
    """`plan` with `fix` applied to every stored route (owner `main-<region>/<route>`) and every
    side quest (owner: its id)."""
    acts: list[Act] = []
    for act in plan.acts:
        if act.main is not None:
            prefix = main_quest_id(act.region)
            routes = tuple(
                r.model_copy(update={"steps": fix(act, f"{prefix}/{r.id}", r.steps)})
                for r in act.main.routes
            )
            act = act.model_copy(update={"main": MainQuestPlan(routes=routes)})
        acts.append(act)
    by_index = {a.index: a for a in acts}
    quests = tuple(
        q.model_copy(update={"steps": fix(by_index[q.act], q.id, q.steps)}) for q in plan.quests
    )
    return plan.model_copy(update={"acts": tuple(acts), "quests": quests})


def _side(plan: CampaignPlan, owner: str) -> QuestPlan | None:
    return next((q for q in plan.quests if q.id == owner), None)


def master_meets(plan: CampaignPlan, notes: list[Problem]) -> CampaignPlan:
    names = plan_names(plan)

    def fix(act: Act, owner: str, steps: tuple[QuestStep, ...]) -> tuple[QuestStep, ...]:
        quest = _side(plan, owner)
        master = boss_npc_id(act.region)
        if quest is None:
            return steps
        out: list[QuestStep] = []
        for i, step in enumerate(steps):
            if step.kind is not StepKind.MEET or step.npc != master:
                out.append(step)
                continue
            giver = quest.giver_npc_id
            if i > 0:
                out.append(QuestStep(kind=StepKind.MEET, text=step.text, npc=giver))
            who = "nothing (dropped)" if i == 0 else f"a meet with {names.person(giver)}"
            notes.append(note(owner, f"meeting {names.person(master)} became {who}"))
        return tuple(out)

    return map_steps(plan, fix)


def home_visits(plan: CampaignPlan, notes: list[Problem]) -> CampaignPlan:
    homes = {n.id: n.home_node for n in plan.npcs}
    names = plan_names(plan)

    def fix(act: Act, owner: str, steps: tuple[QuestStep, ...]) -> tuple[QuestStep, ...]:
        quest = _side(plan, owner)
        home = homes.get(quest.giver_npc_id) if quest is not None else None
        if home is None:
            return steps
        out: list[QuestStep] = []
        for step in steps:
            if step.kind is not StepKind.VISIT or home not in step.nodes:
                out.append(step)
                continue
            nodes = tuple(n for n in step.nodes if n != home)
            notes.append(note(owner, f"{names.place(home)} is the giver's home"))
            if nodes:
                out.append(step.model_copy(update={"nodes": nodes}))
        return tuple(out)

    return map_steps(plan, fix)


def _written(names: StepNames) -> StepFix:
    def fix(act: Act, owner: str, steps: tuple[QuestStep, ...]) -> tuple[QuestStep, ...]:
        return tuple(s.model_copy(update={"text": step_text(s, names)}) for s in steps)

    return fix


def engine_texts(plan: CampaignPlan) -> CampaignPlan:
    return map_steps(plan, _written(plan_names(plan)))
