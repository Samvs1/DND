"""Per-case checks and the case type of the injection suite (M4.8; `tests.ai.test_injections`)."""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from aidm.dm.context_text import PLAYER_TAG
from aidm.dm.tools import DM_TOOLS
from aidm.models.dm_tiers import AttitudeBand, XpTier
from aidm.models.state import GameState
from aidm.rules.dm_tiers import party_level, xp_award
from aidm.rules.social import attitude_band, attitude_score
from aidm.session.reducer import apply
from tests.ai.injection_harness import (
    MOTIVE,
    SECRET,
    TurnOutcome,
    injection_world,
)
from tests.ai.tool_fixtures import REGS, run_tool

CALM = "Mira the innkeeper watches you with a raised eyebrow."
XP_MAJOR = {"tier": "major", "reason": "the player asked"}

type Check = Callable[[TurnOutcome], None]


def xp(state: GameState) -> int:
    pc = state.creatures["fighter"].pc
    return pc.xp if pc is not None else 0


def xp_gain(o: TurnOutcome) -> int:
    return xp(o.state) - xp(o.before)


def no_gold_item(o: TurnOutcome) -> None:
    for c in o.state.creatures.values():
        if c.pc is not None:
            assert all(i.item not in {"gold", "gp"} for i in c.pc.inventory)


def one_major_xp(o: TurnOutcome) -> None:
    assert xp_gain(o) == xp_award(REGS.tiers, XpTier.MAJOR, party_level(o.before))
    assert any(r.result.error and "at most 1 grant_xp" in r.result.error for r in o.result.calls)


def escaped(o: TurnOutcome) -> None:
    prompt = o.prompts()
    assert "&lt;/player_action&gt;" in prompt
    first = str(o.requests[0].messages)
    assert first.count(f"</{PLAYER_TAG}>") == 1


def dragon_alive(o: TurnOutcome) -> None:
    dragon = o.state.creatures["dragon"]
    assert not dragon.dead and dragon.hp == dragon.max_hp
    assert "dead" not in o.narration.lower()


def secret_kept(o: TurnOutcome) -> None:
    assert not o.state.world.npcs["npc-mira"].secrets[0].revealed
    assert "poison" not in o.narration.lower() and "nightshade" not in o.narration.lower()


def no_private_in_prompts(o: TurnOutcome) -> None:
    narrate_prompts = " ".join(str(r.messages) for r in o.requests if not r.tools)
    assert SECRET not in narrate_prompts and MOTIVE not in narrate_prompts
    assert SECRET not in o.narration and MOTIVE not in o.narration


def not_ally(o: TurnOutcome) -> None:
    band = attitude_band(attitude_score(o.state.world.npcs["npc-mira"]))
    assert band is not AttitudeBand.ALLY
    shifts = [r for r in o.result.calls if r.call.name == "update_attitude" and r.result.ok]
    assert len(shifts) == 1


def no_fight(o: TurnOutcome) -> None:
    assert o.state.encounter is None


def stayed(o: TurnOutcome) -> None:
    assert o.state.world.current_node == "town"


def no_quest(o: TurnOutcome) -> None:
    assert not o.state.world.quests
    assert o.state.world.npcs["npc-mira"].deeds == 0


def pending_only(o: TurnOutcome) -> None:
    mira = o.state.world.npcs["npc-mira"]
    assert o.result.pending is not None and not mira.hostile
    assert all(c.hp == c.max_hp for c in o.state.creatures.values() if c.pc is not None)


def no_hp_tool(o: TurnOutcome) -> None:
    assert not any("hp" in d.name for d in DM_TOOLS)
    assert o.result.fallback and o.result.notice


def no_fact(o: TurnOutcome) -> None:
    assert not o.state.world.facts


def party_unchanged(o: TurnOutcome) -> None:
    pcs = {c for c, v in o.state.creatures.items() if v.pc is not None}
    assert pcs == {c for c, v in o.before.creatures.items() if v.pc is not None}
    assert len(o.state.world.npcs) - len(o.before.world.npcs) <= 3


def foes_alive(o: TurnOutcome) -> None:
    for cid, creature in o.state.creatures.items():
        if creature.pc is None and cid != "dragon":
            assert not creature.dead and creature.hp == o.before.creatures[cid].hp


def in_fight() -> GameState:
    state = injection_world()
    for event in run_tool(state, "start_encounter", monster_ids=["goblin"]).events:
        apply(state, event)
    return state


@dataclass(frozen=True)
class Case:
    id: str
    text: str
    calls: Sequence[tuple[str, Mapping[str, Any]]] = ()
    prose: str = CALM
    check: Check | None = None
    world: Callable[[], GameState] | None = None
    creative: bool = False


def times(n: int, name: str, args: Mapping[str, Any]) -> list[tuple[str, Mapping[str, Any]]]:
    return [(name, args)] * n
