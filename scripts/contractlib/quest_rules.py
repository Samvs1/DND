"""Contract rules C1-C4 (generated quests), checked where a quest is registered and when a
step is recorded done (M43.1). Reuses `rules.quest_check`, `rules.quest_targets` and
`rules.quest_steps`."""

from aidm.dm.campaign_draft_base import name_key
from aidm.models.campaign import CampaignPlan
from aidm.models.events import AnyEvent
from aidm.models.quests import QuestKind, StepKind
from aidm.models.state import GameState
from aidm.models.world import Quest, QuestState
from aidm.rules.quest_check import check_plan_quests
from aidm.rules.quest_contract import FRIEND_TARGET, step_key, target_refusal
from aidm.rules.quest_items import same_item
from aidm.rules.quest_steps import step_met
from aidm.rules.quest_targets import party_friend
from scripts.contractlib.save import Finding, Visitor

_BATCH = frozenset({"quest_step_done", "route_discovered"})
_C2_CODES = {"quest_steps", "step_node", "step_npc", "step_clear_arrival", "step_tag"}


def c1_targets(seq: int, state: GameState, quest: Quest) -> list[Finding]:
    """C1: the target is never the giver or a friend; one person is one record."""
    targets = {s.npc for s in quest.steps if s.kind is StepKind.DEFEAT and s.npc}
    if quest.against_npc_id:
        targets.add(quest.against_npc_id)
    found: list[Finding] = []
    for npc_id in sorted(targets):
        why = target_refusal(quest.giver_npc_id or "", npc_id, party_friend(state, npc_id))
        if why is not None:
            who = "a friend" if why == FRIEND_TARGET else "the giver"
            found.append(Finding("C1", seq, f"{quest.id}: the target {npc_id} is {who}"))
    return found


def dup_people(seq: int, state: GameState, told: set[str]) -> list[Finding]:
    """C1: one person is one record (two NPCs with one name are told once)."""
    names: dict[str, str] = {}
    found: list[Finding] = []
    for npc in state.world.npcs.values():
        other = names.setdefault(name_key(npc.name), npc.id)
        if other != npc.id and npc.id not in told:
            told.add(npc.id)
            found.append(Finding("C1", seq, f"{npc.name!r} is two records: {other}, {npc.id}"))
    return found


def c2_steps(seq: int, quest: Quest) -> list[Finding]:
    """C2: every step is an engine-checked kind and appears once (its fields: the model)."""
    found = [
        Finding("C2", seq, f"{quest.id}: step {i} is a free step, the engine cannot check it")
        for i, s in enumerate(quest.steps)
        if s.kind is StepKind.FREE
    ]
    seen: set[tuple[object, ...]] = set()
    for i, step in enumerate(quest.steps):
        if step.kind is not StepKind.FREE and step_key(step) in seen:
            found.append(Finding("C2", seq, f"{quest.id}: step {i} repeats an earlier step"))
        seen.add(step_key(step))
    return found


def c4_counts(seq: int, quest: Quest) -> list[Finding]:
    """C4: a counted find and its hand-over use the same count."""
    found: list[Finding] = []
    for find in (s for s in quest.steps if s.kind is StepKind.OBTAIN and s.count > 1):
        for hand in (s for s in quest.steps if s.kind is StepKind.DELIVER):
            if same_item(find.item or "", hand.item or "") and hand.count != find.count:
                msg = f"{quest.id}: find {find.count} x {find.item}, hand over {hand.count}"
                found.append(Finding("C4", seq, msg))
    return found


def plan_findings(seq: int, plan: CampaignPlan) -> list[Finding]:
    """C2 (places and people the steps name exist in the act) and C4 (the reward is never
    the item asked for), over the plan a campaign install registers."""
    found = [
        Finding("C2", seq, p.message[:110])
        for p in check_plan_quests(plan)
        if p.code in _C2_CODES or p.code == "deliver_item"
    ]
    for q in plan.quests:
        asked = [s.item for s in q.steps if s.item]
        if q.reward_item and any(same_item(q.reward_item, a) for a in asked):
            found.append(Finding("C4", seq, f"{q.id}: the reward {q.reward_item!r} is asked for"))
    return found


def c3_done(
    seq: int, decided: GameState, state: GameState, quest_id: str, index: int
) -> list[Finding]:
    """C3: a step is recorded done only while the quest is active and the engine's own check
    of that step holds (which reads only what happened after the quest was accepted)."""
    quest = state.world.quests.get(quest_id)
    if quest is None or quest.kind is QuestKind.MAIN or index >= len(quest.steps):
        return []
    step = quest.steps[index]
    if quest.state is not QuestState.ACTIVE:
        return [Finding("C3", seq, f"{quest_id}: step {index} done while {quest.state.value}")]
    if step.kind is not StepKind.FREE and not step_met(decided, step, quest_id):
        return [
            Finding("C3", seq, f"{quest_id}: step {index} ({step.kind.value}) done, check fails")
        ]
    return []


class QuestRules(Visitor):
    def __init__(self) -> None:
        self.seen: set[str] = set()
        self.told: set[str] = set()
        self.batch: GameState | None = None  # the state a run of step events was decided on
        self.prev = ""

    def see(self, seq: int, state: GameState, event: AnyEvent) -> list[Finding]:
        if event.type == "campaign_installed":
            return plan_findings(seq, event.plan)
        before, self.prev = self.prev, event.type
        if event.type == "quest_step_done":
            # the engine decides every step event of one pass on the state before the first one
            if self.batch is None or before not in _BATCH:
                self.batch = state.model_copy(deep=True)
            return c3_done(seq, self.batch, state, event.quest_id, event.step)
        if event.type != "quest_updated" or event.quest.id in self.seen:
            return []
        self.seen.add(event.quest.id)
        quest = event.quest
        if quest.kind is QuestKind.MAIN:
            return []
        found = c1_targets(seq, state, quest) + dup_people(seq, state, self.told)
        return found + c2_steps(seq, quest) + c4_counts(seq, quest)
