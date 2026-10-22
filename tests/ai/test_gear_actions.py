"""The AI and typed gear actions (M27.5, docs/next/GOAL_ITEMS.md "Design", "Light and darkness",
"Other rules"): `use_item`, the scoped rope rule, `grant_item` refusing usable gear, putting a
light out, the light-versus-stealth engine lines and the lock guard. FakeLLM only."""

import random
from pathlib import Path
from typing import Any

from aidm.dm.adjudicator import AdjudicationOptions, AdjudicationResult, adjudicate
from aidm.dm.context import SectionKey, build_context
from aidm.dm.context_text import CLOSED_WORLD, ContextPurpose, system_text
from aidm.dm.event_text import event_lines
from aidm.dm.fake_llm import FakeStep, fake_tool_call
from aidm.dm.guard import check_prose
from aidm.dm.guard_types import ViolationKind
from aidm.dm.item_text import LIGHT_WARNING, SEEN_LIGHT
from aidm.dm.narrator import TRIED, unpack_source
from aidm.dm.tool_context import ToolContext
from aidm.models.dice import AdvState
from aidm.models.encounter_events import EncounterStarted
from aidm.models.events import AnyEvent, CheckResolved, EconomyChanged, InventoryChanged
from aidm.models.item_events import FeatureUnlocked, ItemUsed, LightEnded, PlaceAlerted
from aidm.models.state import GameState
from aidm.models.world_events import FeatureIntroduced
from aidm.rules.light import hero_light, put_out
from aidm.session.reducer import apply
from tests.ai.fake_scripts import fake_client
from tests.ai.tool_fixtures import REGS, apply_result, run_tool
from tests.unit.rules.item_fixtures import CAVE, DOCKS, at, gear_fight, hero, qty, run, use

HERO = ToolContext(actor_id="hero")
ROPE = "rope-hempen-50-feet"


def _chest(state: GameState) -> str:
    result = run_tool(
        state, "introduce_feature", ctx=HERO, kind="container", name="Iron chest", lock_tier="easy"
    )
    apply_result(state, result)
    (event,) = result.events
    assert isinstance(event, FeatureIntroduced)
    return event.feature.id


def _check(skill: str, **extra: Any) -> dict[str, Any]:
    return {"actor": "hero", "ability_or_skill": skill, "dc_tier": "medium", **extra}


async def _adjudicate(
    tmp_path: Path, state: GameState, text: str, script: list[FakeStep]
) -> AdjudicationResult:
    client, _ = fake_client(tmp_path, script)
    return await adjudicate(
        state,
        "hero",
        text,
        client,
        AdjudicationOptions(),
        random.Random(3),
        REGS,
        lambda event: apply(state, event),
    )


def _checks(result: AdjudicationResult) -> list[CheckResolved]:
    return [e for e in result.events if isinstance(e, CheckResolved)]


async def test_rope_cannot_force_a_lock(tmp_path: Path) -> None:
    state = at(DOCKS, hero(gear=[ROPE]))
    fid = _chest(state)
    tried = run_tool(state, "use_item", ctx=HERO, actor="hero", item=ROPE, target=fid)
    assert tried.error is not None and "cannot open the Iron chest" in tried.error
    assert tried.events == ()
    text = "I use my rope to force open the iron chest"
    script: list[FakeStep] = [
        fake_tool_call("request_check", _check("athletics", advantage="advantage"))
    ]
    result = await _adjudicate(tmp_path, state, text, script)
    (check,) = _checks(result)
    assert check.result.roll.adv is AdvState.NORMAL  # the rope rule dropped the AI's advantage
    assert "no help" in result.calls[0].result.summary
    assert not any(isinstance(e, FeatureUnlocked) for e in result.events)
    assert state.world.features[fid].lock is not None


