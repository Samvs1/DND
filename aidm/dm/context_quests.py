"""The QUESTS section of the context pack and the route hints of NPC voices (M23.5).

Deterministic and compact, never truncated (`aidm.dm.context`). The model sees what the journal
knows, never more:
- each ACTIVE main quest: its objective, then each KNOWN route (`Quest.routes`) with its current
  step and progress; undiscovered routes are never named here;
- each ACTIVE side quest or favour: objective, giver, current step (x/N when counted) and, for a
  step about a quest item, where it is: "lies at <place>" when visible, "carried by <hero>",
  "handed to <npc>", else "not found yet" (a hidden item's place is never given);
- the open quest card ("<giver> is asking now: <title>"), each other OFFERED quest with its giver
  and where the giver is, and the journal leads;
- the finale (M23.9): while it is open, the question and the two ending TITLES with "never choose
  for them" (the ending texts stay out until chosen); once chosen, that ending and its text.
With ids (`show_ids`: the adjudicator) quests and routes show their ids, and a `free` current
step says the model judges it (`update_quest`); every other step is the engine's.

`route_hint_lines(state, npc_id)`: the hint NPC of a route of an unfinished main quest knows that
way (route title and first step), so talking to them can reveal it (NPC_PRIVATE only).

Public API: `quest_lines(state, show_ids) -> list[str]`, `route_hint_lines(state, npc_id)
-> list[str]`.
"""

from aidm.models.quests import QuestKind, QuestStep, StepKind
from aidm.models.state import GameState
from aidm.models.world import Quest, QuestState
from aidm.rules.finale import chosen_ending, finale_open
from aidm.rules.plan_ids import main_quest_id
from aidm.rules.quest_plan import main_quest
from aidm.rules.quest_steps import step_count
from aidm.rules.scene import node_display_name
from aidm.rules.secrets import item_key

FREE_NOTE = " (a free step: you judge it; call update_quest once the party has done it)"
_ITEM_STEPS = (StepKind.OBTAIN, StepKind.DELIVER)
_KIND_WORDS = {QuestKind.SIDE: "side quest", QuestKind.FAVOUR: "favour (goodwill only)"}


def _tag(show_ids: bool, ident: str) -> str:
    return f" [{ident}]" if show_ids else ""


def _npc_name(state: GameState, npc_id: str | None) -> str:
    npc = state.world.npcs.get(npc_id or "")
    return npc.name if npc is not None else "someone"


def _item_spots(state: GameState, quest: Quest, item: str) -> list[str]:
    wanted = item_key(item)
    owners = {quest.id, None} if quest.kind is QuestKind.FAVOUR else {quest.id}
    spots: list[str] = []
    for thing in sorted(state.world.items.values(), key=lambda i: i.id):
        if thing.quest_id == quest.id and item_key(thing.name) == wanted:
            place = node_display_name(state, thing.node_id)
            spots.append("not found yet" if thing.hidden else f"lies at {place}")
    for c in sorted(state.creatures.values(), key=lambda c: c.id):
        if c.pc is not None and any(
            k.quest_id in owners and item_key(k.name) == wanted for k in c.pc.keepsakes
        ):
            spots.append(f"carried by {c.name}")
    for npc in sorted(state.world.npcs.values(), key=lambda n: n.id):
        if any(k.quest_id in owners and item_key(k.name) == wanted for k in npc.keepsakes):
            spots.append(f"handed to {npc.name}")
    return list(dict.fromkeys(spots)) or ["not found yet"]


def _step_text(
    state: GameState, quest: Quest, steps: tuple[QuestStep, ...], done: int, show_ids: bool
) -> str:
    if done >= len(steps):
        return "every step done"
    step = steps[done]
    text = f"now: {step.text.rstrip('.')}"
    if step.goal() > 1:
        text += f" ({step_count(state, step, quest.id)}/{step.goal()})"
    if len(steps) > 1:
        text += f", step {done + 1} of {len(steps)}"
    if step.kind in _ITEM_STEPS and step.item:
        text += f"; {step.item}: {', '.join(_item_spots(state, quest, step.item))}"
    if step.kind is StepKind.FREE and show_ids:
        text += FREE_NOTE
    return text


