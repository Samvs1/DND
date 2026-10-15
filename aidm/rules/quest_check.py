"""Quest checks of a campaign plan (M23, GOAL "Plan generator and checks"). Pure.

Generation-time checks: they return `Problem`s and never reject a saved plan (the playtest plan
of 2026-10 has a giver in another act and still loads). Every check reads the quests through
`aidm.rules.quest_plan`, so an old plan is checked as it will play.

Checks (codes): `quest_giver_act` (a side quest's giver does not live in its act region),
`quest_steps` (a quest or route has not 1 to 4 steps), `side_quest_count` (more than
`MAX_SIDE_QUESTS` side quests in an act), `step_node` (a step names a place outside the act
region), `step_npc` (a step names an NPC who does not live in the act region and is not its
boss), `deliver_item` (a delivered item is not obtained by a step of the same quest: the engine
counts only quest items owned by the quest, M23.2; a main quest's routes share one owner),
`route_hint` (a route's hint NPC does not live in the act region), `step_clear_arrival` (a
`clear` of the arrival: it is safe, nothing to fight), `step_tag` (a `learn` tag the engine can
never know in that act: no word of the act's places, the quests up to that act or the secrets of
its residents), `route_peace_ally` (a Peace route on a boss without an ally path: the alliance
resolution needs one).

Public API: `MAX_SIDE_QUESTS`, `check_plan_quests(plan) -> list[Problem]` (empty when valid),
`learnable_words(plan, act) -> frozenset[str]` (the words a `learn` tag of that act may use).
"""

from collections.abc import Iterable

from aidm.models.campaign import Act, CampaignPlan
from aidm.models.problem import Problem
from aidm.models.quests import MAX_STEPS, QuestStep, RouteKind, StepKind
from aidm.rules.plan_ids import boss_npc_id
from aidm.rules.quest_plan import main_quest, quest_steps
from aidm.rules.secrets import fact_words, item_key

MAX_SIDE_QUESTS = 2


def _problem(code: str, subject: str, message: str) -> Problem:
    return Problem(code=code, message=f"{subject}: {message}", subject=subject)


def learnable_words(plan: CampaignPlan, act: Act) -> frozenset[str]:
    """What `rules.secrets.engine_knows` can learn in `act`: its places, the quests up to it
    and the secrets of its residents (features are made in play, so they never count here)."""
    nodes = act.region.nodes()
    homes = {n.id for n in nodes}
    texts = [t for n in nodes for t in (n.id, n.name)]
    texts += [t for q in plan.quests if q.act <= act.index for t in (q.id, q.title)]
    texts += [s.text for n in plan.npcs if n.home_node in homes for s in n.secrets]
    return frozenset(fact_words(*texts))


class _Region:
    """What the steps of one act may name."""

    def __init__(self, plan: CampaignPlan, act: Act) -> None:
        self.act = act
        self.nodes = {n.id for n in act.region.nodes()}
        self.residents = {n.id for n in plan.npcs if n.home_node in self.nodes}
        self.npcs = self.residents | {boss_npc_id(act.region)}
        self.words = learnable_words(plan, act)


def _step(region: _Region, owner: str, step: QuestStep) -> list[Problem]:
    out = [
        _problem("step_node", owner, f"{node!r} is not a place of act {region.act.index}")
        for node in step.nodes
        if node not in region.nodes
    ]
    if step.npc is not None and step.npc not in region.npcs:
        msg = f"{step.npc!r} does not live in act {region.act.index} and is not its boss"
        out.append(_problem("step_npc", owner, msg))
    if step.kind is StepKind.CLEAR and step.nodes == (region.act.region.arrival.id,):
        out.append(_problem("step_clear_arrival", owner, "the arrival is safe, nothing to clear"))
    if step.kind is StepKind.LEARN and not fact_words(step.tag or "") <= region.words:
        msg = f"tag {step.tag!r} can never be learned in act {region.act.index}"
        out.append(_problem("step_tag", owner, msg))
    return out


def _steps(region: _Region, owner: str, steps: tuple[QuestStep, ...]) -> list[Problem]:
    out: list[Problem] = []
    if not 1 <= len(steps) <= MAX_STEPS:
        out.append(_problem("quest_steps", owner, f"{len(steps)} steps (1 to {MAX_STEPS})"))
    for step in steps:
        out += _step(region, owner, step)
    return out


def _quest_of(owner: str) -> str:
    return owner.split("/", 1)[0]


def _items(owner_steps: Iterable[tuple[str, tuple[QuestStep, ...]]]) -> list[Problem]:
    pairs = list(owner_steps)
    obtained = {
        (_quest_of(owner), item_key(s.item or ""))
        for owner, steps in pairs
        for s in steps
        if s.kind is StepKind.OBTAIN
    }
    return [
        _problem("deliver_item", owner, f"{s.item!r} is delivered but never obtained")
        for owner, steps in pairs
        for s in steps
        if s.kind is StepKind.DELIVER and (_quest_of(owner), item_key(s.item or "")) not in obtained
    ]


def _act(plan: CampaignPlan, act: Act) -> list[Problem]:
    region = _Region(plan, act)
    sides = [q for q in plan.quests if q.act == act.index]
    out: list[Problem] = []
    if len(sides) > MAX_SIDE_QUESTS:
        msg = f"{len(sides)} side quests (at most {MAX_SIDE_QUESTS})"
        out.append(_problem("side_quest_count", f"act {act.index}", msg))
    owned: list[tuple[str, tuple[QuestStep, ...]]] = []
    for quest in sides:
        if quest.giver_npc_id not in region.residents:
            msg = f"giver {quest.giver_npc_id!r} does not live in act {act.index}"
            out.append(_problem("quest_giver_act", quest.id, msg))
        owned.append((quest.id, quest_steps(plan, quest)))
    main = main_quest(plan, act.index)
    for route in main.routes:
        owner = f"{main.id}/{route.id}"
        if route.hint_npc_id is not None and route.hint_npc_id not in region.residents:
            msg = f"hint npc {route.hint_npc_id!r} does not live in act {act.index}"
            out.append(_problem("route_hint", owner, msg))
        if route.kind is RouteKind.PEACE and act.region.boss.ally_path is None:
            msg = f"a Peace route needs the boss of act {act.index} to have an ally path"
            out.append(_problem("route_peace_ally", owner, msg))
        owned.append((owner, route.steps))
    for owner, steps in owned:
        out += _steps(region, owner, steps)
    return out + _items(owned)


def check_plan_quests(plan: CampaignPlan) -> list[Problem]:
    return [p for act in plan.acts for p in _act(plan, act)]
