"""M19.3 (owner playtest 2026-10-10): a typed pick-up of an item lying here really picks it up,
with no model call, and the table hears one short engine line."""

from pathlib import Path

from aidm.models.protocol_client import Drop, SubmitAction
from aidm.models.protocol_server import NarrationChunkMsg
from aidm.rules.item_grants import carried_qty
from tests.session.table_fixtures import assert_replays, fake_llm, join, of_type, running


async def test_dropped_item_can_be_picked_up_again_by_typing(tmp_path: Path) -> None:
    llm, fake = fake_llm(tmp_path)
    async with running(llm) as (table, _):
        ann = await join(table, "Ann", "fighter")
        hero = table.state.creatures["fighter"]
        assert hero.pc is not None
        item = next(i.item for i in hero.pc.inventory if i.item not in ("chain-mail", "shield"))
        before = carried_qty(hero, item)
        ann.send(Drop(item_id=item))
        await table.settle()
        lying = [i for i in table.state.world.items.values() if i.catalog_id == item]
        assert len(lying) == 1 and carried_qty(table.state.creatures["fighter"], item) == before - 1
        ann.drain()
        calls = len(fake.requests)
        ann.send(SubmitAction(text=f"I pick up the {lying[0].name.lower()}"))
        await table.settle()
        assert carried_qty(table.state.creatures["fighter"], item) == before
        assert lying[0].id not in table.state.world.items
        told = " ".join(m.text for m in of_type(ann.drain(), NarrationChunkMsg))
        assert f"picks up the {lying[0].name.lower()}" in told
        assert len(fake.requests) == calls  # deterministic: no model call
        assert_replays(table)
