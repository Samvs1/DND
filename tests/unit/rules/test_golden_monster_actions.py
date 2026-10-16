"""Golden tests for monster actions (M3.8): breath weapons with recharge, multiattack, riders,
spell kits, legendary actions and monster traits. Numbers cite the SRD 5.1 stat blocks."""

from __future__ import annotations

import pytest

from aidm.models.combat_events import AttackRolled, MonsterActionUsed
from aidm.models.commands import DisengageCommand, RefusalCode
from aidm.models.dice import AdvState
from aidm.models.encounter import Side
from aidm.models.events import AnyEvent, CheckResolved, DiceRolled
from aidm.rules.command_checks import CommandRefused
from aidm.rules.monster_legendary import legendary_action, legendary_ready
from aidm.session.reducer import apply, replay
from tests.unit.rules.combat_fixtures import REGS, ScriptedRng, do, economy, fight
from tests.unit.rules.encounter_fixtures import make_pc
from tests.unit.rules.monster_fixtures import act, advance, dummy, hp, resource, srd_monster
from tests.unit.rules.spell_fixtures import of

BREATH = "recharge-fire-breath"


def test_golden_young_red_dragon_fire_breath() -> None:
    # SRD Young Red Dragon: Fire Breath (Recharge 5-6), 30-foot cone, DC 17 Dex, 56 (16d6) fire,
    # half on a success. A 30 ft cone hits every other creature in the dragon's zone.
    state = fight(
        [
            (srd_monster("young-red-dragon", "dragon"), Side.HOSTILE, "gate"),
            (dummy("t1"), Side.PARTY, "gate"),
            (dummy("t2"), Side.PARTY, "gate"),
            (dummy("far"), Side.PARTY, "yard"),
        ]
    )
    events = act(state, "dragon", "fire-breath", ScriptedRng(5, *[3] * 16, 18))
    saves = of(events, CheckResolved)
    assert [(s.creature_id, s.result.dc, s.result.success) for s in saves] == [
        ("t1", 17, False),
        ("t2", 17, True),
    ]
    assert (hp(state, "t1"), hp(state, "t2"), hp(state, "far")) == (52, 76, 100)
    used = of(events, MonsterActionUsed)[0]
    assert (used.action, used.target_ids, used.target_zone) == ("fire-breath", ("t1", "t2"), "gate")
    assert resource(state, "dragon", BREATH) == 0
    assert not economy(state, "dragon").action


def test_golden_breath_recharge_rolls_at_turn_start() -> None:
    # SRD "Recharge 5-6": at the start of each of its turns the dragon rolls a d6; 5-6 regains it.
    state = fight(
        [
            (srd_monster("young-red-dragon", "dragon"), Side.HOSTILE, "gate"),
            (dummy("t1", dex=30), Side.PARTY, "yard"),
        ]
    )
    act(state, "dragon", "fire-breath", ScriptedRng())  # nobody else in the cone: no rolls
    with pytest.raises(CommandRefused) as refused:
        act(state, "dragon", "fire-breath", ScriptedRng())
    assert refused.value.code is RefusalCode.ABILITY_SPENT
    advance(state, ScriptedRng())  # t1's turn
    started = advance(state, ScriptedRng(4))  # the dragon's turn: a 4 does not recharge
    assert [e.label for e in of(started, DiceRolled)] == ["Recharge fire breath"]
    assert resource(state, "dragon", BREATH) == 0
    advance(state, ScriptedRng())
    advance(state, ScriptedRng(5))
    assert resource(state, "dragon", BREATH) == 1


def test_golden_adult_red_dragon_breath_half_from_text() -> None:
    # SRD Adult Red Dragon: Fire Breath, 60-foot cone, DC 21 Dex, 63 (18d6) fire, "half as much
    # damage on a successful one" (the 5e-bits data says success_type "none"; the text wins).
    # A 60 ft cone targets a zone up to one hop away.
    state = fight(
        [
            (srd_monster("adult-red-dragon", "dragon"), Side.HOSTILE, "gate"),
            (dummy("t1"), Side.PARTY, "yard"),
            (dummy("t2", dex=14), Side.PARTY, "yard"),
            (dummy("near"), Side.PARTY, "gate"),
        ]
    )
    with pytest.raises(CommandRefused) as refused:
        act(state, "dragon", "fire-breath", ScriptedRng())
    assert refused.value.code is RefusalCode.UNKNOWN_ZONE
    act(state, "dragon", "fire-breath", ScriptedRng(15, *[2] * 18, 19), zone="yard")
    assert (hp(state, "t1"), hp(state, "t2"), hp(state, "near")) == (64, 82, 100)


