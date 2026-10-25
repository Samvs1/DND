"""Typed gear phrases the M27.10 live probe exposed (no model: the deterministic precheck).

- "I use the rope to force open the lock" used the rope's climbing use (an Athletics boon)
  because "the lock" named nothing the target matcher knew; it now aims at the locked feature,
  so the rope is refused and the AI judges a plain check (the scoped rope rule).
- "I throw my bottle of water at the fire elemental" was left to the model in a fight; the
  precheck now finds the carried waterskin by its substance word (the ONE gear matcher,
  `aidm.dm.gear_words.held_gear`, shared with creative effects), so the item rules throw it.
"""

from pathlib import Path

from aidm.data.srd import srd
from aidm.dm.fake_llm import FakeStep
from aidm.dm.tool_context import ToolContext
from aidm.models.encounter import Side
from aidm.models.events import AnyEvent
from aidm.models.item_events import BoonGained, ItemUsed
from aidm.models.protocol_client import SubmitAction
from aidm.models.state import GameState
from aidm.models.world_events import FeatureIntroduced
from aidm.rules.monster_stats import creature_from_monster
from aidm.session import combat_flow
from tests.ai.tool_fixtures import apply_result, run_tool
from tests.session.table_fixtures import assert_replays, join, menu_down, pick, running
from tests.unit.rules.item_fixtures import DOCKS, at, gear_fight, hero, qty

ROPE = "rope-hempen-50-feet"
WATER = "I throw my bottle of water at the fire elemental"


def _chest(state: GameState) -> str:
    ctx = ToolContext(actor_id="hero")
    result = run_tool(
        state, "introduce_feature", ctx=ctx, kind="container", name="Iron chest", lock_tier="medium"
    )
    apply_result(state, result)
    (event,) = result.events
    assert isinstance(event, FeatureIntroduced)
    return event.feature.id


def _elemental(*gear: str) -> GameState:
    elemental = creature_from_monster(srd().monsters.get("fire-elemental"), "fe")
    return gear_fight(DOCKS, hero(gear=list(gear)), (elemental, Side.HOSTILE, "b"))


async def _typed(
    tmp_path: Path, state: GameState, text: str, *picks: FakeStep
) -> tuple[list[AnyEvent], GameState]:
    """`picks`: the menu chooser's scripted readings (M36.10b); other AI calls fail (no key)."""
    async with running(menu_down(tmp_path, *picks), state) as (table, _):
        seat = await join(table, "Ann", "hero")
        if table.combat_active():

            async def enter() -> None:
                await combat_flow.after_resolution(table, [])

            table.schedule(enter)
            await table.settle()
        seat.send(SubmitAction(text=text))
        await table.settle()
        assert_replays(table)
        return [entry.event for entry in table.log], table.state.model_copy(deep=True)


async def test_m27_rope_to_force_the_lock_is_not_a_climb(tmp_path: Path) -> None:
    state = at(DOCKS, hero(gear=[ROPE]))
    chest = _chest(state)
    events, after = await _typed(tmp_path, state, "I use the rope to force open the lock")
    assert not [e for e in events if isinstance(e, BoonGained | ItemUsed)]  # no climbing boon
    assert after.world.features[chest].lock is not None  # and the lock holds
    assert qty(after, "hero", ROPE) == 1


async def test_m27_typed_bottle_of_water_is_the_waterskin(tmp_path: Path) -> None:
    state = _elemental("waterskin")
    hurl = pick(("throw:waterskin", ["fe"], None))  # the fight menu's improvised throw
    events, after = await _typed(tmp_path, state, WATER, hurl)
    used = [(e.item, e.use_id) for e in events if isinstance(e, ItemUsed)]
    assert used == [("waterskin", "improvised-throw")]  # thrown through the item rules
    assert qty(after, "hero", "waterskin") == 0
