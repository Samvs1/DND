"""Locks through the DM tools (M27.4): `introduce_feature` repairs a lock that may not stay,
`request_check` naming a locked feature is a lock check at the lock's tier, and the manifest says
a feature is locked."""

from aidm.dm.context_sections import manifest_lines
from aidm.dm.tool_context import ToolContext, ToolResult
from aidm.models.character import InventoryItem
from aidm.models.checks import DcTier
from aidm.models.events import CheckResolved
from aidm.models.item_events import FeatureUnlocked, PlaceAlerted
from aidm.models.state import GameState
from aidm.models.world_events import FeatureIntroduced, PartyMoved
from aidm.rules.checks import dc_for_tier
from aidm.rules.scene import current_scene
from aidm.session.reducer import apply
from tests.ai.tool_fixtures import apply_result, run_tool
from tests.unit.rules.item_fixtures import DOCKS, at, hero

HERO = ToolContext(actor_id="hero")
GATEWAY = "sunken-vestry"


def _state(*gear: str) -> GameState:
    return at(DOCKS, hero(gear=list(gear)))


def _introduce(
    state: GameState, kind: str, name: str = "Iron chest", *, lock_tier: str
) -> ToolResult:
    result = run_tool(
        state, "introduce_feature", ctx=HERO, kind=kind, name=name, lock_tier=lock_tier
    )
    assert result.error is None, result.error
    apply_result(state, result)
    return result


def _feature_of(result: ToolResult) -> str:
    (event,) = result.events
    assert isinstance(event, FeatureIntroduced)
    return event.feature.id


def test_introduce_feature_places_a_lock_on_a_cache() -> None:
    state = _state()
    state.world.region_tier = 2  # M29.6b: act 1 caps a new lock at medium
    result = _introduce(state, "cache", lock_tier="hard")
    lock = state.world.features[_feature_of(result)].lock
    assert lock is not None and lock.dc_tier is DcTier.HARD and lock.opens.value == "cache"
    assert "(locked, hard)" in result.summary


def test_introduce_feature_repairs_a_lock_on_a_passage_or_at_the_gateway() -> None:
    state = _state()
    passage = _introduce(state, "passage", name="Low tunnel", lock_tier="easy")
    assert state.world.features[_feature_of(passage)].lock is None
    assert "no lock" in passage.summary
    apply(state, PartyMoved(from_node=DOCKS, to_node=GATEWAY, scene_index=2))
    door = _introduce(state, "door", name="Vestry door", lock_tier="medium")
    assert state.world.features[_feature_of(door)].lock is None
    assert "gateway" in door.summary


def test_introduce_feature_never_locks_away_a_quest_item() -> None:
    state = _state()
    result = _introduce(state, "container", name="Choir tide-orders", lock_tier="medium")
    assert state.world.features[_feature_of(result)].lock is None


def test_request_check_forces_a_locked_feature_at_the_lock_tier() -> None:
    state = _state("crowbar")
    fid = _feature_of(_introduce(state, "container", lock_tier="easy"))
    forced = run_tool(
        state,
        "request_check",
        ctx=HERO,
        seed=3,
        actor="hero",
        ability_or_skill="athletics",
        dc_tier="nearly_impossible",  # the AI's tier never applies to a lock
        advantage="advantage",  # nor its advantage flag
        feature=fid,
    )
    assert forced.error is None, forced.error
    (check,) = [e for e in forced.events if isinstance(e, CheckResolved)]
    assert check.result.dc == dc_for_tier(DcTier.EASY)
    assert check.result.adv_why == ("Crowbar",)
    assert any(isinstance(e, PlaceAlerted) for e in forced.events)
    assert "lock" in forced.summary


def test_a_key_opens_through_request_check_and_other_checks_wait() -> None:
    state = _state()
    fid = _feature_of(_introduce(state, "container", lock_tier="medium"))
    look = run_tool(
        state,
        "request_check",
        ctx=HERO,
        actor="hero",
        ability_or_skill="investigation",
        dc_tier="easy",
        feature=fid,
    )
    assert look.error is not None and "locked" in look.error and look.events == ()
    pc = state.creatures["hero"].pc
    assert pc is not None
    pc.inventory.append(InventoryItem(item="chest-key", qty=1))
    opened = run_tool(
        state,
        "request_check",
        ctx=HERO,
        actor="hero",
        ability_or_skill="investigation",
        dc_tier="easy",
        feature=fid,
    )
    assert opened.events == (
        FeatureUnlocked(feature_id=fid, creature_id="hero", method="key", item="chest-key"),
    )
    assert "chest-key" in opened.summary


def test_the_manifest_marks_a_locked_feature() -> None:
    state = _state()
    _introduce(state, "container", lock_tier="medium")
    lines = manifest_lines(state, current_scene(state), show_ids=False)
    assert any("Iron chest (container, locked: medium)" in line for line in lines)
