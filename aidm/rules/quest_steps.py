"""Engine checks of quest steps (M23, GOAL "Steps"). Pure, state-based.

Every check reads the CURRENT state, so work done before a quest is accepted counts the moment
it is active. A step is met when its count reaches `QuestStep.goal()`:
- visit: its places in `World.visited` (x/N);
- clear: a fight there was won (or a parley succeeded): the spoke milestone `clear:<node>` in
  `CampaignState.milestones` (DECISIONS M23.2); a gateway counts once its boss is defeated;
- defeat: the NPC is dead (`WorldNpc.dead`), or the step names a region boss and
  `progression.boss_defeated` holds (saves from before `dead`);
- obtain: living heroes carry `count` copies: keepsakes of that name whose `quest_id` is the
  quest owning the step (quest items placed by the engine; flavour keepsakes never count) plus
  inventory entries with the item's key;
- deliver: the NPC holds such a keepsake (`WorldNpc.keepsakes`, handed over by `KeepsakeGiven`);
  for a favour a flavour keepsake (no `quest_id`) of that name counts too (M23.5);
- meet: the party stands where the NPC is, the NPC alive and not hostile;
- win_over: the NPC (alive, not hostile) reaches the band's floor score;
- learn: `rules.secrets.engine_knows(tag)`;
- free: never by itself (the AI proposes it through `update_quest`, `rules.quest_free`).

Public API: `step_count(state, step, owner) -> int` (0..goal, the x of "x/N"),
`step_met(state, step, owner) -> bool`, `steps_met(state, steps, done, owner) -> int` (how many
leading steps are met when `done` are already recorded; steps are sequential),
`npc_meetable(state, npc_id) -> bool` (present, alive, not hostile).
"""

from collections.abc import Callable

from aidm.models.quests import QuestKind, QuestStep, StepKind
from aidm.models.state import GameState
from aidm.models.world import WorldNpc
from aidm.rules.milestones import clear_key
from aidm.rules.plan_ids import boss_npc_id
from aidm.rules.progression import boss_defeated
from aidm.rules.secrets import engine_knows, item_key
from aidm.rules.social import attitude_score, band_floor, npc_is_hostile

type _Check = Callable[[GameState, QuestStep, str], int]


def _alive(state: GameState, npc_id: str | None) -> WorldNpc | None:
    npc = state.world.npcs.get(npc_id or "")
    return npc if npc is not None and not npc.dead else None


def npc_meetable(state: GameState, npc_id: str | None) -> bool:
    npc = _alive(state, npc_id)
    if npc is None or npc.node_id is None:
        return False
    return npc.node_id == state.world.current_node and not npc_is_hostile(npc)


def _visit(state: GameState, step: QuestStep, owner: str) -> int:
    return sum(1 for node in step.nodes if node in state.world.visited)


def _clear(state: GameState, step: QuestStep, owner: str) -> int:
    campaign = state.campaign
    if campaign is None:
        return 0
    node = step.nodes[0]
    if clear_key(node) in campaign.milestones:
        return 1
    region = next((r for r in campaign.plan.all_regions() if r.gateway.id == node), None)
    return int(region is not None and boss_defeated(state, region))


def _defeat(state: GameState, step: QuestStep, owner: str) -> int:
    npc = state.world.npcs.get(step.npc or "")
    if npc is not None and npc.dead:
        return 1
    campaign = state.campaign
    if campaign is None:
        return 0
    regions = campaign.plan.all_regions()
    region = next((r for r in regions if boss_npc_id(r) == step.npc), None)
    return int(region is not None and boss_defeated(state, region))


def _carried(state: GameState, item: str, owner: str) -> int:
    wanted = item_key(item)
    count = 0
    for creature in state.creatures.values():
        if creature.pc is None or creature.dead:
            continue
        count += sum(
            1 for k in creature.pc.keepsakes if k.quest_id == owner and item_key(k.name) == wanted
        )
        count += sum(e.qty for e in creature.pc.inventory if item_key(e.item) == wanted)
    return count


def _obtain(state: GameState, step: QuestStep, owner: str) -> int:
    return min(step.goal(), _carried(state, step.item or "", owner))


def _owners(state: GameState, owner: str) -> frozenset[str | None]:
    """Whose keepsakes count for a deliver step: the owning quest's; a favour also counts a
    flavour keepsake (it asks for one the party already carries, M23.5)."""
    quest = state.world.quests.get(owner)
    if quest is not None and quest.kind is QuestKind.FAVOUR:
        return frozenset({owner, None})
    return frozenset({owner})


def _deliver(state: GameState, step: QuestStep, owner: str) -> int:
    npc = state.world.npcs.get(step.npc or "")
    if npc is None:
        return 0
    wanted = item_key(step.item or "")
    owners = _owners(state, owner)
    held = sum(1 for k in npc.keepsakes if k.quest_id in owners and item_key(k.name) == wanted)
    return min(step.goal(), held)


def _meet(state: GameState, step: QuestStep, owner: str) -> int:
    return int(npc_meetable(state, step.npc))


def _win_over(state: GameState, step: QuestStep, owner: str) -> int:
    npc = _alive(state, step.npc)
    if npc is None or npc.hostile or step.band is None:
        return 0
    return int(attitude_score(npc) >= band_floor(step.band))


def _learn(state: GameState, step: QuestStep, owner: str) -> int:
    return int(engine_knows(state, step.tag or ""))


def _free(state: GameState, step: QuestStep, owner: str) -> int:
    return 0


_CHECKS: dict[StepKind, _Check] = {
    StepKind.VISIT: _visit,
    StepKind.CLEAR: _clear,
    StepKind.DEFEAT: _defeat,
    StepKind.OBTAIN: _obtain,
    StepKind.DELIVER: _deliver,
    StepKind.MEET: _meet,
    StepKind.WIN_OVER: _win_over,
    StepKind.LEARN: _learn,
    StepKind.FREE: _free,
}


def step_count(state: GameState, step: QuestStep, owner: str) -> int:
    return min(step.goal(), _CHECKS[step.kind](state, step, owner))


def step_met(state: GameState, step: QuestStep, owner: str) -> bool:
    return step_count(state, step, owner) >= step.goal()


def steps_met(state: GameState, steps: tuple[QuestStep, ...], done: int, owner: str) -> int:
    met = done
    while met < len(steps) and step_met(state, steps[met], owner):
        met += 1
    return met
