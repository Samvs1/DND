"""What now? (M23.8, GOAL_QUESTS "What players see"). Pure: reads the state, never changes it.

`what_now(state)` answers the players' "what should we do?" with a few plain lines (at most
`MAX_LINES`, no ids), in this order (a running fight or a waiting encounter card comes first):
1. the main quest of the party's region: for every KNOWN route not finished, its current step
   and where (a place, an NPC's current place, "<n> of <m> places seen" for an explore step, the
   next hop when the place is not next door). A region already resolved says the way on is open;
2. every active side quest and favour: its current step and where (same rules);
3. the open quest card ("<giver> is waiting for your answer: <title> (Play tab)") and every other
   offered quest ("<giver> at <place> asked you: <title>");
4. the journal leads;
5. only when 1-4 hold nothing beyond the Force route: a nudge toward an undiscovered route whose
   hint NPC lives in this region, alive and not hostile, else the unexplored exits from here.

M23.9: while the finale card is open, the answer is that choice (the question, then where to
answer it) before anything else.

Never told: an undiscovered route (except as the nudge), where a hidden quest item lies beyond
the place the step text itself names, secrets, motives, or the name of a boss the party has not
reached (it reads "the master of <region>", the journal's rule, `session.views_quests`).

Public API: `MAX_LINES`, `NOTHING`, `FINALE_LINE`, `what_now(state) -> tuple[str, ...]`.
"""

import re

from aidm.models.campaign import RegionPlan
from aidm.models.encounter import EncounterStatus
from aidm.models.quests import FORCE_ROUTE_ID, QuestKind, QuestStep, StepKind
from aidm.models.state import GameState
from aidm.models.world import Quest, QuestState
from aidm.rules.finale import finale_open
from aidm.rules.plan_ids import boss_npc_id, main_quest_id
from aidm.rules.progression import region_of
from aidm.rules.quest_plan import main_quest
from aidm.rules.quest_steps import step_count
from aidm.rules.scene import node_display_name
from aidm.rules.secrets import item_key
from aidm.rules.social import npc_is_hostile
from aidm.rules.world_graph import legal_neighbours, travel_route

