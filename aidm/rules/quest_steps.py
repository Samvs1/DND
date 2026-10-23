"""Engine checks of quest steps (M23, GOAL "Steps"). Pure, state-based.

Every check reads the CURRENT state. A step is met when its count reaches `QuestStep.goal()`:
- visit (M29.9b T3 T14): its places the party ARRIVED at after the quest was accepted
  (`World.arrived` after `Quest.active_since`; the place it stands at when it accepts does not
  count until the next arrival); a main quest (active from the first step into its region) and
  a save from before count `World.visited` (x/N);
- clear: a fight there was won (or a parley succeeded): the spoke milestone `clear:<node>` in
  `CampaignState.milestones` (DECISIONS M23.2); a gateway counts once its boss is defeated;
- defeat: the NPC is dead (`WorldNpc.dead`), or the step names a region boss and
  `progression.boss_defeated` holds (saves from before `dead`);
- obtain: the party has `count` copies: engine quest items of that name (any quest's: one item
  per name and place serves every quest needing it, M29.7c R11; flavour keepsakes never count)
  that living heroes carry or have handed to someone, plus inventory entries with the item's key;
- deliver: the NPC holds such a keepsake (`WorldNpc.keepsakes`, handed over by `KeepsakeGiven`);
  for a favour a flavour keepsake (no `quest_id`) of that name counts too (M23.5);
- meet: the party stands where the NPC is, the NPC alive and not hostile, and (M29.9b) the
  party arrived there after the quest was accepted (`_fresh_here`; a main quest: always);
- win_over: the NPC (alive, not hostile) reaches the band's floor score;
- learn: something teaches the tag NOW (`rules.quest_learn.learn_source`, M29.7c R1: the place
  the party stands at, a feature or secret here, a finished quest, a clue a hero carries; the
  sources bound to the place only after an arrival while the quest is active), never an old
  visit; or a clue was held or read (`World.learned`, M29.9b T13) after the quest
  was accepted;
- free: never by itself (the AI proposes it through `update_quest`, `rules.quest_free`);
- pay (M29.9a): the NPC's `WorldNpc.paid` total reaches the step's `gold` (`rules.paying`).

Public API: `step_count(state, step, owner) -> int` (0..goal, the x of "x/N"),
`step_met(state, step, owner) -> bool`, `steps_met(state, steps, done, owner) -> int` (how many
leading steps are met when `done` are already recorded; steps are sequential),
`npc_meetable(state, npc_id) -> bool` (present, alive, not hostile).
"""

from collections.abc import Callable

from aidm.models.quests import QuestKind, QuestStep, StepKind
from aidm.models.state import GameState
from aidm.models.world import QuestState, WorldNpc
from aidm.rules.milestones import clear_key
from aidm.rules.plan_ids import boss_npc_id
from aidm.rules.progression import boss_defeated
from aidm.rules.quest_learn import learn_source
from aidm.rules.secrets import item_key
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


def _since(state: GameState, owner: str) -> int | None:
    """The seq after which a visit or a presence counts for `owner` (M29.9b T3 T14): its
    acceptance; an offered quest counts only what comes next; None (a main quest, active from
    the party's first step into its region, a save from before, or no registered quest: a
    favour checked before it is asked) counts every visit."""
    quest = state.world.quests.get(owner)
    if quest is not None and quest.state is QuestState.OFFERED:
        return state.event_count
    return quest.active_since if quest is not None else None


def _fresh_here(state: GameState, owner: str) -> bool:
    """The party ARRIVED where it stands after `owner` was accepted (M29.9b: presence the
    party had before, at acceptance, never closes a step; the next arrival does)."""
    since = _since(state, owner)
    here = state.world.current_node or ""
    return since is None or state.world.arrived.get(here, -1) > since


def _visit(state: GameState, step: QuestStep, owner: str) -> int:
    world = state.world
    since = _since(state, owner)
    if since is None:
        return sum(1 for node in step.nodes if node in world.visited)
    return sum(1 for node in step.nodes if world.arrived.get(node, -1) > since)


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


def _carried(state: GameState, item: str) -> int:
    """Copies of `item` the living heroes carry (engine quest items of any quest, M29.7c R11: one
    item serves every quest that needs it; flavour keepsakes never count) or handed over to
    someone (an obtained item stays obtained), plus inventory entries with the item's key."""
    wanted = item_key(item)
    count = 0
    for creature in state.creatures.values():
        if creature.pc is None or creature.dead:
            continue
        count += sum(
            1
            for k in creature.pc.keepsakes
            if k.quest_id is not None and item_key(k.name) == wanted
        )
        count += sum(e.qty for e in creature.pc.inventory if item_key(e.item) == wanted)
    for npc in state.world.npcs.values():
        count += sum(
            1 for k in npc.keepsakes if k.quest_id is not None and item_key(k.name) == wanted
        )
    return count


def _obtain(state: GameState, step: QuestStep, owner: str) -> int:
    return min(step.goal(), _carried(state, step.item or ""))


def _favour(state: GameState, owner: str) -> bool:
    """A favour also counts a flavour keepsake (it asks for one the party already carries,
    M23.5); every quest counts an engine quest item of that name (M29.7c R11)."""
    quest = state.world.quests.get(owner)
    return quest is not None and quest.kind is QuestKind.FAVOUR


def _deliver(state: GameState, step: QuestStep, owner: str) -> int:
    npc = state.world.npcs.get(step.npc or "")
    if npc is None:
        return 0
    wanted = item_key(step.item or "")
    flavour = _favour(state, owner)
    held = sum(
        1
        for k in npc.keepsakes
        if (k.quest_id is not None or flavour) and item_key(k.name) == wanted
    )
    return min(step.goal(), held)


def _meet(state: GameState, step: QuestStep, owner: str) -> int:
    return int(npc_meetable(state, step.npc) and _fresh_here(state, owner))


def _win_over(state: GameState, step: QuestStep, owner: str) -> int:
    npc = _alive(state, step.npc)
    if npc is None or npc.hostile or step.band is None:
        return 0
    return int(attitude_score(npc) >= band_floor(step.band))


def _learn(state: GameState, step: QuestStep, owner: str) -> int:
    tag = step.tag or ""
    since = _since(state, owner)
    learned = state.world.learned.get(tag)
    if learned is not None and (since is None or learned > since):
        return 1  # M29.9b T13: a clue held or read while the quest is on (`rules.lore`)
    return int(learn_source(state, tag, here_counts=_fresh_here(state, owner)) is not None)


def _free(state: GameState, step: QuestStep, owner: str) -> int:
    return 0


def _pay(state: GameState, step: QuestStep, owner: str) -> int:
    npc = _alive(state, step.npc)
    return int(npc is not None and step.gold > 0 and npc.paid >= step.gold)


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
    StepKind.PAY: _pay,
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
