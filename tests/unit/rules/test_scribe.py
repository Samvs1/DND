"""The Scribe's revive rules (M13.1): quotes, refusals, restore modes, kept conditions, gold."""

import pytest

from aidm.data.scribe_defs import ScribeTable, scribe_table
from aidm.models.defeat import PartyDefeated
from aidm.models.encounter import Encounter
from aidm.models.events import (
    ConditionApplied,
    ConditionRemoved,
    CreatureDied,
    GoldChanged,
    HpChanged,
)
from aidm.models.scribe import CharacterRewritten
from aidm.models.state import ActiveCondition, GameState
from aidm.rules.scribe import (
    ScribeRefusal,
    ScribeRefused,
    fallen_heroes,
    restored_hp,
    revive_events,
    revive_price,
    scribe_view,
    table_block,
)
from aidm.session.reducer import apply, replay
from tests.ai.tool_fixtures import party_state
from tests.unit.rules.combat_fixtures import small_map

TABLE = scribe_table()


def _kill(state: GameState, cid: str) -> None:
    hp = state.creatures[cid].hp
    apply(state, HpChanged(creature_id=cid, delta=-hp, new_hp=0))
    apply(state, CreatureDied(creature_id=cid))


def _gold(state: GameState, cid: str, gold: int) -> None:
    pc = state.creatures[cid].pc
    assert pc is not None
    apply(state, GoldChanged(creature_id=cid, delta=gold - pc.gold, gold=gold))


def _state(level: int = 1, gold: int = 100, dead: tuple[str, ...] = ("rogue",)) -> GameState:
    state = party_state(level)
    for cid in ("fighter", "rogue", "wizard", "cleric"):
        _gold(state, cid, gold)
    for cid in dead:
        _kill(state, cid)
    return state


def _gold_of(state: GameState, cid: str) -> int:
    pc = state.creatures[cid].pc
    assert pc is not None
    return pc.gold


def test_golden_scribe_price_level_1() -> None:
    # data/bg3/scribe.json (house rule): base_gp 0 + per_level_gp 25 x level 1 = 25 gp
    assert revive_price(1, TABLE) == 25


def test_golden_scribe_price_level_5() -> None:
    # data/bg3/scribe.json (house rule): base_gp 0 + per_level_gp 25 x level 5 = 125 gp
    assert revive_price(5, TABLE) == 125


def test_golden_scribe_restore_half_rounds_up() -> None:
    # data/bg3/scribe.json restore "half": ceil(max_hp / 2)
    assert restored_hp(11, TABLE) == 6
    assert restored_hp(12, TABLE) == 6
    assert restored_hp(1, TABLE) == 1


def test_restore_modes_from_data() -> None:
    assert restored_hp(13, TABLE.model_copy(update={"restore": "one"})) == 1
    assert restored_hp(13, TABLE.model_copy(update={"restore": "full"})) == 13


def test_base_price_is_added() -> None:
    table = ScribeTable(base_gp=10, per_level_gp=20)
    assert revive_price(3, table) == 70


def test_view_lists_each_fallen_with_its_price() -> None:
    state = _state(level=5, dead=("rogue", "wizard"))
    view = scribe_view(state, TABLE, paused=False)
    assert view.available and view.reason is None
    assert [(f.creature_id, f.level, f.price_gp) for f in view.fallen] == [
        ("rogue", 5, 125),
        ("wizard", 5, 125),
    ]


