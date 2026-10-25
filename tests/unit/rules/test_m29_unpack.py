"""Open the pack (M29.3b): an old save's sealed starting pack becomes its SRD contents."""

import random

from aidm.data.item_uses import uses_for_item
from aidm.models.item_events import ItemUsed
from aidm.rules.item_use import use_item
from aidm.session.reducer import apply
from tests.unit.rules.item_fixtures import CAVE, at, gear_fight, hero, qty, refusal, run, use
from tests.unit.rules.test_m27_gear_sources import PACKS


def test_golden_unpack_dungeoneers_pack_gives_srd_contents() -> None:
    state = at(CAVE, hero(gear=["dungeoneers-pack"]))
    events = use(state, "dungeoneers-pack")
    assert any(isinstance(e, ItemUsed) and not e.no_effect for e in events), events
    run(state, events)
    # SRD 5.1 Equipment Packs, Dungeoneer's Pack: a backpack, a crowbar, a hammer, 10 pitons,
    # 10 torches, a tinderbox, 10 days of rations, a waterskin and 50 feet of hempen rope.
    assert qty(state, "hero", "dungeoneers-pack") == 0
    assert qty(state, "hero", "torch") == 10 and qty(state, "hero", "piton") == 10
    assert qty(state, "hero", "rations-1-day") == 10
    for item in ("backpack", "crowbar", "hammer", "tinderbox", "waterskin", "rope-hempen-50-feet"):
        assert qty(state, "hero", item) == 1, item


def test_unpack_then_light_a_torch_from_an_old_save() -> None:
    state = at(CAVE, hero(gear=["dungeoneers-pack"]))
    assert "item_used" not in [e.type for e in use(state, "torch")]  # sealed: no torch
    run(state, use(state, "dungeoneers-pack"))
    events = use(state, "torch")
    assert any(e.type == "light_lit" for e in events), events


def test_unpack_adds_to_gear_already_carried() -> None:
    state = at(CAVE, hero(gear=["dungeoneers-pack", ("torch", 2)]))
    run(state, use(state, "dungeoneers-pack"))
    assert qty(state, "hero", "torch") == 12


def test_unpack_refused_in_a_fight_and_when_not_carried() -> None:
    me = hero(gear=["dungeoneers-pack"])
    assert "fight" in refusal(use(gear_fight(CAVE, me), "dungeoneers-pack"))
    assert "carry" in refusal(use(at(CAVE, hero()), "dungeoneers-pack"))


def test_unpack_events_replay_to_the_same_state() -> None:
    state = at(CAVE, hero(gear=["dungeoneers-pack"]))
    events = use_item(state, "hero", "dungeoneers-pack", rng=random.Random(1))
    replayed = state.model_copy(deep=True)
    for event in events:
        apply(replayed, event)
    run(state, events)
    assert replayed.model_dump() == state.model_dump()


def test_every_shipped_pack_has_an_unpack_use() -> None:
    for pack in PACKS:
        uses = uses_for_item(pack)
        assert [u.effect.kind for u in uses] == ["unpack"], pack
        assert uses[0].when == "place" and uses[0].cost is None and uses[0].consumes
