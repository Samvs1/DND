"""What met a quest step, as a short line (M29.5b G20, M29.7c R1). Pure.

A step can be met by earlier play (an item already carried, a fight already won, the party
standing with the person it names); the storyteller is told WHAT met it, so it tells no new deed
and the player sees why the step is done (p4 451: accepting a quest completed it at once).

Public API: `step_reason(state, step, owner) -> str | None` (None for a free step, judged by
the storyteller, or when the state does not show the step met).
"""

from collections.abc import Callable

from aidm.models.quests import QuestStep, StepKind
from aidm.models.state import GameState
from aidm.rules.quest_learn import learn_source
from aidm.rules.quest_steps import step_met
from aidm.rules.scene import node_display_name
from aidm.rules.secrets import item_key

type _Reason = Callable[[GameState, QuestStep], str | None]


def _npc(state: GameState, npc_id: str | None) -> str:
    npc = state.world.npcs.get(npc_id or "")
    return npc.name if npc is not None else "they"


def _places(state: GameState, step: QuestStep) -> str:
    return ", ".join(node_display_name(state, n) for n in step.nodes)


def _visit(state: GameState, step: QuestStep) -> str:
    return f"the party has been to {_places(state, step)}"


def _clear(state: GameState, step: QuestStep) -> str:
    return f"the fight at {_places(state, step)} was won"


def _defeat(state: GameState, step: QuestStep) -> str:
    return f"{_npc(state, step.npc)} has fallen"


def _holder(state: GameState, item: str) -> str | None:  # M29.5b G20 wording
    wanted = item_key(item)
    for c in state.creatures.values():
        if c.pc is None or c.dead:
            continue
        names = [k.name for k in c.pc.keepsakes] + [row.item for row in c.pc.inventory]
        if any(item_key(n) == wanted for n in names):
            return f"{c.name} already carries the {item}"
    for npc in state.world.npcs.values():
        if any(item_key(k.name) == wanted and k.quest_id is not None for k in npc.keepsakes):
            return f"the party already handed the {item} to {npc.name}"
    return None


def _obtain(state: GameState, step: QuestStep) -> str | None:
    return _holder(state, step.item) if step.item else None


def _deliver(state: GameState, step: QuestStep) -> str:
    return f"{_npc(state, step.npc)} holds the {step.item}"


def _meet(state: GameState, step: QuestStep) -> str:
    return f"the party stands with {_npc(state, step.npc)}"


def _win_over(state: GameState, step: QuestStep) -> str:
    return f"{_npc(state, step.npc)} trusts the party"


def _learn(state: GameState, step: QuestStep) -> str | None:
    return learn_source(state, step.tag or "")


def _free(state: GameState, step: QuestStep) -> str | None:
    return None


def _pay(state: GameState, step: QuestStep) -> str:
    return f"{_npc(state, step.npc)} has been paid"


_REASONS: dict[StepKind, _Reason] = {
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


def step_reason(state: GameState, step: QuestStep, owner: str) -> str | None:
    if not step_met(state, step, owner):
        return None
    return _REASONS[step.kind](state, step)
