"""Encounter lifecycle: start, monsters, initiative, surprise, outcome, XP."""

from __future__ import annotations

import random

import pytest

from aidm.data.srd import srd
from aidm.models.abilities import Ability
from aidm.models.encounter import (
    EncounterStatus,
    MonsterSpawn,
    PartyPlacement,
    Side,
    SurpriseKind,
    WithdrawReason,
)
from aidm.models.encounter_events import EncounterEnded, EncounterStarted
from aidm.models.events import ConditionApplied, CreatureAdded, CreatureDied, HpChanged, XpGained
from aidm.models.state import CreatureKind, GameState
from aidm.rules.condition_timing import new_condition
from aidm.rules.encounter import (
    EncounterRefusal,
    EncounterRefused,
    encounter_outcome,
    end_encounter,
    kill_xp,
    roll_initiative,
    start_encounter,
    withdraw_combatant,
)
from tests.unit.rules.encounter_fixtures import make_pc, party_state, run, setup_for, started


class _Script:
    """An rng that returns scripted values (for exact initiative rolls)."""

    def __init__(self, values: list[int]) -> None:
        self.values = list(values)

    def randint(self, a: int, b: int) -> int:
        value = self.values.pop(0)
        assert a <= value <= b
        return value


def test_start_spawns_monsters_from_srd_blocks() -> None:
    state, _ = started(1, [make_pc("ana")], ["goblin", "goblin"])
    goblin = state.creatures["goblin-1"]
    # SRD 5.1 Goblin: AC 15, HP 7 (2d6), DEX 14, Stealth +6, 50 XP.
    assert (goblin.kind, goblin.ac, goblin.hp, goblin.max_hp) == (CreatureKind.MONSTER, 15, 7, 7)
    assert goblin.abilities[Ability.DEX] == 14
    assert "goblin-2" in state.creatures
    enc = state.encounter
    assert enc is not None and enc.status is EncounterStatus.ACTIVE
    assert enc.combatant("goblin-2").xp == 50
    assert enc.combatant("goblin-1").side is Side.HOSTILE
    assert enc.positions() == {"ana": "gate", "goblin-1": "yard", "goblin-2": "yard"}
    assert (enc.round, enc.active_index, enc.turn_open) == (1, -1, False)


def test_spawn_ids_skip_existing_ones_and_events_order() -> None:
    state = party_state(make_pc("ana"))
    state.creatures["goblin-1"] = make_pc("goblin-1")
    events = start_encounter(
        random.Random(2), state, setup_for(["ana"], ["goblin"]), srd().monsters
    )
    assert isinstance(events[0], CreatureAdded) and events[0].creature.id == "goblin-2"
    assert isinstance(events[1], EncounterStarted)


def test_initiative_is_1d4_plus_dex_with_deterministic_ties() -> None:
    a, b, c, d = (make_pc(n, dex=x) for n, x in (("a", 14), ("b", 16), ("c", 14), ("d", 10)))
    entries = roll_initiative(_Script([3, 2, 3, 4]), [a, b, c, d])
    assert [(e.creature_id, e.roll, e.total) for e in entries] == [
        ("b", 2, 5),  # DEX 16 (+3) beats the tie on 5 by DEX score
        ("a", 3, 5),  # same total and DEX as c: id order
        ("c", 3, 5),
        ("d", 4, 4),
    ]


def test_same_seed_gives_same_initiative() -> None:
    pcs = [make_pc("ana", dex=14), make_pc("bo", dex=8)]
    first, _ = started(9, pcs, ["goblin", "orc"])
    second, _ = started(9, pcs, ["goblin", "orc"])
    assert first.encounter == second.encounter
    assert first.encounter is not None
    assert all(1 <= e.roll <= 4 for e in first.encounter.initiative)


