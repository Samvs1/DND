"""Locks (M27.4, GOAL_ITEMS "Locks"): a fitting key, thieves' tools or force; placement repair."""

import json

from aidm.models.abilities import Ability, Skill
from aidm.models.checks import DcTier
from aidm.models.events import AnyEvent, CheckResolved
from aidm.models.item_events import FeatureUnlocked, ItemUsed, PlaceAlerted
from aidm.models.state import Creature, GameState
from aidm.models.world import FeatureKind, LockInfo, WorldFeature
from aidm.models.world_events import FeatureIntroduced
from aidm.rules.checks import PROF_PART, dc_for_tier
from aidm.rules.locks import MAX_LOCK_TIER, lock_check, lock_problem, placed_lock
from tests.unit.rules.combat_fixtures import ScriptedRng
from tests.unit.rules.item_fixtures import DOCKS, at, hero, refusal, run, use

CHEST = "feat-chest"
GATEWAY = "sunken-vestry"  # the sample campaign's act 1 gateway


def _feature(
    kind: FeatureKind = FeatureKind.CONTAINER,
    *,
    name: str = "Iron chest",
    node: str = DOCKS,
    tier: DcTier = DcTier.MEDIUM,
) -> WorldFeature:
    return WorldFeature(
        id=CHEST, kind=kind, name=name, node_id=node, lock=LockInfo(dc_tier=tier, opens=kind)
    )


def _locked(*gear: str, tools: tuple[str, ...] = ()) -> GameState:
    state = at(DOCKS, hero(gear=list(gear), tools=tools))
    run(state, [FeatureIntroduced(feature=_feature())])
    return state


def _of[T](events: list[AnyEvent], kind: type[T]) -> list[T]:
    return [e for e in events if isinstance(e, kind)]


def _try(
    rng: ScriptedRng,
    state: GameState,
    actor: Creature,
    feature: WorldFeature,
    what: Skill | Ability,
) -> list[AnyEvent]:
    outcome = lock_check(rng, state, actor, feature, what, "")
    assert not isinstance(outcome, str), outcome
    return outcome


def _refused(state: GameState, what: Skill) -> str:
    outcome = lock_check(ScriptedRng(), state, state.creatures["hero"], _feature(), what, "")
    assert isinstance(outcome, str)
    return outcome


def _check(events: list[AnyEvent]) -> CheckResolved:
    (check,) = _of(events, CheckResolved)
    return check


def test_a_fitting_key_opens_the_lock_without_a_check() -> None:
    state = _locked("chest-key", "thieves-tools")
    events = use(state, "thieves-tools", CHEST, rng=ScriptedRng())
    assert events == [
        FeatureUnlocked(feature_id=CHEST, creature_id="hero", method="key", item="chest-key")
    ]
    hero_ = state.creatures["hero"]
    assert _try(ScriptedRng(), state, hero_, _feature(), Skill.ATHLETICS) == events
    run(state, events)
    assert state.world.features[CHEST].lock is None


def test_a_key_of_another_kind_does_not_fit() -> None:
    state = _locked("iron-key")  # doors and passages only
    events = _try(ScriptedRng(1), state, state.creatures["hero"], _feature(), Ability.STR)
    assert not _of(events, FeatureUnlocked)


def test_thieves_tools_pick_the_lock_with_the_tool_proficiency() -> None:
    state = _locked("thieves-tools", tools=("thieves-tools",))
    events = use(state, "thieves-tools", CHEST, rng=ScriptedRng(20))
    check = _check(events)
    assert check.result.dc == dc_for_tier(DcTier.MEDIUM)
    assert check.result.tier is DcTier.MEDIUM
    prof = hero().proficiency_bonus  # tool proficient, not skilled: PROF once (RULES_DECISIONS)
    assert [p.value for p in check.result.parts if p.name == PROF_PART] == [prof]
    assert _of(events, FeatureUnlocked)[0].method == "pick"
    assert not _of(events, PlaceAlerted)  # picking is quiet
    run(state, events)
    assert state.world.features[CHEST].lock is None


def test_a_failed_pick_keeps_the_lock_and_can_be_retried() -> None:
    state = _locked("thieves-tools")
    events = use(state, "thieves-tools", CHEST, rng=ScriptedRng(1))
    assert not _check(events).result.success
    assert not _of(events, FeatureUnlocked)
    run(state, events)
    assert state.world.features[CHEST].lock is not None
    assert _of(use(state, "thieves-tools", CHEST, rng=ScriptedRng(20)), FeatureUnlocked)


