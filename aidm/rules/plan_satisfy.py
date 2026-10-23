"""Closed world at plan time: every quest step can be finished in the world it names (M29.9b).

Pure. `unsatisfiable(plan)` lists each step nobody could finish (codes):
- `learn_source`: a `learn` tag has no source in its act: the step's own clue item or another
  clue of the act teaching that tag (`rules.quest_items` places them), a place of the act whose
  id or name holds every tag word, an NPC living there with a secret holding it, or another
  quest of that act or before whose id or title holds it (what `rules.quest_learn` reads in
  play);
- `give_item`: a `deliver` step's item is obtained by no step of the same quest (the routes of a
  main quest share one owner, the rule `aidm.rules.quest_steps` counts by);
- `step_person`: a step names a person who is neither an NPC of the plan nor a region master;
- `step_place`: a step names a place that is no place of its act.
`satisfy_plan(plan, notes)` repairs each one onto registered things, or registers the thing
through the quest-item path (each repair a `quest_repair` note): a missing place is dropped (no
place left: the act's first spoke); a missing person becomes the owner's anchor (a side quest's
giver, a route's master; a `defeat` of nobody becomes a `free` step); a delivered item nobody
obtains gets an `obtain` at the first spoke (no room: the step meets its person); a tag without
a source gets a clue "Notes on <Tag>" lying at the act's first spoke.

Public API: `unsatisfiable(plan) -> list[Problem]`, `satisfy_plan(plan, notes) -> CampaignPlan`,
`learnable(plan, act, owner, step) -> bool`, `CLUE_NAME`.
"""

from aidm.models.campaign import Act, CampaignPlan
from aidm.models.problem import Problem
from aidm.models.quests import MAX_STEPS, QuestStep, StepKind
from aidm.rules.plan_ids import boss_npc_id
from aidm.rules.plan_steps import map_steps, note
from aidm.rules.secrets import fact_words, item_key

CLUE_NAME = "Notes on {tag}"
_NPC_KINDS = frozenset({StepKind.MEET, StepKind.WIN_OVER, StepKind.DELIVER, StepKind.PAY})


def _quest_of(owner: str) -> str:
    return owner.split("/", 1)[0]


def _act_steps(plan: CampaignPlan, act: Act) -> list[QuestStep]:
    routes = act.main.routes if act.main is not None else ()
    steps = [s for r in routes for s in r.steps]
    return steps + [s for q in plan.quests if q.act == act.index for s in q.steps]


def _clues(plan: CampaignPlan, act: Act) -> set[str]:
    """The tags the clue items of `act`'s steps teach."""
    return {s.tag for s in _act_steps(plan, act) if s.kind is StepKind.LEARN and s.item and s.tag}


def learnable(plan: CampaignPlan, act: Act, owner: str, step: QuestStep) -> bool:
    """A source can teach `step`'s tag in `act` (see the module doc)."""
    wanted = fact_words(step.tag or "")
    if not wanted:
        return False
    if step.item or step.tag in _clues(plan, act):
        return True
    homes = {n.id for n in act.region.nodes()}
    groups = [(n.id, n.name) for n in act.region.nodes()]
    groups += [(s.text,) for n in plan.npcs if n.home_node in homes for s in n.secrets]
    groups += [
        (q.id, q.title) for q in plan.quests if q.act <= act.index and q.id != _quest_of(owner)
    ]
    return any(wanted <= fact_words(*group) for group in groups)


