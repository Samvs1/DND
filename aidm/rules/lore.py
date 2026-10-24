"""Clues that teach a learn tag (M29.9b T13, r3-items 727-783: the party found, held, read and
handed over "the spore-ink note the archivist left", and the learn step never moved). Pure.

A clue is data on the item: `WorldItem.teaches` / `Keepsake.teaches` (a learn tag). There is no
per-item branch: every clue works the same way.
- Taking one up (`rules.equipment.take_events`, `give_keepsake`) or reading it (`use_item` on
  the keepsake, the ONE item interpreter, and the typed "read the note") records ONE
  `LoreLearned`; a learn step counts it when it was recorded while its quest was active
  (`rules.quest_steps`). A clue a living hero carries also teaches it NOW
  (`rules.quest_learn.learn_source`).
- The storyteller may make a found keepsake a clue (`give_keepsake(teaches=...)`) only for a tag
  the party is trying to learn: a learn step not done yet of an active quest or of a route
  of an active main quest (`wanted_tags`). The plan's clue items are placed by
  `rules.quest_items`.

M31.1b V13c: a place whose id or name holds an open learn tag teaches it when the party looks
around or searches there while the quest is active (`place_lore_events`: ONE `LoreLearned`,
`item` the place's name), never by the arrival alone.

Public API: `place_lore_events(state, actor_id) -> list[AnyEvent]` (`LoreLearned` only),
`open_learn_steps(state) -> list[(Quest, QuestStep)]` (the learn steps not done yet, with their
quest), `learned_for(state, quest, tag) -> bool` (recorded while the quest is active),
`wanted_tags(state) -> frozenset[str]`, `lore_events(creature_id, keepsake)`,
`carried_clue(state, actor_id, item) -> Keepsake | None`, `read_events(state, actor_id, item)
-> list[LoreLearned]` (empty: no clue of that name is carried).
"""

from aidm.models.character import Keepsake
from aidm.models.events import AnyEvent
from aidm.models.quest_events import LoreLearned
from aidm.models.quests import QuestKind, QuestStep, StepKind
from aidm.models.state import GameState
from aidm.models.world import Quest, QuestState
from aidm.rules.plan_ids import main_quest_id
from aidm.rules.quest_plan import main_quest
from aidm.rules.secrets import fact_words, item_key


def _route_steps(state: GameState, quest: Quest) -> list[QuestStep]:
    """The steps not done yet of the routes of an active main quest (found or not)."""
    campaign = state.campaign
    if campaign is None:
        return []
    act = next((a for a in campaign.plan.acts if main_quest_id(a.region) == quest.id), None)
    if act is None:
        return []
    steps: list[QuestStep] = []
    for route in main_quest(campaign.plan, act.index).routes:
        progress = quest.route(route.id)
        steps += route.steps[progress.steps_done if progress is not None else 0 :]
    return steps


def _open_steps(state: GameState) -> list[tuple[Quest, QuestStep]]:
    steps: list[tuple[Quest, QuestStep]] = []
    for quest in state.world.quests.values():
        if quest.state is not QuestState.ACTIVE:
            continue
        own = _route_steps(state, quest) if quest.kind is QuestKind.MAIN else None
        own = own if own is not None else list(quest.steps[quest.steps_done :])
        steps += [(quest, step) for step in own]
    return steps


def open_learn_steps(state: GameState) -> list[tuple[Quest, QuestStep]]:
    return [(q, s) for q, s in _open_steps(state) if s.kind is StepKind.LEARN and s.tag]


def learned_for(state: GameState, quest: Quest, tag: str) -> bool:
    learned = state.world.learned.get(tag)
    since = quest.active_since
    return learned is not None and (since is None or learned > since)


def place_lore_events(state: GameState, actor_id: str) -> list[AnyEvent]:
    here = state.world.current_node
    if here is None:
        return []
    name = state.world.node_names.get(here, "") or here
    words = fact_words(here, name)
    out: list[AnyEvent] = []
    taught: set[str] = set()
    for quest, step in open_learn_steps(state):
        tag = step.tag or ""
        wanted = fact_words(tag)
        if not wanted or not wanted <= words or learned_for(state, quest, tag):
            continue
        if tag not in taught:
            taught.add(tag)
            out.append(LoreLearned(creature_id=actor_id, item=name, tag=tag))
    return out


def wanted_tags(state: GameState) -> frozenset[str]:
    return frozenset(s.tag for _, s in open_learn_steps(state) if s.tag)


def lore_events(creature_id: str, keepsake: Keepsake) -> list[LoreLearned]:
    if keepsake.teaches is None:
        return []
    return [LoreLearned(creature_id=creature_id, item=keepsake.name, tag=keepsake.teaches)]


def carried_clue(state: GameState, actor_id: str, item: str) -> Keepsake | None:
    """The clue keepsake named `item` (id, name or item key) the hero carries, else None."""
    actor = state.creatures.get(actor_id)
    if actor is None or actor.pc is None or actor.dead:
        return None
    wanted = item.strip().lower()
    for keepsake in actor.pc.keepsakes:
        names = {keepsake.id.lower(), keepsake.name.lower(), item_key(keepsake.name)}
        if keepsake.teaches is not None and (wanted in names or item_key(item) in names):
            return keepsake
    return None


def read_events(state: GameState, actor_id: str, item: str) -> list[LoreLearned]:
    clue = carried_clue(state, actor_id, item)
    return lore_events(actor_id, clue) if clue is not None else []
