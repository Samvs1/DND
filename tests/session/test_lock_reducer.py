"""Locks in the reducer (M27.4): FeatureUnlocked clears the lock, replay == snapshot, old saves
with features and no lock field load unlocked."""

import json

import pytest

from aidm.models.checks import DcTier
from aidm.models.events import AnyEvent, LoggedEvent, event_adapter
from aidm.models.item_events import FeatureUnlocked, PlaceAlerted
from aidm.models.state import GameState
from aidm.models.world import FeatureKind, LockInfo, WorldFeature
from aidm.models.world_events import FeatureIntroduced, PartyMoved
from aidm.session.persistence import replay_log
from aidm.session.reducer import apply, replay
from aidm.session.reducer_errors import ReducerError
from tests.unit.rules.encounter_fixtures import make_pc


def _base() -> GameState:
    state = GameState(campaign_id="locks", seed=1)
    state.creatures["hero"] = make_pc("hero")
    return state


def _chest(fid: str, *, locked: bool = True) -> WorldFeature:
    lock = LockInfo(dc_tier=DcTier.HARD, opens=FeatureKind.CONTAINER) if locked else None
    return WorldFeature(id=fid, kind=FeatureKind.CONTAINER, name=fid, node_id="vault", lock=lock)


def _events() -> list[AnyEvent]:
    return [
        PartyMoved(from_node=None, to_node="vault", scene_index=1),
        FeatureIntroduced(feature=_chest("chest-a")),
        FeatureIntroduced(feature=_chest("chest-b")),
        PlaceAlerted(node="vault"),
        FeatureUnlocked(feature_id="chest-a", creature_id="hero", method="force"),
    ]


def test_feature_unlocked_clears_only_that_lock() -> None:
    state = replay(_base(), _events())
    assert state.world.features["chest-a"].lock is None
    assert state.world.features["chest-b"].lock == LockInfo(
        dc_tier=DcTier.HARD, opens=FeatureKind.CONTAINER
    )


def test_feature_unlocked_needs_a_known_feature() -> None:
    with pytest.raises(ReducerError):
        apply(_base(), FeatureUnlocked(feature_id="ghost", creature_id="hero", method="key"))


def test_replay_with_locks_equals_snapshot() -> None:
    base = _base()
    live = base.model_copy(deep=True)
    for event in _events():
        apply(live, event)
    log = [
        LoggedEvent(seq=i, event=event_adapter.validate_json(event.model_dump_json()))
        for i, event in enumerate(_events())
    ]
    snapshot = GameState.model_validate_json(live.model_dump_json())
    assert replay_log(base, log) == snapshot == live
    assert snapshot.world.alerted == "vault"


def test_old_save_with_features_and_no_lock_field_loads_unlocked() -> None:
    state = replay(_base(), [FeatureIntroduced(feature=_chest("old-chest", locked=False))])
    raw = json.loads(state.model_dump_json())
    for feature in raw["world"]["features"].values():
        feature.pop("lock")  # a save from before M27.4
    old = GameState.model_validate(raw)
    assert old.world.features["old-chest"].lock is None
    log = [LoggedEvent(seq=0, event=PartyMoved(from_node="vault", to_node="cave", scene_index=2))]
    assert replay_log(old, log).world.features["old-chest"].lock is None