async def test_rope_to_tie_up_a_goblin_keeps_the_ai_call(tmp_path: Path) -> None:
    state = at(DOCKS, hero(gear=[ROPE]))
    _chest(state)  # a lock in the room does not make every rope check a lock check
    text = "I tie up the goblin with my rope"
    for skill in ("sleight-of-hand", "athletics"):
        script: list[FakeStep] = [
            fake_tool_call("request_check", _check(skill, advantage="advantage"))
        ]
        result = await _adjudicate(tmp_path, state, text, script)
        (check,) = _checks(result)
        assert check.result.roll.adv is AdvState.ADVANTAGE, skill


async def test_found_rope_is_not_granted(tmp_path: Path) -> None:
    state = at(DOCKS, hero())
    script: list[FakeStep] = [
        fake_tool_call("grant_item", {"catalog_id": ROPE, "qty": 1, "reason": "found"})
    ]
    result = await _adjudicate(tmp_path, state, "I search the shed and find a rope", script)
    assert result.calls[0].result.error is not None
    assert "usable gear" in (result.calls[0].result.error or "")
    assert not any(isinstance(e, InventoryChanged) for e in result.events)
    assert qty(state, "hero", ROPE) == 0


async def test_keepsake_rope_is_not_usable(tmp_path: Path) -> None:
    state = at(DOCKS, hero(keepsakes=["Rope"]))
    tried = run_tool(state, "use_item", ctx=HERO, actor="hero", item="Rope")
    assert tried.error is not None and "keepsake" in tried.error and tried.events == ()
    script: list[FakeStep] = [
        fake_tool_call("request_check", _check("athletics", advantage="advantage"))
    ]
    result = await _adjudicate(tmp_path, state, "I climb down the wall with my rope", script)
    (check,) = _checks(result)
    assert check.result.roll.adv is AdvState.NORMAL


async def test_real_rope_climbs_through_use_item_with_its_boon(tmp_path: Path) -> None:
    state = at(DOCKS, hero(gear=[ROPE]))
    script: list[FakeStep] = [
        fake_tool_call("use_item", {"actor": "hero", "item": ROPE}),
        fake_tool_call("request_check", _check("athletics")),
    ]
    result = await _adjudicate(tmp_path, state, "I climb down the wall with my rope", script)
    assert any(isinstance(e, ItemUsed) for e in result.events)
    script = [fake_tool_call("request_check", _check("athletics"))]
    climbed = await _adjudicate(tmp_path, state, "I climb down", script)
    (check,) = _checks(climbed)
    assert check.result.roll.adv is AdvState.ADVANTAGE and "Rope" in check.result.adv_why


async def test_refused_use_is_told_to_the_narrator_as_an_attempt(tmp_path: Path) -> None:
    state = at(DOCKS, hero(gear=["torch"]))
    script: list[FakeStep] = [fake_tool_call("use_item", {"actor": "hero", "item": "torch"})]
    result = await _adjudicate(tmp_path, state, "I light my torch", script)
    error = result.calls[0].result.error
    assert error is not None and "not dark" in error
    _, facts, _ = unpack_source(result)
    assert TRIED.format(why=error) in facts
    assert qty(state, "hero", "torch") == 1  # a refusal consumes nothing


def test_narration_never_opens_a_lock_without_unlock() -> None:
    state = at(DOCKS, hero(gear=["thieves-tools"]))
    fid = _chest(state)
    opened = "The lock clicks and the lid of the iron chest swings open."
    report = check_prose(opened, state)
    assert [v.kind for v in report.violations] == [ViolationKind.LOCK_OPENED]
    for fine in (
        "You try to open the iron chest, but the lock holds.",
        "The iron chest stays shut.",
        "Hero kneels by the iron chest and sets to work on the lock.",
    ):
        assert check_prose(fine, state).ok, fine
    apply(state, FeatureUnlocked(feature_id=fid, creature_id="hero", method="pick"))
    assert check_prose(opened, state).ok


