"""Property: random encounters driven through the rules replay exactly and keep invariants."""

from __future__ import annotations

import random

from hypothesis import given, settings
from hypothesis import strategies as st

from aidm.data.srd import srd
from aidm.models.damage import DamagePacket, DamageType
from aidm.models.encounter import (
    EncounterSetup,
    EncounterStatus,
    MonsterSpawn,
    PartyPlacement,
    SurpriseKind,
    WithdrawReason,
)
from aidm.models.events import AnyEvent, event_adapter
from aidm.models.state import GameState
from aidm.rules.damage import resolve_damage
from aidm.rules.encounter import (
    encounter_outcome,
    end_encounter,
    start_encounter,
    withdraw_combatant,
)
from aidm.rules.turns import begin_turn, end_turn, spend_action, spend_movement
from aidm.session.reducer import replay
from tests.unit.rules.encounter_fixtures import make_pc, party_state, run, small_map

MONSTERS = ["goblin", "orc", "skeleton", "zombie", "wolf", "kobold"]


def _setup(data: st.DataObject, pc_ids: list[str]) -> EncounterSetup:
    zones = [z.id for z in small_map().zones]
    party = tuple(
        PartyPlacement(creature_id=cid, zone_id=data.draw(st.sampled_from(zones))) for cid in pc_ids
    )
    monsters = tuple(
        MonsterSpawn(monster=m, zone_id=data.draw(st.sampled_from(zones)))
        for m in data.draw(st.lists(st.sampled_from(MONSTERS), min_size=1, max_size=4))
    )
    surprise = data.draw(st.sampled_from(list(SurpriseKind)))
    return EncounterSetup(
        encounter_id="prop", zone_map=small_map(), party=party, monsters=monsters, surprise=surprise
    )


def _act(data: st.DataObject, state: GameState, log: list[AnyEvent]) -> None:
    enc = state.encounter
    assert enc is not None
    cid = enc.active_id()
    assert cid is not None
    eco = enc.combatant(cid).economy
    if eco.action and data.draw(st.booleans()):
        run(state, spend_action(state, cid), log)
        others = sorted(c for c in enc.combatants if c != cid and not state.creatures[c].dead)
        if others:
            target = state.creatures[data.draw(st.sampled_from(others))]
            hit = DamagePacket(
                amount=data.draw(st.integers(1, 15)), damage_type=DamageType.SLASHING
            )
            run(state, resolve_damage(target, [hit], source_id=cid), log)
    if eco.movement_left >= 5 and data.draw(st.booleans()):
        run(state, spend_movement(state, cid, 5), log)
    if data.draw(st.integers(0, 12)) == 0:
        reason = data.draw(st.sampled_from(list(WithdrawReason)))
        run(state, withdraw_combatant(state, cid, reason), log)


def _fight(data: st.DataObject) -> tuple[GameState, GameState, list[AnyEvent]]:
    count = data.draw(st.integers(1, 3))
    pcs = [make_pc(f"pc{i}", dex=data.draw(st.integers(6, 18))) for i in range(count)]
    initial = party_state(*pcs)
    live = initial.model_copy(deep=True)
    rng = random.Random(data.draw(st.integers(0, 2**31)))
    log: list[AnyEvent] = []
    run(live, start_encounter(rng, live, _setup(data, [p.id for p in pcs]), srd().monsters), log)
    last_round = 1
    for _ in range(data.draw(st.integers(0, 40))):
        outcome = encounter_outcome(live)
        if outcome is not None:
            run(live, end_encounter(live, outcome), log)
            break
        run(live, begin_turn(rng, live), log)
        assert live.encounter is not None and live.encounter.round >= last_round
        last_round = live.encounter.round
        _act(data, live, log)
        run(live, end_turn(rng, live), log)
    return initial, live, log


@settings(max_examples=120, deadline=None)
@given(st.data())
def test_random_encounters_replay_to_the_live_state(data: st.DataObject) -> None:
    initial, live, log = _fight(data)
    assert replay(initial, log).model_dump() == live.model_dump()
    decoded = [event_adapter.validate_json(e.model_dump_json()) for e in log]
    assert replay(initial, decoded).model_dump() == live.model_dump()
    assert GameState.model_validate_json(live.model_dump_json()) == live


@settings(max_examples=80, deadline=None)
@given(st.data())
def test_encounter_invariants(data: st.DataObject) -> None:
    _, live, _ = _fight(data)
    enc = live.encounter
    assert enc is not None
    for cid, combatant in enc.combatants.items():
        creature = live.creatures[cid]
        assert 0 <= creature.hp <= creature.max_hp
        assert enc.zone_map.has_zone(combatant.zone_id)
        assert combatant.economy.movement_left <= creature.speed
    if enc.status is not EncounterStatus.ACTIVE:
        assert not enc.turn_open
