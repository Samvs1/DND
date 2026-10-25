"""Downed heroes outside a fight at the table (M20.2, playtest 3: the warlock lay at 0 HP from the
ghast fight to the dragon fight; nothing outside a fight could raise her)."""

from pathlib import Path

from aidm.models.events import HpChanged, Stabilized
from aidm.models.protocol_client import HelpUp, SubmitAction
from aidm.models.protocol_server import ErrorMsg
from aidm.rules.death import is_dying
from aidm.session.table import Table
from tests.session.defeat_fixtures import end_turns_until_over, hurt
from tests.session.table_fixtures import (
    assert_replays,
    drain_queue,
    fake_llm,
    join,
    menu_llm,
    of_type,
    pick,
    running,
    start_fight,
)


def _foe(table: Table) -> str:
    return next(c.id for c in table.state.creatures.values() if c.pc is None and not c.dead)


async def test_won_fight_leaves_the_dying_stable_and_an_ally_helps_them_up(
    tmp_path: Path,
) -> None:
    llm, _ = fake_llm(tmp_path)
    async with running(llm) as (table, _clock):
        ann = await join(table, "Ann", "fighter")
        bob = await join(table, "Bob", "rogue")
        await start_fight(table, "wolf")
        await hurt(table, "rogue", table.state.creatures["rogue"].hp)
        await hurt(table, _foe(table), 999)
        await end_turns_until_over(table, [ann, bob])
        assert not table.in_combat
        rogue = table.state.creatures["rogue"]
        assert rogue.hp == 0 and not rogue.dead and not is_dying(rogue)
        assert any(isinstance(e.event, Stabilized) for e in table.log)
        ann.send(HelpUp(target_id="rogue"))
        await table.settle()
        assert table.state.creatures["rogue"].hp == 1
        assert_replays(table)


async def test_typed_help_up_and_refusals(tmp_path: Path) -> None:
    llm, _ = menu_llm(tmp_path, pick(("help_up", ["rogue"], None)))  # the menu chooser's
    async with running(llm) as (table, _clock):
        ann = await join(table, "Ann", "fighter")
        bob = await join(table, "Bob", "rogue")
        await hurt(table, "rogue", table.state.creatures["rogue"].hp)
        drain_queue(bob.conn)
        bob.send(HelpUp(target_id="fighter"))
        await table.settle()
        refused = of_type(drain_queue(bob.conn), ErrorMsg)
        assert table.state.creatures["fighter"].hp > 0 and refused  # a downed hero cannot help
        ann.send(SubmitAction(text="I help Brannoc to his feet"))
        await table.settle()
        healed = [e.event for e in table.log if isinstance(e.event, HpChanged)]
        assert table.state.creatures["rogue"].hp == 1 and healed[-1].creature_id == "rogue"
        assert_replays(table)