def test_put_out_torch_is_spent_lantern_relights() -> None:
    state = at(CAVE, hero(gear=["torch", "lantern-hooded"]))
    run(state, use(state, "torch"))
    assert qty(state, "hero", "torch") == 0 and hero_light(state, "hero") is not None
    doused = put_out(state, "hero")
    assert doused == [LightEnded(creature_id="hero", reason="doused", item="torch")]
    run(state, doused)
    assert hero_light(state, "hero") is None and qty(state, "hero", "torch") == 0
    assert state.world.alerted == CAVE  # putting it out does not un-alert the place
    for _ in range(2):  # a lantern can be lit, put out and lit again
        run(state, use(state, "lantern-hooded"))
        assert hero_light(state, "hero") is not None
        run(state, put_out(state, "hero"))
    assert qty(state, "hero", "lantern-hooded") == 1
    assert put_out(state, "hero")[0].type == "item_use_refused"  # no light left to put out


def test_put_out_in_a_fight_is_free() -> None:
    state = gear_fight(CAVE, hero(gear=["lantern-hooded"]))
    lit = use(state, "lantern-hooded")
    assert any(isinstance(e, EconomyChanged) for e in lit)  # lighting is a bonus action
    run(state, lit)
    doused = put_out(state, "hero")
    assert not any(isinstance(e, EconomyChanged) for e in doused)
    run(state, doused)
    assert hero_light(state, "hero") is None


def test_light_warning_line_once_per_lighting() -> None:
    state = at(CAVE, hero(gear=["lantern-hooded"]))
    lit = use(state, "lantern-hooded")
    run(state, lit)
    lines = event_lines(state, lit)
    assert sum(LIGHT_WARNING in line for line in lines) == 1
    assert any(isinstance(e, PlaceAlerted) and e.reason == "light" for e in lit)
    again = use(state, "lantern-hooded")  # refused: already lit, nothing told
    assert not any(LIGHT_WARNING in line for line in event_lines(state, again))
    doused = put_out(state, "hero")
    run(state, doused)
    assert event_lines(state, doused) == ["Hero puts out the lantern."]
    relit = use(state, "lantern-hooded")
    run(state, relit)
    assert sum(LIGHT_WARNING in line for line in event_lines(state, relit)) == 1


def test_fight_start_says_light_gave_you_away() -> None:
    fought = gear_fight(CAVE, hero())
    assert fought.encounter is not None
    started = EncounterStarted(encounter=fought.encounter)
    state = at(CAVE, hero(gear=["torch"]))
    assert event_lines(state, [started]) == ["A fight breaks out."]
    run(state, use(state, "torch"))
    assert state.world.alerted_by == "light"
    assert event_lines(state, [started]) == [f"A fight breaks out. {SEEN_LIGHT}"]
    noisy = at(CAVE, hero())
    apply(noisy, PlaceAlerted(node=CAVE))  # a forced lock: noise, not a light
    assert event_lines(noisy, [started]) == ["A fight breaks out."]


def test_old_place_alerted_events_default_to_noise() -> None:
    event = PlaceAlerted.model_validate({"type": "place_alerted", "node": CAVE})
    assert event.reason == "noise"
    state = at(CAVE, hero())
    payload: list[AnyEvent] = [event]
    run(state, payload)
    assert state.world.alerted_by == "noise"


def test_adjudicator_sees_usable_gear_here_and_the_gear_rule() -> None:
    state = at(CAVE, hero(gear=["torch", ROPE]))
    pack = build_context(state, ContextPurpose.ADJUDICATE, "hero", "I look around")
    manifest = pack.section(SectionKey.MANIFEST)
    assert manifest is not None
    gear = [line for line in manifest.lines if line.startswith("Usable gear of Hero")]
    assert gear and "Torch [torch]: light this dark place" in gear[0]
    assert "Rope [rope-hempen-50-feet]: climb or cross here" in gear[0]
    assert any("this place is dark, unlit" in line for line in manifest.lines)
    assert manifest.lines[-1] == CLOSED_WORLD
    assert "gear advantage comes only from use_item" in system_text(ContextPurpose.ADJUDICATE)
    told = build_context(state, ContextPurpose.NARRATE, "hero").section(SectionKey.MANIFEST)
    assert told is not None and not any("Usable gear" in line for line in told.lines)