class _World:
    """What one plan registers: people, places by act, items obtained by owner."""

    def __init__(self, plan: CampaignPlan) -> None:
        self.plan = plan
        self.people = {n.id for n in plan.npcs} | {boss_npc_id(r) for r in plan.all_regions()}
        self.obtained: set[tuple[str, str]] = set()
        map_steps(plan, self._obtains)

    def _obtains(self, act: Act, owner: str, steps: tuple[QuestStep, ...]) -> tuple[QuestStep, ...]:
        for s in steps:
            if s.kind is StepKind.OBTAIN and s.item:
                self.obtained.add((_quest_of(owner), item_key(s.item)))
        return steps

    def failures(self, act: Act, owner: str, step: QuestStep) -> list[str]:
        out: list[str] = []
        places = {n.id for n in act.region.nodes()}
        if any(n not in places for n in step.nodes):
            out.append("step_place")
        if step.npc is not None and step.npc not in self.people:
            out.append("step_person")
        held = (_quest_of(owner), item_key(step.item or "")) in self.obtained
        if step.kind is StepKind.DELIVER and not held:
            out.append("give_item")
        if step.kind is StepKind.LEARN and not learnable(self.plan, act, owner, step):
            out.append("learn_source")
        return out


_MESSAGES = {
    "step_place": "a step names a place outside its act",
    "step_person": "a step names a person nobody registered",
    "give_item": "an item is given that no step of the quest obtains",
    "learn_source": "a tag nothing in the act can teach",
}


def unsatisfiable(plan: CampaignPlan) -> list[Problem]:
    world = _World(plan)
    found: list[Problem] = []

    def check(act: Act, owner: str, steps: tuple[QuestStep, ...]) -> tuple[QuestStep, ...]:
        for i, step in enumerate(steps, start=1):
            found.extend(
                Problem(code=c, message=f"{owner}: step {i}: {_MESSAGES[c]}", subject=owner)
                for c in world.failures(act, owner, step)
            )
        return steps

    map_steps(plan, check)
    return found


def _anchor(plan: CampaignPlan, act: Act, owner: str) -> str:
    quest = next((q for q in plan.quests if q.id == owner), None)
    return quest.giver_npc_id if quest is not None else boss_npc_id(act.region)


def _fix_place(act: Act, step: QuestStep) -> QuestStep:
    places = {n.id for n in act.region.nodes()}
    nodes = tuple(n for n in step.nodes if n in places) or (act.region.spokes[0].id,)
    if step.kind in (StepKind.CLEAR, StepKind.LEARN):
        nodes = nodes[:1]
    return step.model_copy(update={"nodes": nodes})


def _fix_person(plan: CampaignPlan, act: Act, owner: str, step: QuestStep) -> QuestStep:
    if step.kind not in _NPC_KINDS:
        return QuestStep(kind=StepKind.FREE, text=step.text)
    return step.model_copy(update={"npc": _anchor(plan, act, owner)})


def _clue(act: Act, step: QuestStep) -> QuestStep:
    name = CLUE_NAME.format(tag=(step.tag or "").title())
    return step.model_copy(update={"item": name, "nodes": (act.region.spokes[0].id,)})


def _fix_steps(
    world: _World, act: Act, owner: str, steps: tuple[QuestStep, ...], notes: list[Problem]
) -> tuple[QuestStep, ...]:
    out: list[QuestStep] = []
    inserted = 0
    for step in steps:
        codes = world.failures(act, owner, step)
        if "step_place" in codes:
            step = _fix_place(act, step)
        if "step_person" in codes:
            step = _fix_person(world.plan, act, owner, step)
        if "learn_source" in codes:
            step = _clue(act, step)
        if "give_item" in codes and step.kind is StepKind.DELIVER:
            if len(steps) + inserted < MAX_STEPS:
                spoke = (act.region.spokes[0].id,)
                out.append(QuestStep(kind=StepKind.OBTAIN, text="-", item=step.item, nodes=spoke))
                world.obtained.add((_quest_of(owner), item_key(step.item or "")))
                inserted += 1
            else:
                step = QuestStep(kind=StepKind.MEET, text=step.text, npc=step.npc)
        notes.extend(note(owner, f"repaired: {_MESSAGES[c]}") for c in codes)
        out.append(step)
    return tuple(out)


def satisfy_plan(plan: CampaignPlan, notes: list[Problem]) -> CampaignPlan:
    world = _World(plan)
    return map_steps(plan, lambda act, owner, steps: _fix_steps(world, act, owner, steps, notes))