def test_revive_success_events_and_state() -> None:
    state = _state(gold=40)
    target = state.creatures["rogue"]
    events = revive_events(state, "fighter", "rogue", TABLE)
    assert events[0] == GoldChanged(creature_id="fighter", delta=-25, gold=15)
    rewritten = events[-1]
    assert isinstance(rewritten, CharacterRewritten)
    assert rewritten == CharacterRewritten(
        target_id="rogue", payer_id="fighter", cost_gp=25, hp=-(-target.max_hp // 2)
    )
    start = state.model_copy(deep=True)
    for event in events:
        apply(state, event)
    rogue = state.creatures["rogue"]
    assert not rogue.dead and not rogue.stable
    assert rogue.hp == rewritten.hp
    assert (rogue.death_save_successes, rogue.death_save_failures) == (0, 0)
    assert _gold_of(state, "fighter") == 15 and _gold_of(state, "rogue") == 40
    assert replay(start, events).model_dump() == state.model_dump()
    assert fallen_heroes(state) == []


def test_revive_clears_conditions_but_keeps_exhaustion() -> None:
    state = _state()
    for name in ("exhaustion", "poisoned", "prone", "poisoned"):
        cond = ActiveCondition(name=name, source_id="x" if name == "poisoned" else None)
        apply(state, ConditionApplied(creature_id="rogue", condition=cond))
    events = revive_events(state, "fighter", "rogue", TABLE)
    removed = [e.name for e in events if isinstance(e, ConditionRemoved)]
    assert sorted(removed) == ["poisoned", "prone"]
    for event in events:
        apply(state, event)
    assert [c.name for c in state.creatures["rogue"].conditions] == ["exhaustion"]


def test_revive_picks_the_requested_target() -> None:
    state = _state(dead=("rogue", "wizard"))
    for event in revive_events(state, "fighter", "wizard", TABLE):
        apply(state, event)
    assert not state.creatures["wizard"].dead and state.creatures["rogue"].dead


def test_exact_funds_reach_zero_never_negative() -> None:
    state = _state(gold=25)
    events = revive_events(state, "fighter", "rogue", TABLE)
    assert events[0] == GoldChanged(creature_id="fighter", delta=-25, gold=0)


def _refused(state: GameState, payer: str, target: str, *, paused: bool = False) -> ScribeRefusal:
    with pytest.raises(ScribeRefused) as caught:
        revive_events(state, payer, target, TABLE, paused=paused)
    return caught.value.reason


def test_refusal_no_funds() -> None:
    assert _refused(_state(gold=24), "fighter", "rogue") is ScribeRefusal.NO_FUNDS


def test_refusal_none_fallen() -> None:
    state = _state(dead=())
    assert _refused(state, "fighter", "rogue") is ScribeRefusal.NONE_FALLEN
    view = scribe_view(state, TABLE, paused=False)
    assert not view.available and view.reason == "scribe_none_fallen" and not view.fallen


def test_refusal_not_fallen_at_zero_hp_alive() -> None:
    state = _state()
    hp = state.creatures["wizard"].hp
    apply(state, HpChanged(creature_id="wizard", delta=-hp, new_hp=0))
    assert _refused(state, "fighter", "wizard") is ScribeRefusal.NOT_FALLEN
    assert _refused(state, "fighter", "cleric") is ScribeRefusal.NOT_FALLEN


def test_refusal_payer_down() -> None:
    state = _state()
    assert _refused(state, "rogue", "rogue") is ScribeRefusal.PAYER_DOWN
    hp = state.creatures["fighter"].hp
    apply(state, HpChanged(creature_id="fighter", delta=-hp, new_hp=0))
    assert _refused(state, "fighter", "rogue") is ScribeRefusal.PAYER_DOWN


def test_refusal_unknown_target() -> None:
    assert _refused(_state(), "fighter", "nobody") is ScribeRefusal.UNKNOWN_TARGET


def test_refusal_in_combat() -> None:
    state = _state()
    state.encounter = Encounter(id="f1", zone_map=small_map())
    assert _refused(state, "fighter", "rogue") is ScribeRefusal.IN_COMBAT
    view = scribe_view(state, TABLE, paused=False)
    assert not view.available and view.reason == "scribe_in_combat" and len(view.fallen) == 1


def test_refusal_paused_and_defeated() -> None:
    state = _state()
    assert _refused(state, "fighter", "rogue", paused=True) is ScribeRefusal.PAUSED
    assert table_block(state, paused=True) is ScribeRefusal.PAUSED
    apply(state, PartyDefeated(text="The road ends here."))
    assert _refused(state, "fighter", "rogue") is ScribeRefusal.DEFEATED