def test_forcing_with_a_crowbar_has_named_advantage_and_is_noisy() -> None:
    state = _locked("crowbar")
    events = use(state, "crowbar", CHEST, rng=ScriptedRng(1, 20))
    check = _check(events)
    assert check.result.adv_why == ("Crowbar",)
    assert check.result.skill is Skill.ATHLETICS
    assert _of(events, FeatureUnlocked)[0].method == "force"
    assert _of(events, PlaceAlerted) == [PlaceAlerted(node=DOCKS)]
    assert _of(events, ItemUsed)


def test_forcing_without_a_crowbar_is_a_plain_noisy_check() -> None:
    state = _locked()
    events = _try(ScriptedRng(20), state, state.creatures["hero"], _feature(), Skill.ATHLETICS)
    assert _check(events).result.adv_why == ()  # one d20 only: no advantage
    assert _of(events, FeatureUnlocked)[0].item is None
    assert _of(events, PlaceAlerted) == [PlaceAlerted(node=DOCKS)]


def test_a_failed_force_is_noisy_and_can_always_be_retried() -> None:
    state = _locked("crowbar")
    failed = use(state, "crowbar", CHEST, rng=ScriptedRng(1, 1))
    assert not _check(failed).result.success
    assert _of(failed, PlaceAlerted) and not _of(failed, FeatureUnlocked)
    run(state, failed)
    again = use(state, "crowbar", CHEST, rng=ScriptedRng(20, 20))
    assert _of(again, FeatureUnlocked)
    assert not _of(again, PlaceAlerted)  # already alerted


def test_a_climbing_rope_boon_does_not_force_a_lock() -> None:
    state = _locked("rope-hempen-50-feet")
    run(state, use(state, "rope-hempen-50-feet"))  # an Athletics place boon
    events = _try(ScriptedRng(20), state, state.creatures["hero"], _feature(), Skill.ATHLETICS)
    assert _check(events).result.adv_why == ()


def test_picking_needs_thieves_tools_and_other_checks_wait_for_the_lock() -> None:
    state = _locked()
    assert "thieves' tools" in _refused(state, Skill.SLEIGHT_OF_HAND)
    assert "locked" in _refused(state, Skill.INVESTIGATION)


def test_gear_on_nothing_locked_is_refused() -> None:
    state = _locked("crowbar")
    assert "nothing locked" in refusal(use(state, "crowbar", "feat-none"))
    run(state, [FeatureUnlocked(feature_id=CHEST, creature_id="hero", method="force")])
    assert "not locked" in refusal(use(state, "crowbar", CHEST))


def test_locks_stay_only_on_caches_containers_and_side_doors() -> None:
    state = at(DOCKS)
    for kind in (FeatureKind.CACHE, FeatureKind.CONTAINER, FeatureKind.DOOR):
        assert lock_problem(state, _feature(kind)) is None
        assert placed_lock(state, _feature(kind)).lock is not None
    for kind in (FeatureKind.PASSAGE, FeatureKind.LEVER, FeatureKind.TRAP, FeatureKind.OBJECT):
        assert lock_problem(state, _feature(kind)) is not None
        assert placed_lock(state, _feature(kind)).lock is None


def test_a_lock_never_lands_on_the_gateway_or_a_quest_item() -> None:
    state = at(DOCKS)
    assert placed_lock(state, _feature(FeatureKind.DOOR, node=GATEWAY)).lock is None
    quest = _feature(FeatureKind.CACHE, name="Choir tide-orders")  # an act 1 quest item
    assert "quest item" in str(lock_problem(state, quest))
    assert placed_lock(state, quest).lock is None


def test_a_lock_tier_is_capped_so_forcing_can_succeed() -> None:
    placed = placed_lock(at(DOCKS), _feature(tier=DcTier.NEARLY_IMPOSSIBLE))
    assert placed.lock is not None and placed.lock.dc_tier is MAX_LOCK_TIER


def test_an_old_save_feature_without_a_lock_field_loads_unlocked() -> None:
    raw = json.loads(_feature().model_dump_json())
    raw.pop("lock")
    assert WorldFeature.model_validate(raw).lock is None