def test_golden_owlbear_multiattack() -> None:
    # SRD Owlbear: Multiattack = Beak (+7, 1d10+5 piercing) and Claws (+7, 2d8+5 slashing).
    state = fight(
        [(srd_monster("owlbear", "owl"), Side.HOSTILE, "gate"), (dummy("t1"), Side.PARTY, "gate")]
    )
    events = act(state, "owl", "multiattack", ScriptedRng(10, 4, 8, 3, 5), targets=["t1"])
    rolls = of(events, AttackRolled)
    assert [(r.attack, r.roll.total, r.hit) for r in rolls] == [
        ("Beak", 17, True),
        ("Claws", 15, True),
    ]
    assert hp(state, "t1") == 100 - 9 - 13
    assert not economy(state, "owl").action


def test_owlbear_multiattack_out_of_reach_consumes_nothing() -> None:
    state = fight(
        [(srd_monster("owlbear", "owl"), Side.HOSTILE, "gate"), (dummy("t1"), Side.PARTY, "yard")]
    )
    with pytest.raises(CommandRefused) as refused:
        act(state, "owl", "multiattack", ScriptedRng(), targets=["t1"])
    assert refused.value.code is RefusalCode.OUT_OF_RANGE
    assert economy(state, "owl").action


def test_golden_goblin_scimitar_and_nimble_escape() -> None:
    # SRD Goblin: Scimitar +4, 1d6+2 slashing; Nimble Escape: Disengage or Hide as a bonus action.
    state = fight(
        [(srd_monster("goblin", "gob"), Side.HOSTILE, "gate"), (dummy("t1"), Side.PARTY, "gate")]
    )
    act(state, "gob", "scimitar", ScriptedRng(9, 5), targets=["t1"])
    assert hp(state, "t1") == 93
    do(state, DisengageCommand(actor_id="gob", bonus_action=True), ScriptedRng())
    eco = economy(state, "gob")
    assert (eco.action, eco.bonus_action, eco.disengaged) == (False, False, True)


def test_golden_mage_magic_missile_uses_own_slot() -> None:
    # SRD Mage: 9th-level caster, 1st level (4 slots) includes magic missile: 3 darts of 1d4+1
    # force at a 1st-level slot.
    state = fight(
        [(srd_monster("mage", "mage"), Side.HOSTILE, "gate"), (dummy("t1"), Side.PARTY, "yard")]
    )
    act(state, "mage", "spell:magic-missile", ScriptedRng(2, 3, 4), targets=["t1"])
    assert hp(state, "t1") == 100 - 3 - 4 - 5
    assert resource(state, "mage", "spell-slot-1") == 3


def test_golden_mage_fire_bolt_scales_with_caster_level() -> None:
    # SRD Mage: +6 to hit with spell attacks; fire bolt at caster level 9 deals 2d10 fire.
    state = fight(
        [(srd_monster("mage", "mage"), Side.HOSTILE, "gate"), (dummy("t1"), Side.PARTY, "yard")]
    )
    events = act(state, "mage", "spell:fire-bolt", ScriptedRng(10, 4, 6), targets=["t1"])
    assert of(events, AttackRolled)[0].roll.total == 16
    assert hp(state, "t1") == 90


def test_mage_spell_outside_kit_refused() -> None:
    state = fight(
        [(srd_monster("mage", "mage"), Side.HOSTILE, "gate"), (dummy("t1"), Side.PARTY, "gate")]
    )
    with pytest.raises(CommandRefused) as refused:
        act(state, "mage", "spell:cure-wounds", ScriptedRng(), targets=["t1"])
    assert refused.value.code is RefusalCode.SPELL_NOT_READY


