"""Creative actions use the item rules (M27.6 part B, docs/next/GOAL_ITEMS.md "D: creative actions
use the same rules"): gear a free-form action leans on is carried or refused, a carried one is
spent per its data, a substance weakness is the engine's, and the AI sees each foe's traits.
FakeLLM only."""

import random
from pathlib import Path
from typing import Any

from aidm.data.srd import srd
from aidm.dm.adjudicator import CREATIVE_ACTION_TOOLS, AdjudicationOptions, adjudicate
from aidm.dm.context import SectionKey, build_context
from aidm.dm.context_text import ContextPurpose
from aidm.dm.creative_gear import GEAR_REFUSED
from aidm.dm.fake_llm import FakeStep, fake_tool_call
from aidm.dm.narrator import TRIED, unpack_source
from aidm.dm.tool_context import ToolContext
from aidm.models.encounter import Side
from aidm.models.events import DiceRolled, InventoryChanged
from aidm.models.item_events import ItemUsed
from aidm.models.state import GameState
from aidm.rules.monster_stats import creature_from_monster
from aidm.session.reducer import apply
from tests.ai.fake_scripts import fake_client
from tests.ai.tool_fixtures import REGS, apply_result, run_tool
from tests.unit.rules.combat_fixtures import monster
from tests.unit.rules.item_fixtures import DOCKS, at, gear_fight, hero, qty

THROW = "I throw my waterskin at the goblin"


def _effect(**extra: Any) -> dict[str, Any]:
    return {"actor": "hero", "target": "gob", "effect_kind": "minor_damage", **extra}


def _goblin_fight(*gear: str, keepsakes: tuple[str, ...] = ()) -> GameState:
    me = hero(gear=list(gear), keepsakes=keepsakes)
    return gear_fight(DOCKS, me, (monster("gob", ac=12), Side.HOSTILE, "b"))


def _said(text: str) -> ToolContext:
    return ToolContext(actor_id="hero", player_text=text)


async def test_creative_throw_of_an_item_you_lack_is_refused(tmp_path: Path) -> None:
    state = _goblin_fight()
    script: list[FakeStep] = [fake_tool_call("creative_effect", _effect(item="waterskin"))]
    client, _ = fake_client(tmp_path, script)
    result = await adjudicate(
        state,
        "hero",
        THROW,
        client,
        AdjudicationOptions(creative_action=True),
        random.Random(3),
        REGS,
        lambda event: apply(state, event),
    )
    error = result.calls[0].result.error
    assert error is not None and error.startswith(GEAR_REFUSED) and "does not carry" in error
    assert not result.events and state.creatures["gob"].hp == 10
    _, facts, _ = unpack_source(result)
    assert TRIED.format(why=error) in facts  # told as an attempt
    lacked = run_tool(state, "use_item", ctx=_said(THROW), actor="hero", item="waterskin")
    assert lacked.error is not None and "does not carry" in lacked.error


def test_creative_effect_naming_gear_it_lacks_is_refused() -> None:
    state = _goblin_fight()
    named = run_tool(state, "creative_effect", ctx=_said("I strike"), **_effect(item="rope"))
    assert named.error is not None and "does not carry rope" in named.error
    chair = _said("I throw a chair at the goblin")  # names no gear: the creative effect runs
    scenery = run_tool(state, "creative_effect", ctx=chair, **_effect())
    assert scenery.error is None and state.creatures["gob"].hp == 10
    assert not any(isinstance(e, ItemUsed) for e in scenery.events)
    theirs = _said("I throw the rope at the goblin")  # not said as the hero's own: no refusal
    assert run_tool(state, "creative_effect", ctx=theirs, **_effect()).error is None
    pc = state.creatures["hero"].pc
    assert pc is not None
    pc.inventory = []
    pc.equipped.shield = "shield"  # worn gear counts as carried
    bash = _said("I use my shield on the goblin")
    shoved = run_tool(state, "creative_effect", ctx=bash, **_effect(effect_kind="push"))
    assert shoved.error is None or GEAR_REFUSED not in shoved.error


def test_creative_throw_consumes_the_item() -> None:
    state = _goblin_fight("waterskin")
    # "my bottle of water" is the carried waterskin (its substance, water, is named)
    ctx = _said("I throw my bottle of water at the goblin")  # the model names the item
    result = run_tool(state, "creative_effect", ctx=ctx, **_effect(item="waterskin"))
    assert result.error is None, result.error
    used = [e for e in result.events if isinstance(e, ItemUsed)]
    assert [u.use_id for u in used] == ["improvised-throw"]
    assert any(isinstance(e, InventoryChanged) and e.delta == -1 for e in result.events)
    apply_result(state, result)
    assert qty(state, "hero", "waterskin") == 0


def test_a_keepsake_named_like_a_catalogue_item_is_refused() -> None:
    state = _goblin_fight(keepsakes=("Waterskin",))
    result = run_tool(state, "creative_effect", ctx=_said(THROW), **_effect(item="Waterskin"))
    assert result.error is not None and "keepsake" in result.error
    assert result.events == ()
    tool = run_tool(
        state, "use_item", ctx=_said(THROW), actor="hero", item="Waterskin", target="gob"
    )
    assert tool.error is not None and "keepsake" in tool.error


def test_splashing_water_on_a_fire_elemental_out_of_a_fight_is_the_weakness() -> None:
    state = at(DOCKS, hero(gear=["waterskin"]))
    state.creatures["fe"] = creature_from_monster(srd().monsters.get("fire-elemental"), "fe")
    args = _effect(target="fe", effect_kind="condition", condition="blinded", item="waterskin")
    result = run_tool(state, "creative_effect", ctx=_said("I splash it"), **args)
    assert result.error is None, result.error
    weak = [e for e in result.events if isinstance(e, DiceRolled)]
    assert [(e.label, e.roll.total) for e in weak] == [("Water Susceptibility", 1)]  # SRD 5.1
    apply_result(state, result)
    assert state.creatures["fe"].hp == 101 and qty(state, "hero", "waterskin") == 0


def test_use_item_is_a_creative_action_tool() -> None:
    assert "use_item" in CREATIVE_ACTION_TOOLS


def test_fight_context_lists_monster_traits() -> None:
    elemental = creature_from_monster(srd().monsters.get("fire-elemental"), "fe")
    state = gear_fight(
        DOCKS, hero(), (elemental, Side.HOSTILE, "b"), (monster("gob"), Side.HOSTILE, "c")
    )
    pack = build_context(state, ContextPurpose.ADJUDICATE, "hero", "I look at it")
    manifest = pack.section(SectionKey.MANIFEST)
    assert manifest is not None
    traits = [line for line in manifest.lines if line.startswith("Foe traits")]
    assert traits == [
        "Foe traits - Fire Elemental: Fire Form, Illumination, Water Susceptibility (weak to water)"
    ]
    calm = at(DOCKS, hero())
    calm_pack = build_context(calm, ContextPurpose.ADJUDICATE, "hero", "I look around")
    calm_manifest = calm_pack.section(SectionKey.MANIFEST)
    assert calm_manifest is not None
    assert not any(line.startswith("Foe traits") for line in calm_manifest.lines)
