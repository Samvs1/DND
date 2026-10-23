"""Quest items in the world (M23.3, GOAL "Items"). Pure.

Every `obtain` step of an act (the routes of its main quest and its side quests, read through
`aidm.rules.quest_plan`) places `count` copies of its item over its places (copy i lies at
`nodes[i % len(nodes)]`), visible or hidden; a copy of an item (same `item_key`) an earlier step
of the act already lays at that place is not placed again (M29.7c R11: one item per name and
place, which every quest needing it counts, `aidm.rules.quest_steps`); a hidden one is found
by a search check meeting `dc_for_tier(HIDDEN_ITEM_DC_TIER)`
(`aidm.rules.scene.discovery_events`). A placed item carries the id of the quest OWNING the step
(`main-<region>` for route steps; the first step placing a shared item owns it);
`aidm.rules.quest_steps` counts it once a hero carries it; picked up it becomes a keepsake with
that `quest_id` (`aidm.rules.equipment.take_events`). Keepsakes cannot be sold or dropped, so
neither can quest items.

Idempotent without new state: an item id (`plan_ids.quest_item_id`) is placed only when no
world item, hero keepsake or NPC keepsake has it, so an item picked up or handed over is never
placed again (DECISIONS M23.3; a hero removed from the table takes its keepsakes along, and
their quest items lie at their places again after the next settle).

Names: `item_words` is `secrets.item_key` (the rules' one item normaliser, also used by the step
checks) split into words, articles dropped and a plural `s` cut. `same_item(a, b)`: the word sets
are equal, or the smaller one (at least two words) lies inside the larger ("Bell-Tongue" is the
"False Bell-Tongue"; a plain "ring" is not the "Drowned King's Ring").

Public API: `HIDDEN_ITEM_DC_TIER`, `act_quest_items(plan, act_index) -> list[WorldItem]`,
`quest_item_events(state, plan, act_index) -> list[ItemPlaced]`, `item_words(name)`,
`same_item(a, b)`, `Spot`, `QuestItemSpot(item_id, name, spot, holder)`,
`quest_item_named(state, name) -> QuestItemSpot | None` (a visible copy here first).
"""

from collections import Counter
from dataclasses import dataclass
from enum import StrEnum

from aidm.models.campaign import CampaignPlan
from aidm.models.checks import DcTier
from aidm.models.quests import QuestStep, StepKind
from aidm.models.state import GameState
from aidm.models.world import WorldItem
from aidm.models.world_events import ItemPlaced
from aidm.rules.checks import dc_for_tier
from aidm.rules.plan_ids import quest_item_id
from aidm.rules.quest_plan import main_quest, quest_steps
from aidm.rules.secrets import item_key

HIDDEN_ITEM_DC_TIER = DcTier.EASY
_ARTICLES = frozenset({"the", "a", "an"})
_MIN_PART_WORDS = 2


class Spot(StrEnum):
    HERE = "here"
    HIDDEN_HERE = "hidden_here"
    ELSEWHERE = "elsewhere"
    CARRIED = "carried"
    GIVEN = "given"


@dataclass(frozen=True)
class QuestItemSpot:
    item_id: str
    name: str
    spot: Spot
    holder: str = ""  # the hero or NPC holding it (carried / given)


type _Placed = Counter[tuple[str, str]]


def _items(
    quest_id: str, route_id: str | None, steps: tuple[QuestStep, ...], placed: _Placed
) -> list[WorldItem]:
    """The copies the steps place; a copy an earlier step already lays at that place (same item
    key) is not placed twice: one item per name and place, shared (M29.7c R11)."""
    out: list[WorldItem] = []
    for index, step in enumerate(steps):
        if step.kind is not StepKind.OBTAIN or step.item is None or not step.nodes:
            continue
        before, here = Counter(placed), Counter[tuple[str, str]]()
        for copy in range(step.count):
            node = step.nodes[copy % len(step.nodes)]
            spot = (item_key(step.item), node)
            here[spot] += 1
            if here[spot] <= before[spot]:
                continue
            placed[spot] += 1
            out.append(
                WorldItem(
                    id=quest_item_id(quest_id, route_id, index, copy),
                    name=step.item,
                    node_id=node,
                    hidden=step.hidden,
                    discover_dc=dc_for_tier(HIDDEN_ITEM_DC_TIER) if step.hidden else None,
                    quest_id=quest_id,
                )
            )
    return out


def act_quest_items(plan: CampaignPlan, act_index: int) -> list[WorldItem]:
    main = main_quest(plan, act_index)
    placed: _Placed = Counter()
    items = [i for route in main.routes for i in _items(main.id, route.id, route.steps, placed)]
    for quest in plan.quests:
        if quest.act == act_index:
            items += _items(quest.id, None, quest_steps(plan, quest), placed)
    return items


def _known_ids(state: GameState) -> set[str]:
    known = set(state.world.items)
    for creature in state.creatures.values():
        if creature.pc is not None:
            known.update(k.id for k in creature.pc.keepsakes)
    for npc in state.world.npcs.values():
        known.update(k.id for k in npc.keepsakes)
    return known


def quest_item_events(state: GameState, plan: CampaignPlan, act_index: int) -> list[ItemPlaced]:
    known = _known_ids(state)
    return [ItemPlaced(item=i) for i in act_quest_items(plan, act_index) if i.id not in known]


def item_words(name: str) -> frozenset[str]:
    words = (w for w in item_key(name).split("-") if w and w not in _ARTICLES)
    return frozenset(w.removesuffix("s") if len(w) > 3 else w for w in words)


def same_item(a: str, b: str) -> bool:
    left, right = item_words(a), item_words(b)
    if not left or not right:
        return False
    small, large = (left, right) if len(left) <= len(right) else (right, left)
    return small == large or (len(small) >= _MIN_PART_WORDS and small <= large)


def _spots(state: GameState) -> list[QuestItemSpot]:
    here = state.world.current_node
    spots: list[QuestItemSpot] = []
    for item in sorted(state.world.items.values(), key=lambda i: i.id):
        if item.quest_id is None:
            continue
        spot = Spot.ELSEWHERE
        if item.node_id == here:
            spot = Spot.HIDDEN_HERE if item.hidden else Spot.HERE
        spots.append(QuestItemSpot(item.id, item.name, spot))
    for creature in state.creatures.values():
        if creature.pc is not None:
            spots += [
                QuestItemSpot(k.id, k.name, Spot.CARRIED, creature.name)
                for k in creature.pc.keepsakes
                if k.quest_id is not None
            ]
    for npc in state.world.npcs.values():
        spots += [
            QuestItemSpot(k.id, k.name, Spot.GIVEN, npc.name)
            for k in npc.keepsakes
            if k.quest_id is not None
        ]
    return spots


def quest_item_named(state: GameState, name: str) -> QuestItemSpot | None:
    """The quest item `name` looks like (a visible copy lying here first), else None."""
    matches = [s for s in _spots(state) if same_item(name, s.name)]
    here = next((s for s in matches if s.spot is Spot.HERE), None)
    return here or (matches[0] if matches else None)
