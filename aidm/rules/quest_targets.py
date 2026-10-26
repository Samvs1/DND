"""A side quest read against the world it is asked in (M41.4, round 7 Z14 Z15). Pure.

A plan writes its side quests before play, and the world moves on before a giver asks: round 7
offered "Straighten the River" against the seer who had just been helped, and its "Win the fight
at The Grey Bog" closed at once from the fight before the quest. And a task closed far from the
person who gave it and paid at once (The Brief Life of War). From engine state only, never from
the quest's words:
- `party_friend(state, npc_id)`: the NPC is on the party's side NOW: alive, not hostile, and
  friendly or better (`social.attitude_band`), or the party did them good (`WorldNpc.deeds` or
  `social` above nothing: fought for them, a gift, a warm talk), or they gave the party a task it
  took (an active or completed quest of theirs).
- `asked_quest(state, quest) -> Quest`: the quest as it is asked and as it is accepted
  (`quest_offers`): a target who is the party's friend is no target (`against_npc_id` None, so
  no deed against them), and a step to defeat a friend is meeting them instead; a `clear` step
  whose place is already won (`quest_steps.place_won`) is a visit of it, because only a fight
  after the acceptance counts and that place's fight is spent: the task is to go and see. The
  changed steps get the engine's text (`rules.step_text`).
- `report_step_due(state, quest) -> QuestStep | None` (Z14): an active side quest or favour with
  steps that do not end with its giver (known and alive) gets the report to the giver as its last
  step (`QuestStepAdded`, by `quest_progress`): the giver pays, so a task is handed in where it
  was given (saves from before; a plan quest whose four steps left no room, `plan_tasks`).

Public API: `party_friend`, `asked_quest`, `report_step_due`.
"""

from aidm.models.dm_tiers import AttitudeBand
from aidm.models.quests import MAX_QUEST_STEPS, QuestKind, QuestStep, StepKind
from aidm.models.state import GameState
from aidm.models.world import Quest, QuestState
from aidm.rules.plan_tasks import ends_at, report_step
from aidm.rules.quest_steps import place_won
from aidm.rules.social import attitude_band, attitude_score, npc_is_hostile
from aidm.rules.step_text import StepNames, state_names, step_text

_FRIENDS = frozenset({AttitudeBand.FRIENDLY, AttitudeBand.ALLY})
_TOOK = frozenset({QuestState.ACTIVE, QuestState.COMPLETED})


def party_friend(state: GameState, npc_id: str | None) -> bool:
    npc = state.world.npcs.get(npc_id or "")
    if npc is None or npc.dead or npc_is_hostile(npc):
        return False
    if npc.deeds > 0 or npc.social > 0 or attitude_band(attitude_score(npc)) in _FRIENDS:
        return True
    quests = state.world.quests.values()
    return any(q.giver_npc_id == npc.id and q.state in _TOOK for q in quests)


def _asked_step(state: GameState, step: QuestStep, names: StepNames) -> QuestStep:
    if step.kind is StepKind.DEFEAT and party_friend(state, step.npc):
        new = QuestStep(kind=StepKind.MEET, text="-", npc=step.npc)
    elif step.kind is StepKind.CLEAR and place_won(state, step.nodes[0]):
        new = QuestStep(kind=StepKind.VISIT, text="-", nodes=step.nodes)
    else:
        return step
    return new.model_copy(update={"text": step_text(new, names)})


def asked_quest(state: GameState, quest: Quest) -> Quest:
    names = state_names(state)
    steps = tuple(_asked_step(state, step, names) for step in quest.steps)
    against = quest.against_npc_id
    if party_friend(state, against):
        against = None
    if steps == quest.steps and against == quest.against_npc_id:
        return quest
    return quest.model_copy(update={"steps": steps, "against_npc_id": against})


def report_step_due(state: GameState, quest: Quest) -> QuestStep | None:
    giver = state.world.npcs.get(quest.giver_npc_id or "")
    if quest.kind is QuestKind.MAIN or quest.state is not QuestState.ACTIVE or not quest.steps:
        return None
    if giver is None or giver.dead or ends_at(quest.steps, giver.id):
        return None
    if len(quest.steps) >= MAX_QUEST_STEPS:
        return None
    step = report_step(giver.id)
    return step.model_copy(update={"text": step_text(step, state_names(state))})