def test_surprise_marks_the_ambushed_side() -> None:
    state, _ = started(3, [make_pc("ana")], ["goblin"], SurpriseKind.PARTY)
    enc = state.encounter
    assert enc is not None
    assert [c.name for c in state.creatures["ana"].conditions] == ["surprised"]
    assert enc.combatant("ana").surprised and not enc.combatant("ana").economy.reaction
    assert state.creatures["goblin-1"].conditions == []
    state2, _ = started(3, [make_pc("ana")], ["goblin"], SurpriseKind.HOSTILE)
    assert [c.name for c in state2.creatures["goblin-1"].conditions] == ["surprised"]


_ANA = PartyPlacement(creature_id="ana", zone_id="gate")


@pytest.mark.parametrize(
    ("party", "reason"),
    [
        ((_ANA, PartyPlacement(creature_id="ghost", zone_id="gate")), "unknown_creature"),
        ((_ANA, _ANA), "duplicate_placement"),
        ((PartyPlacement(creature_id="ana", zone_id="moon"),), "unknown_zone"),
    ],
)
def test_start_refusals_emit_nothing(party: tuple[PartyPlacement, ...], reason: str) -> None:
    state = party_state(make_pc("ana"))
    bad = setup_for(["ana"], ["goblin"]).model_copy(update={"party": party})
    with pytest.raises(EncounterRefused) as err:
        start_encounter(random.Random(1), state, bad, srd().monsters)
    assert err.value.reason.value == reason
    assert state.encounter is None


def test_start_refuses_unknown_monster_dead_pc_and_second_fight() -> None:
    state = party_state(make_pc("ana"))
    setup = setup_for(["ana"], ["goblin"])
    bad = setup.model_copy(
        update={"monsters": (MonsterSpawn(monster="tarrasque-x", zone_id="yard"),)}
    )
    with pytest.raises(EncounterRefused) as err:
        start_encounter(random.Random(1), state, bad, srd().monsters)
    assert err.value.reason is EncounterRefusal.UNKNOWN_MONSTER
    state.creatures["ana"].dead = True
    with pytest.raises(EncounterRefused) as err:
        start_encounter(random.Random(1), state, setup, srd().monsters)
    assert err.value.reason is EncounterRefusal.CREATURE_DOWN
    live, _ = started(1, [make_pc("ana")], ["goblin"])
    with pytest.raises(EncounterRefused) as err:
        start_encounter(random.Random(1), live, setup_for(["ana"], []), srd().monsters)
    assert err.value.reason is EncounterRefusal.ALREADY_ACTIVE


def _kill(state: GameState, cid: str) -> None:
    run(state, [HpChanged(creature_id=cid, delta=-1, new_hp=0), CreatureDied(creature_id=cid)])


def test_victory_when_all_hostiles_dead_fled_or_surrendered() -> None:
    state, _ = started(4, [make_pc("ana")], ["goblin", "goblin", "goblin"])
    assert encounter_outcome(state) is None
    _kill(state, "goblin-1")
    run(state, withdraw_combatant(state, "goblin-2", WithdrawReason.SURRENDERED))
    assert encounter_outcome(state) is None
    run(state, withdraw_combatant(state, "goblin-3", WithdrawReason.FLED))
    assert encounter_outcome(state) is EncounterStatus.VICTORY
    assert kill_xp(state) == 100  # killed + surrendered goblins, not the one that fled


def test_party_wipe_counts_dying_and_stable_pcs_as_down() -> None:
    state, _ = started(5, [make_pc("ana"), make_pc("bo")], ["goblin"])
    run(state, [HpChanged(creature_id="ana", delta=-5, new_hp=0)])
    assert encounter_outcome(state) is None  # bo still stands
    state.creatures["bo"].hp = 0
    state.creatures["bo"].stable = True
    assert encounter_outcome(state) is EncounterStatus.DEFEAT


