"""M19.4 (owner playtest 2026-10-10): "I move to the ravine" in a fight moves the hero (the same
commands as the phone's Move list), spends no action, and needs no model call."""

from pathlib import Path

from aidm.models.protocol_client import SubmitAction
from aidm.models.protocol_server import Notice
from aidm.rules.zones import zone_neighbors
from tests.session.table_fixtures import (
    assert_replays,
    disabled_llm,
    join,
    of_type,
    running,
    start_fight,
)


async def test_a_typed_move_moves_the_hero_and_keeps_the_action(tmp_path: Path) -> None:
    async with running(disabled_llm(tmp_path)) as (table, _):
        ann = await join(table, "Ann", "fighter")
        bob = await join(table, "Bob", "rogue")
        await start_fight(table, "goblin", "goblin")
        enc = table.state.encounter
        assert enc is not None and table.turn_key is not None
        active = enc.active_id()
        seat = next(s for s in (ann, bob) if table.players[s.player_id].creature_id == active)
        assert active is not None
        me = enc.combatants[active]
        near = next(
            z
            for z, feet in zone_neighbors(enc.zone_map, me.zone_id)
            if feet <= me.economy.movement_left
        )
        name = next(z.name for z in enc.zone_map.zones if z.id == near)
        seat.drain()
        seat.send(SubmitAction(text=f"I move to the {name}"))
        await table.settle()
        now = table.state.encounter
        assert now is not None
        assert now.combatants[active].zone_id == near
        assert now.combatants[active].economy.action  # moving is not the action
        notes = [n.text for n in of_type(seat.drain(), Notice)]
        assert f"You move to {name}." in notes
        assert_replays(table)
