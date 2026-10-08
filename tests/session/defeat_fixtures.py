"""Helpers for the defeat flow tests (M11.1): a solo or duo party, a trap job, playing a fight."""

from aidm.dm.tool_context import ToolContext
from aidm.dm.tool_exec import execute_tool
from aidm.models.commands import EndTurnCommand
from aidm.models.damage import DamagePacket, DamageType
from aidm.models.protocol_client import CombatCommandMsg
from aidm.models.state import GameState
from aidm.rules.damage import resolve_damage
from aidm.session.table import Table
from tests.ai.guard_fixtures import inn_state
from tests.ai.tool_fixtures import tool_call
from tests.session.table_fixtures import Seat


def party_of(*keep: str, hp: dict[str, int] | None = None) -> GameState:
    """`inn_state` with only the heroes in `keep`; `hp` sets HP (raising max HP if needed)."""
    state = inn_state()
    for cid in [c for c in state.creatures if state.creatures[c].pc and c not in keep]:
        del state.creatures[cid]
    for cid, value in (hp or {}).items():
        creature = state.creatures[cid]
        creature.max_hp = max(creature.max_hp, value)
        creature.hp = value
    return state


async def hurt(table: Table, creature_id: str, amount: int) -> None:
    """A trap outside the normal flow: damage applied by a table job."""

    async def job() -> None:
        target = table.state.creatures[creature_id]
        packet = DamagePacket(amount=amount, damage_type=DamageType.PIERCING)
        table.apply_all(resolve_damage(target, [packet]))

    table.schedule(job)
    await table.settle()


async def travel(table: Table, node_id: str) -> None:
    async def job() -> None:
        call = tool_call("move_party", node_id=node_id)
        result = execute_tool(table.state, call, ToolContext("fighter"), table.rng, table.regs)
        assert result.ok, result.error
        table.apply_all(list(result.events))

    table.schedule(job)
    await table.settle()


async def end_turns_until_over(table: Table, seats: list[Seat], limit: int = 200) -> None:
    """Every prompted hero just ends its turn, until the fight is over (or `limit` steps)."""
    for _ in range(limit):
        enc = table.state.encounter
        if not table.in_combat or enc is None or table.turn_key is None:
            return
        active = enc.active_id() or ""
        seat = next(s for s in seats if table.players[s.player_id].creature_id == active)
        seat.send(CombatCommandMsg(command=EndTurnCommand(actor_id=active)))
        await table.settle()