def test_allied_npc_prevents_defeat_and_neutrals_do_not_matter() -> None:
    state = party_state(make_pc("ana"), make_pc("ally"), make_pc("cat"))
    state.creatures["ally"].kind = CreatureKind.NPC
    state.creatures["ally"].pc = None
    setup = setup_for(["ana"], ["goblin"])
    extra = (
        PartyPlacement(creature_id="ally", zone_id="gate"),
        PartyPlacement(creature_id="cat", zone_id="wall", side=Side.NEUTRAL),
    )
    setup = setup.model_copy(update={"party": setup.party + extra})
    run(state, start_encounter(random.Random(6), state, setup, srd().monsters))
    state.creatures["ana"].hp = 0
    assert encounter_outcome(state) is None
    state.creatures["ally"].hp = 0
    assert encounter_outcome(state) is EncounterStatus.DEFEAT
    state.creatures["ally"].hp = 5
    _kill(state, "goblin-1")
    assert encounter_outcome(state) is EncounterStatus.VICTORY


def test_party_that_flees_ends_fled() -> None:
    state, _ = started(7, [make_pc("ana"), make_pc("bo")], ["ogre"])
    run(state, withdraw_combatant(state, "ana", WithdrawReason.FLED))
    assert encounter_outcome(state) is None
    run(state, withdraw_combatant(state, "bo", WithdrawReason.FLED))
    assert encounter_outcome(state) is EncounterStatus.FLED


def test_end_awards_kill_xp_split_among_living_pcs() -> None:
    pcs = [make_pc("ana"), make_pc("bo"), make_pc("cy")]
    state, _ = started(8, pcs, ["goblin", "goblin", "orc"])
    for cid in ("goblin-1", "goblin-2", "orc-1"):
        _kill(state, cid)
    _kill(state, "cy")
    events = end_encounter(state, EncounterStatus.VICTORY)
    ended = events[0]
    # SRD 5.1: Goblin CR 1/4 = 50 XP, Orc CR 1/2 = 100 XP; 200 XP split by 2 living PCs.
    assert isinstance(ended, EncounterEnded)
    assert (ended.xp_total, ended.xp_each, ended.recipients) == (200, 100, ("ana", "bo"))
    gains = [e for e in events if isinstance(e, XpGained)]
    assert [(g.creature_id, g.amount) for g in gains] == [("ana", 100), ("bo", 100)]
    run(state, events)
    assert state.encounter is not None and state.encounter.status is EncounterStatus.VICTORY
    pc_data = state.creatures["ana"].pc
    assert pc_data is not None and pc_data.xp == 100


def test_end_expires_round_conditions_but_keeps_others() -> None:
    state, _ = started(10, [make_pc("ana")], ["goblin"])
    run(
        state,
        [
            ConditionApplied(creature_id="ana", condition=new_condition("dodging")),
            ConditionApplied(creature_id="ana", condition=new_condition("exhaustion")),
        ],
    )
    run(state, end_encounter(state, EncounterStatus.PARLEY))
    assert [c.name for c in state.creatures["ana"].conditions] == ["exhaustion"]
    with pytest.raises(EncounterRefused):
        end_encounter(state, EncounterStatus.VICTORY)


def test_end_refuses_active_status() -> None:
    state, _ = started(11, [make_pc("ana")], ["goblin"])
    with pytest.raises(EncounterRefused) as err:
        end_encounter(state, EncounterStatus.ACTIVE)
    assert err.value.reason is EncounterRefusal.INVALID_STATUS


def test_same_named_foes_get_letters_in_spawn_order() -> None:
    """M20.7 (playtest 3: two stirges both read 'Stirge'): letters only where names collide."""
    state, _ = started(4, [make_pc("ana")], ["goblin", "orc", "goblin", "goblin"])
    names = [state.creatures[c].name for c in ("goblin-1", "goblin-2", "goblin-3", "orc-1")]
    assert names == ["Goblin A", "Goblin B", "Goblin C", "Orc"]
    alone, _ = started(4, [make_pc("ana")], ["goblin"])
    assert alone.creatures["goblin-1"].name == "Goblin"