def test_golden_bandit_captain_melee_routine() -> None:
    # SRD Bandit Captain: three melee attacks (two Scimitar +5 1d6+3, one Dagger +5 1d4+3).
    state = fight(
        [
            (srd_monster("bandit-captain", "cap"), Side.HOSTILE, "gate"),
            (dummy("t1"), Side.PARTY, "gate"),
        ]
    )
    events = act(state, "cap", "multiattack", ScriptedRng(12, 4, 2, 15, 1), targets=["t1"])
    assert [r.attack for r in of(events, AttackRolled)] == ["Scimitar", "Scimitar", "Dagger"]
    assert hp(state, "t1") == 100 - 7 - 4


def test_golden_bandit_captain_ranged_routine_when_out_of_reach() -> None:
    # Or two ranged attacks with its daggers (range 20/60 ft: one hop).
    state = fight(
        [
            (srd_monster("bandit-captain", "cap"), Side.HOSTILE, "gate"),
            (dummy("t1"), Side.PARTY, "yard"),
        ]
    )
    events = act(state, "cap", "multiattack", ScriptedRng(10, 2, 1), targets=["t1"])
    rolls = of(events, AttackRolled)
    assert [(r.attack, r.hit) for r in rolls] == [("Dagger", True), ("Dagger", False)]
    assert hp(state, "t1") == 95


def test_golden_adult_red_dragon_legendary_actions() -> None:
    # SRD Adult Red Dragon legendary actions (3 per round): Tail Attack (Tail +14, 2d8+8
    # bludgeoning); Wing Attack (Costs 2): DC 22 Dex, 2d6+8 bludgeoning and knocked prone.
    state = fight(
        [
            (dummy("t1"), Side.PARTY, "gate"),
            (srd_monster("adult-red-dragon", "dragon"), Side.HOSTILE, "gate"),
        ]
    )
    initial = state.model_copy(deep=True)
    log: list[AnyEvent] = []
    assert legendary_ready(state) == ["dragon"]
    for action, rng in (
        ("tail-attack", ScriptedRng(5, 3, 4)),
        ("wing-attack", ScriptedRng(10, 3, 3)),
    ):
        events = legendary_action(state, "dragon", action, ["t1"], None, REGS, rng)
        for event in events:
            apply(state, event)
        log.extend(events)
    assert hp(state, "t1") == 100 - 15 - 14
    assert any(c.name == "prone" for c in state.creatures["t1"].conditions)
    assert resource(state, "dragon", "legendary-actions") == 0
    assert legendary_ready(state) == []
    with pytest.raises(CommandRefused) as refused:
        legendary_action(state, "dragon", "tail-attack", ["t1"], None, REGS, ScriptedRng())
    assert refused.value.code is RefusalCode.NO_LEGENDARY
    assert replay(initial, log).model_dump() == state.model_dump()
    advance(state, ScriptedRng())
    assert resource(state, "dragon", "legendary-actions") == 3
    with pytest.raises(CommandRefused) as refused:
        legendary_action(state, "dragon", "tail-attack", ["t1"], None, REGS, ScriptedRng())
    assert refused.value.code is RefusalCode.NOT_YOUR_TURN


def test_golden_ghoul_claws_paralyze() -> None:
    # SRD Ghoul: Claws +4, 2d4+2 slashing; a creature other than an elf or undead must succeed
    # on a DC 10 Con save or be paralyzed for 1 minute, repeating the save at the end of its turns.
    state = fight(
        [(srd_monster("ghoul", "ghoul"), Side.HOSTILE, "gate"), (dummy("t1"), Side.PARTY, "gate")]
    )
    act(state, "ghoul", "claws", ScriptedRng(12, 2, 3, 4), targets=["t1"])
    assert hp(state, "t1") == 93
    paralyzed = [c for c in state.creatures["t1"].conditions if c.name == "paralyzed"]
    assert len(paralyzed) == 1
    assert paralyzed[0].rounds_left == 10
    assert paralyzed[0].save_ends is not None and paralyzed[0].save_ends.dc == 10


def test_ghoul_claws_spare_undead_and_elves() -> None:
    zombie = dummy("zombie")
    zombie.creature_type = "undead"
    elf = make_pc("elfy")
    assert elf.pc is not None
    elf.pc.race = "elf"
    for target, rng in ((zombie, ScriptedRng(12, 2, 3)), (elf, ScriptedRng(19, 2, 3))):
        state = fight(
            [(srd_monster("ghoul", "ghoul"), Side.HOSTILE, "gate"), (target, Side.PARTY, "gate")]
        )
        act(state, "ghoul", "claws", rng, targets=[target.id])
        assert not any(c.name == "paralyzed" for c in state.creatures[target.id].conditions)


