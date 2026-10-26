"""Plan repairs that keep learning and reporting honest (M31.1b, round 4 V13 V14). Pure.

Run by `aidm.rules.plan_repair.repair_plan`, each repair a `quest_repair` note:
- `normal_tags` (V13): learn tags are slugs (`secrets.item_key`), and a tag whose words hold
  every word of a shorter learn tag of the same act is that tag ("brother-mallow" is "mallow"),
  so play matches tags exactly and never fuzzily;
- `learn_visits` (V13c): a learn step whose ONLY source is a place (arriving there taught it,
  round 4: "Learn about tithing" closed on arrival) becomes a visit of that place, so its line
  says what the party really does ("Go to The Tithing Shed"); a step with a clue, a person who
  teaches it or a quest title keeps learning (`plan_satisfy.learn_sources`);
- `giver_reports` (V14; M41.4, round 7 Z14: every side quest, no longer only one whose words
  asked the party back, as those words missed "prove to the archivist"): a side quest ends with
  a `meet` of its giver (the giver pays, so the task is handed in where it was given), unless
  its last step already happens at the giver (meet, deliver to, pay or win over them) or it has
  `MAX_STEPS` already (play adds the report then, `rules.quest_targets.report_step_due`).
  Favours always end so (`rules.favours`).

Public API: `normal_tags(plan, notes)`, `learn_visits(plan, notes)`,
`giver_reports(plan, notes)`, `report_step(giver_id)`, `ends_at(steps, giver_id) -> bool`.
"""

from aidm.models.campaign import Act, CampaignPlan
from aidm.models.problem import Problem
from aidm.models.quests import MAX_STEPS, QuestStep, StepKind
from aidm.rules.plan_satisfy import learn_sources
from aidm.rules.plan_steps import map_steps, note
from aidm.rules.secrets import fact_words, item_key

_AT_GIVER = frozenset({StepKind.MEET, StepKind.DELIVER, StepKind.PAY, StepKind.WIN_OVER})


def _canon_tag(tags: set[str], tag: str) -> str:
    slug = item_key(tag) or tag
    words = fact_words(slug)
    shorter = sorted(t for t in tags if fact_words(t) and fact_words(t) < words)
    return shorter[0] if shorter else slug


def normal_tags(plan: CampaignPlan, notes: list[Problem]) -> CampaignPlan:
    tags: dict[int, set[str]] = {}

    def collect(act: Act, owner: str, steps: tuple[QuestStep, ...]) -> tuple[QuestStep, ...]:
        found = tags.setdefault(act.index, set())
        found.update(item_key(s.tag) for s in steps if s.kind is StepKind.LEARN and s.tag)
        return steps

    def fix(act: Act, owner: str, steps: tuple[QuestStep, ...]) -> tuple[QuestStep, ...]:
        out: list[QuestStep] = []
        for step in steps:
            tag = _canon_tag(tags.get(act.index, set()), step.tag) if step.tag else None
            if tag is not None and tag != step.tag:
                notes.append(note(owner, f"the tag {step.tag!r} is {tag!r}"))
                step = step.model_copy(update={"tag": tag})
            out.append(step)
        return tuple(out)

    map_steps(plan, collect)
    return map_steps(plan, fix)


def _taught_here(act: Act, step: QuestStep) -> str | None:
    wanted = fact_words(step.tag or "")
    return next((n.id for n in act.region.nodes() if wanted <= fact_words(n.id, n.name)), None)


def learn_visits(plan: CampaignPlan, notes: list[Problem]) -> CampaignPlan:
    def fix(act: Act, owner: str, steps: tuple[QuestStep, ...]) -> tuple[QuestStep, ...]:
        out: list[QuestStep] = []
        for step in steps:
            place = _taught_here(act, step) if step.kind is StepKind.LEARN else None
            only = place is not None and learn_sources(plan, act, owner, step) == frozenset(
                {"place"}
            )
            if place is None or not only or step.item:
                out.append(step)
                continue
            out.append(QuestStep(kind=StepKind.VISIT, text=step.text, nodes=(place,)))
            notes.append(note(owner, f"learning about {step.tag} is a visit of its place"))
        return tuple(out)

    return map_steps(plan, fix)


def ends_at(steps: tuple[QuestStep, ...], giver_id: str) -> bool:
    return bool(steps) and steps[-1].kind in _AT_GIVER and steps[-1].npc == giver_id


def report_step(giver_id: str) -> QuestStep:
    return QuestStep(kind=StepKind.MEET, text="-", npc=giver_id)


def giver_reports(plan: CampaignPlan, notes: list[Problem]) -> CampaignPlan:
    quests = {q.id: q for q in plan.quests}

    def fix(act: Act, owner: str, steps: tuple[QuestStep, ...]) -> tuple[QuestStep, ...]:
        quest = quests.get(owner)
        if quest is None or ends_at(steps, quest.giver_npc_id) or len(steps) >= MAX_STEPS:
            return steps
        notes.append(note(owner, "the task is handed in where it was given: it ends with them"))
        return (*steps, report_step(quest.giver_npc_id))

    return map_steps(plan, fix)