def _main_lines(state: GameState, quest: Quest, show_ids: bool) -> list[str]:
    campaign = state.campaign
    lines = [f"Main quest: {quest.title}{_tag(show_ids, quest.id)}: {quest.objective}"]
    act = None
    if campaign is not None:
        act = next((a for a in campaign.plan.acts if main_quest_id(a.region) == quest.id), None)
    if campaign is None or act is None:
        return lines
    for route in main_quest(campaign.plan, act.index).routes:
        progress = quest.route(route.id)
        if progress is None:
            continue  # never an undiscovered route
        step = _step_text(state, quest, route.steps, progress.steps_done, show_ids)
        lines.append(f"Known way: {route.title}{_tag(show_ids, route.id)}: {step}")
    return lines


def _task_line(state: GameState, quest: Quest, show_ids: bool) -> str:
    words = _KIND_WORDS.get(quest.kind, "quest")
    head = f"Active {words}: {quest.title}{_tag(show_ids, quest.id)}"
    head += f" for {_npc_name(state, quest.giver_npc_id)}"
    goal = f": {quest.objective.rstrip('.')}" if quest.objective else ""
    if not quest.steps:
        return f"{head}{goal}"
    return f"{head}{goal}; {_step_text(state, quest, quest.steps, quest.steps_done, show_ids)}"


def _offered_line(state: GameState, quest: Quest, show_ids: bool) -> str:
    giver = state.world.npcs.get(quest.giver_npc_id or "")
    by = ""
    if giver is not None:
        by = f", given by {giver.name} at {node_display_name(state, giver.node_id)}"
    goal = f": {quest.objective.rstrip('.')}" if quest.objective else ""
    return f"Offered (not accepted): {quest.title}{_tag(show_ids, quest.id)}{by}{goal}"


def quest_lines(state: GameState, show_ids: bool) -> list[str]:
    world = state.world
    quests = sorted(world.quests.values(), key=lambda q: q.id)
    active = [q for q in quests if q.state is QuestState.ACTIVE]
    lines = [
        ln for q in active if q.kind is QuestKind.MAIN for ln in _main_lines(state, q, show_ids)
    ]
    lines += [_task_line(state, q, show_ids) for q in active if q.kind is not QuestKind.MAIN]
    ask = world.quest_ask
    asked = world.quests.get(ask.quest_id) if ask is not None else None
    if ask is not None and asked is not None:
        who = _npc_name(state, ask.npc_id)
        lines.append(f"{who} is asking now: {asked.title} (the players answer Accept or Not now)")
    lines += [
        _offered_line(state, q, show_ids)
        for q in quests
        if q.state is QuestState.OFFERED and q is not asked
    ]
    lines += [f"Lead: {lead.text}" for lead in world.leads]
    return [*lines, *_finale_lines(state)]


def _finale_lines(state: GameState) -> list[str]:
    finale = finale_open(state)
    if finale is not None:
        a, b = (o.title for o in finale.options)
        return [
            f'FINALE (waiting for the players): {finale.question} Endings: "{a}" or "{b}".'
            " The players choose on their card; never choose for them or tell an ending."
        ]
    ending = chosen_ending(state)
    if ending is not None:
        return [f'FINALE: the party chose "{ending.title}": {ending.text}']
    return []


def route_hint_lines(state: GameState, npc_id: str | None) -> list[str]:
    campaign = state.campaign
    if campaign is None or not npc_id:
        return []
    lines: list[str] = []
    for act in campaign.plan.acts:
        known = state.world.quests.get(main_quest_id(act.region))
        if known is not None and known.state is not QuestState.ACTIVE:
            continue
        for route in main_quest(campaign.plan, act.index).routes:
            if route.hint_npc_id == npc_id:
                first = route.steps[0].text.rstrip(".")
                lines.append(
                    f"You know a way ({route.title}): {first}. Share it when the party asks"
                    " for help or about the trouble here."
                )
    return lines