def test_golden_wolf_pack_tactics_and_trip() -> None:
    # SRD Wolf: Pack Tactics (advantage when an ally is within 5 ft of the target); Bite +4,
    # 2d4+2 piercing, DC 11 Str save or knocked prone.
    state = fight(
        [
            (srd_monster("wolf", "w1"), Side.HOSTILE, "gate"),
            (srd_monster("wolf", "w2"), Side.HOSTILE, "gate"),
            (dummy("t1"), Side.PARTY, "gate"),
        ]
    )
    events = act(state, "w1", "bite", ScriptedRng(3, 15, 1, 1, 15), targets=["t1"])
    roll = of(events, AttackRolled)[0].roll
    assert (roll.adv, roll.natural, roll.total) == (AdvState.ADVANTAGE, 15, 19)
    assert hp(state, "t1") == 96
    assert not any(c.name == "prone" for c in state.creatures["t1"].conditions)


def test_wolf_alone_has_no_pack_advantage() -> None:
    state = fight(
        [
            (srd_monster("wolf", "w1"), Side.HOSTILE, "gate"),
            (srd_monster("wolf", "w2"), Side.HOSTILE, "yard"),
            (dummy("t1"), Side.PARTY, "gate"),
        ]
    )
    events = act(state, "w1", "bite", ScriptedRng(15, 1, 1, 2), targets=["t1"])
    assert of(events, AttackRolled)[0].roll.adv is AdvState.NORMAL
    assert any(c.name == "prone" for c in state.creatures["t1"].conditions)


def test_breath_is_not_magic_for_magic_resistance() -> None:
    # Magic Resistance covers spells and magical effects; a breath weapon rolls one d20.
    resistant = dummy("t1")
    resistant.traits = ["magic-resistance"]
    state = fight(
        [
            (srd_monster("young-red-dragon", "dragon"), Side.HOSTILE, "gate"),
            (resistant, Side.PARTY, "gate"),
        ]
    )
    events = act(state, "dragon", "fire-breath", ScriptedRng(5, *[3] * 16))
    assert of(events, CheckResolved)[0].result.roll.adv is AdvState.NORMAL


def test_multiattack_retargets_when_a_target_drops() -> None:
    # SRD Young Red Dragon: Bite (+10, 2d10+6 piercing plus 1d6 fire) and two Claws (+10,
    # 2d6+6 slashing). Targets are dealt round-robin; the last claw's target is dead, so it
    # goes to the next listed target still standing.
    state = fight(
        [
            (srd_monster("young-red-dragon", "dragon"), Side.HOSTILE, "gate"),
            (dummy("t1", hp=5), Side.PARTY, "gate"),
            (dummy("t2"), Side.PARTY, "gate"),
        ]
    )
    rng = ScriptedRng(10, 5, 5, 1, 10, 1, 1, 10, 1, 1)
    events = act(state, "dragon", "multiattack", rng, targets=["t1", "t2"])
    assert [r.target_id for r in of(events, AttackRolled)] == ["t1", "t2", "t2"]
    assert state.creatures["t1"].dead
    assert hp(state, "t2") == 84


def test_monster_action_refusals_consume_nothing() -> None:
    state = fight(
        [(srd_monster("goblin", "gob"), Side.HOSTILE, "gate"), (dummy("t1"), Side.PARTY, "gate")]
    )
    with pytest.raises(CommandRefused) as refused:
        act(state, "gob", "fire-breath", ScriptedRng(), targets=["t1"])
    assert refused.value.code is RefusalCode.UNKNOWN_OPTION
    with pytest.raises(CommandRefused) as refused:
        act(state, "gob", "scimitar", ScriptedRng(), targets=["t1", "t1"])
    assert refused.value.code is RefusalCode.BAD_TARGETS
    assert economy(state, "gob").action
    plain = fight([(dummy("plain"), Side.HOSTILE, "gate"), (dummy("t1"), Side.PARTY, "gate")])
    with pytest.raises(CommandRefused) as refused:
        act(plain, "plain", "scimitar", ScriptedRng(), targets=["t1"])
    assert refused.value.code is RefusalCode.NOT_A_MONSTER