MAX_LINES = 6
NOTHING = "Nothing presses right now: look around and talk to the people here."
FIGHTING = "First win this fight, or get away."
FINALE_LINE = "Choose how the story ends on the finale card (Play tab)."
DANGER = "Danger bars the way here: choose what to do on the encounter card."
_NUMBERS = {2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven"}
_TITLES = frozenset(
    {
        "brother",
        "sister",
        "lord",
        "lady",
        "master",
        "magister",
        "cantor",
        "old",
        "the",
        "sir",
        "dame",
        "mother",
        "father",
        "captain",
        "warden",
        "priest",
        "mistress",
        "high",
        "elder",
    }
)
_NPC_STEPS = (StepKind.DEFEAT, StepKind.MEET, StepKind.WIN_OVER, StepKind.DELIVER)


def _suffix(state: GameState, node: str) -> str:
    """Nothing next door, ", two places away via X" further, a note when no open way leads there."""
    world = state.world
    path = travel_route(world, world.current_node, node)
    if path is None:
        return " (the way there is not open yet)"
    if len(path) <= 1:
        return ""
    hops = _NUMBERS.get(len(path), str(len(path)))
    return f", {hops} places away via {node_display_name(state, path[0])}"


def _place(state: GameState, node: str) -> str:
    if node == state.world.current_node:
        return "right here"
    return node_display_name(state, node) + _suffix(state, node)


def _master(region: RegionPlan) -> str:
    return f"the master of {region.name}"


def _boss_met(state: GameState, region: RegionPlan) -> bool:
    world = state.world
    boss = world.npcs.get(boss_npc_id(region))
    node = boss.node_id if boss is not None else region.gateway.id
    return node == world.current_node or node in world.visited


def _safe(state: GameState, text: str) -> str:
    """`text` with the name of every boss the party has not reached replaced."""
    campaign = state.campaign
    if campaign is None:
        return text
    for region in campaign.plan.all_regions():
        if _boss_met(state, region):
            continue
        name = region.boss.name
        text = text.replace(name, _master(region))
        words = [w for w in re.findall(r"[A-Za-z']+", name) if w.lower() not in _TITLES]
        if words and len(words[0]) >= 4:
            text = re.sub(rf"\b{re.escape(words[0])}\b", _master(region), text)
    return text


def _visit_where(state: GameState, step: QuestStep) -> str:
    world = state.world
    if len(step.nodes) == 1:
        return f"Where: {_place(state, step.nodes[0])}."
    left = [n for n in step.nodes if n not in world.visited]
    seen = f"{len(step.nodes) - len(left)} of {len(step.nodes)} places seen"
    if not left:
        return f"{seen}."

    def far(node: str) -> int:
        path = travel_route(world, world.current_node, node)
        return len(path) if path is not None else 99

    nearest = min(left, key=far)
    return f"{seen}; next: {_place(state, nearest)}."


def _obtain_where(state: GameState, owner: str, step: QuestStep) -> str:
    wanted = item_key(step.item or "")
    items = sorted(
        (i for i in state.world.items.values() if i.quest_id == owner),
        key=lambda i: i.id,
    )
    items = [i for i in items if item_key(i.name) == wanted and i.node_id is not None]
    visible = [i.node_id for i in items if not i.hidden and i.node_id is not None]
    if visible:
        return f"It lies at {_place(state, visible[0])}."
    hidden = [i.node_id for i in items if i.hidden and i.node_id is not None]
    if not hidden:
        return ""
    lower = step.text.lower()
    named = [n for n in hidden if node_display_name(state, n).lower() in lower]
    if not named:
        return "It is hidden: search the places you visit."
    return f"Where: {_place(state, named[0])}. It is hidden there: search when you arrive."


def _where(state: GameState, owner: str, step: QuestStep) -> str:
    if step.kind is StepKind.VISIT:
        return _visit_where(state, step)
    if step.kind is StepKind.CLEAR:
        return f"Where: {_place(state, step.nodes[0])}."
    if step.kind is StepKind.OBTAIN:
        return _obtain_where(state, owner, step)
    if step.kind in _NPC_STEPS:
        npc = state.world.npcs.get(step.npc or "")
        if npc is not None and not npc.dead and npc.node_id is not None:
            return f"Where: {_place(state, npc.node_id)}."
    return ""


def _step_line(state: GameState, owner: str, step: QuestStep) -> str:
    text = _safe(state, step.text.rstrip(". "))
    if step.kind is not StepKind.VISIT and step.goal() > 1:
        text += f" ({step_count(state, step, owner)}/{step.goal()})"
    where = _where(state, owner, step)
    return f"{text}. {where}" if where else f"{text}."


def _act_of(state: GameState) -> tuple[RegionPlan, int] | None:
    campaign = state.campaign
    region = region_of(state, state.world.current_node)
    if campaign is None or region is None:
        return None
    act = next(a for a in campaign.plan.acts if a.region.id == region.id)
    return region, act.index


def _way_on(state: GameState, region: RegionPlan, act_index: int) -> list[str]:
    campaign = state.campaign
    if campaign is None or act_index >= len(campaign.plan.acts):
        return []
    arrival = campaign.plan.acts[act_index].region.arrival.id
    name = node_display_name(state, arrival)
    return [f"The way on to {name} is open{_suffix(state, arrival)}."]


def _main_lines(state: GameState, region: RegionPlan, act_index: int) -> tuple[list[str], bool]:
    """The main quest's lines, and whether any known route other than Force is open."""
    campaign = state.campaign
    if campaign is None:
        return [], False
    if region.id in campaign.resolved:
        return _way_on(state, region, act_index), True
    quest = state.world.quests.get(main_quest_id(region))
    if quest is not None and quest.state is not QuestState.ACTIVE:
        return [], False
    known = {r.route_id: r.steps_done for r in quest.routes} if quest is not None else {}
    known = known or {FORCE_ROUTE_ID: 0}
    owner = main_quest_id(region)
    lines: list[str] = []
    other = False
    for route in main_quest(campaign.plan, act_index).routes:
        done = known.get(route.id)
        if done is None or done >= len(route.steps):
            continue
        other = other or route.id != FORCE_ROUTE_ID
        title = _safe(state, route.title.rstrip(". "))
        lines.append(f"{title}: {_step_line(state, owner, route.steps[done])}")
    return lines, other


def _npc_name(state: GameState, npc_id: str | None) -> str:
    npc = state.world.npcs.get(npc_id or "")
    return npc.name if npc is not None else "someone"


def _task_line(state: GameState, quest: Quest) -> str:
    giver = _npc_name(state, quest.giver_npc_id)
    favour = "a favour " if quest.kind is QuestKind.FAVOUR else ""
    head = f"{quest.title} ({favour}for {giver})"
    if quest.steps_done < len(quest.steps):
        return f"{head}: {_step_line(state, quest.id, quest.steps[quest.steps_done])}"
    goal = _safe(state, quest.objective.rstrip(". "))
    return f"{head}: {goal}." if goal else f"{head}."


def _offer_lines(state: GameState, quests: list[Quest]) -> list[str]:
    world = state.world
    ask = world.quest_ask
    lines: list[str] = []
    asked = world.quests.get(ask.quest_id) if ask is not None else None
    if ask is not None and asked is not None:
        who = _npc_name(state, ask.npc_id)
        lines.append(f"{who} is waiting for your answer: {asked.title} (Play tab).")
    for quest in quests:
        if quest.state is not QuestState.OFFERED or quest is asked:
            continue
        giver = world.npcs.get(quest.giver_npc_id or "")
        at = f" at {node_display_name(state, giver.node_id)}" if giver and giver.node_id else ""
        lines.append(f"{_npc_name(state, quest.giver_npc_id)}{at} asked you: {quest.title}.")
    return lines


def _nudge(state: GameState, region: RegionPlan, act_index: int) -> list[str]:
    campaign = state.campaign
    world = state.world
    if campaign is None or region.id in campaign.resolved:
        return []
    quest = world.quests.get(main_quest_id(region))
    past = region.boss.name if _boss_met(state, region) else _master(region)
    for route in main_quest(campaign.plan, act_index).routes:
        if route.id == FORCE_ROUTE_ID or (quest is not None and quest.route(route.id)):
            continue
        npc = world.npcs.get(route.hint_npc_id or "")
        if npc is None or npc.dead or npc_is_hostile(npc) or npc.node_id is None:
            continue
        home = region_of(state, npc.node_id)
        if home is None or home.id != region.id:
            continue
        where = (
            "here with you"
            if npc.node_id == world.current_node
            else "at " + _place(state, npc.node_id)
        )
        return [f"{npc.name} {where} may know another way past {past}."]
    exits = [n for n in legal_neighbours(world, world.current_node) if n not in world.visited]
    if not exits:
        return []
    return [f"Unexplored from here: {', '.join(node_display_name(state, n) for n in exits)}."]


def _urgent(state: GameState) -> list[str]:
    enc = state.encounter
    if enc is not None and enc.status is EncounterStatus.ACTIVE:
        return [FIGHTING]
    offer = state.campaign.offer if state.campaign is not None else None
    return [DANGER] if offer is not None else []


def what_now(state: GameState) -> tuple[str, ...]:
    finale = finale_open(state)
    if finale is not None:
        return (finale.question, FINALE_LINE)
    found = _act_of(state)
    if found is None:
        return (NOTHING,)
    region, act_index = found
    world = state.world
    main, other = _main_lines(state, region, act_index)
    main = [*_urgent(state), *main]
    quests = sorted(world.quests.values(), key=lambda q: q.id)
    active = [q for q in quests if q.state is QuestState.ACTIVE and q.kind is not QuestKind.MAIN]
    rest = [_task_line(state, q) for q in active]
    rest += _offer_lines(state, quests)
    rest += [lead.text for lead in world.leads]
    lines = [*main, *rest]
    if not other and not rest:
        lines += _nudge(state, region, act_index)
    return tuple(lines[:MAX_LINES]) or (NOTHING,)
