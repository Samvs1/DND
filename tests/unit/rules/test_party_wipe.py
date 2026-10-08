"""Party wipe detection (M11.1, DECISIONS M11.1): every hero dead, or every hero down and no
standing party-side ally in an active fight."""

from aidm.models.encounter import EncounterStatus, WithdrawReason
from aidm.models.state import Creature, CreatureKind
from aidm.rules.encounter import encounter_outcome
from aidm.rules.party_wipe import ally_standing, can_act, party_heroes, party_wiped, standing_foes
from tests.unit.rules.encounter_fixtures import make_pc, party_state, started


def _down(pc: Creature, *, dead: bool = False) -> Creature:
    pc.hp = 0
    pc.dead = dead
    return pc


def test_no_heroes_is_never_a_wipe() -> None:
    assert not party_wiped(party_state())


def test_one_hero_down_outside_a_fight_is_a_wipe() -> None:
    state = party_state(_down(make_pc("sam")))
    assert party_heroes(state)[0].id == "sam"
    assert party_wiped(state)


def test_one_standing_hero_prevents_the_wipe() -> None:
    state = party_state(_down(make_pc("sam")), make_pc("mira"))
    assert not party_wiped(state)


def test_every_hero_dead_is_a_wipe() -> None:
    state = party_state(_down(make_pc("sam"), dead=True), _down(make_pc("mira"), dead=True))
    assert party_wiped(state)
    assert not can_act(state.creatures["sam"])


def test_lost_fight_with_everyone_down_is_a_wipe_and_names_the_foes() -> None:
    state, _ = started(3, [make_pc("sam")], ["wolf"])
    state.creatures["sam"].hp = 0
    assert encounter_outcome(state) is EncounterStatus.DEFEAT
    assert party_wiped(state)
    assert standing_foes(state) == ["Wolf"]


def test_a_standing_party_ally_keeps_the_fight_going() -> None:
    state, _ = started(3, [make_pc("sam")], ["wolf"])
    enc = state.encounter
    assert enc is not None
    ally = make_pc("hound").model_copy(update={"kind": CreatureKind.NPC, "pc": None})
    state.creatures["hound"] = ally
    enc.combatants["hound"] = enc.combatants["sam"].model_copy(update={"creature_id": "hound"})
    state.creatures["sam"].hp = 0
    assert ally_standing(state)
    assert not party_wiped(state)
    state.creatures["hound"].hp = 0
    assert party_wiped(state)


def test_a_hero_who_fled_and_is_up_is_not_wiped() -> None:
    state, _ = started(3, [make_pc("sam"), make_pc("mira")], ["wolf"])
    enc = state.encounter
    assert enc is not None
    state.creatures["sam"].hp = 0
    enc.combatants["mira"] = enc.combatants["mira"].model_copy(
        update={"withdrawn": WithdrawReason.FLED}
    )
    assert encounter_outcome(state) is EncounterStatus.FLED
    assert not party_wiped(state)
