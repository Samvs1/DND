"""Class and race feature actions through the `feature_action` command (M7.5b, SPEC 7.2 / 7.4)."""

from __future__ import annotations

import random

import pytest

from aidm.data.character_data import character_registries
from aidm.models.combat_events import AttackRolled, FeatureUsed
from aidm.models.commands import AttackCommand, FeatureActionCommand, HideCommand, RefusalCode
from aidm.models.encounter import Side
from aidm.models.events import DamageTaken, HpChanged, ResourceSet
from aidm.models.state import Creature, GameState
from aidm.rules.command_checks import CommandRefused
from aidm.rules.commands import execute_command
from aidm.rules.creation import build_character
from aidm.rules.features import feature_actions
from aidm.rules.party_ai import next_pc_command
from aidm.rules.resources import resource_left
from aidm.rules.rests import short_rest
from aidm.rules.spellcasting import SlotKind, slot_key
from aidm.session.reducer import apply
from tests.unit.rules.combat_fixtures import REGS, ScriptedRng, do, economy, fight, monster
from tests.unit.rules.creation_fixtures import default_choices
from tests.unit.rules.golden_builds import golden_levels
from tests.unit.rules.spell_fixtures import conditions_of, of


def _hero(cls: str, level: int, cid: str = "hero") -> Creature:
    return golden_levels(cls)[level].model_copy(update={"id": cid}, deep=True)


def _use(
    feature: str, *, targets: tuple[str, ...] = (), zone: str | None = None
) -> FeatureActionCommand:
    return FeatureActionCommand(
        actor_id="hero", feature_id=feature, target_ids=targets, target_zone=zone
    )


def _refused(state: GameState, command: FeatureActionCommand) -> RefusalCode:
    with pytest.raises(CommandRefused) as info:
        execute_command(state, command, REGS, ScriptedRng())
    return info.value.code


def _foe(cid: str, *, hp: int = 30, kind: str | None = None) -> Creature:
    return monster(cid, hp=hp, ac=13).model_copy(update={"creature_type": kind})


def test_golden_second_wind() -> None:
    # SRD 5.1 Fighter: Second Wind, a bonus action, regains 1d10 + fighter level HP, once per
    # short rest. Level-1 golden fighter at 3 of 12 HP, d10 = 7: 7 + 1 = 8 -> 11 HP.
    hero = _hero("fighter", 1).model_copy(update={"hp": 3})
    state = fight([(hero, Side.PARTY, "gate"), (_foe("gob"), Side.HOSTILE, "yard")])
    events = do(state, _use("second-wind"), ScriptedRng(7))
    assert state.creatures["hero"].hp == 11
    assert of(events, HpChanged)[0].delta == 8
    assert of(events, FeatureUsed)[0].name == "Second Wind"
    assert not economy(state, "hero").bonus_action and economy(state, "hero").action
    assert resource_left(state.creatures["hero"], "second-wind") == 0
    assert _refused(state, _use("second-wind")) is RefusalCode.ABILITY_SPENT


def test_second_wind_refused_at_full_hp_and_without_the_feature() -> None:
    state = fight([(_hero("fighter", 1), Side.PARTY, "gate"), (_foe("gob"), Side.HOSTILE, "yard")])
    assert _refused(state, _use("second-wind")) is RefusalCode.FULL_HP
    assert resource_left(state.creatures["hero"], "second-wind") == 1
    assert _refused(state, _use("action-surge-1-use")) is RefusalCode.NO_FEATURE
    assert _refused(state, _use("cunning-action")) is RefusalCode.NO_FEATURE
    rogue = fight([(_hero("rogue", 2), Side.PARTY, "gate"), (_foe("gob"), Side.HOSTILE, "yard")])
    assert _refused(rogue, _use("second-wind")) is RefusalCode.NO_FEATURE
    # Cunning Action keeps working through the existing bonus-action commands.
    hide = HideCommand(actor_id="hero", bonus_action=True)
    assert execute_command(rogue, hide, REGS, ScriptedRng(10))


def _attack(state: GameState, rng: random.Random) -> list[AttackRolled]:
    return of(do(state, AttackCommand(actor_id="hero", target_id="ogre"), rng), AttackRolled)


@pytest.mark.parametrize(("level", "attacks"), [(2, 2), (5, 4)])
def test_golden_action_surge_two_attack_actions(level: int, attacks: int) -> None:
    # SRD 5.1 Fighter: Action Surge (2nd level) gives one additional action on the turn, once
    # per short rest; with Extra Attack (5th level) each Attack action makes two attacks.
    ogre = _foe("ogre", hp=500)
    state = fight([(_hero("fighter", level), Side.PARTY, "gate"), (ogre, Side.HOSTILE, "gate")])
    assert _refused(state, _use("action-surge-1-use")) is RefusalCode.ACTION_UNUSED
    rng = random.Random(3)
    rolled = [roll for _ in range(attacks // 2) for roll in _attack(state, rng)]
    assert not economy(state, "hero").action
    surge = do(state, _use("action-surge-1-use"), rng)
    assert of(surge, FeatureUsed)[0].name == "Action Surge"
    assert economy(state, "hero").action and economy(state, "hero").bonus_action
    rolled += [roll for _ in range(attacks // 2) for roll in _attack(state, rng)]
    assert len(rolled) == attacks
    assert not economy(state, "hero").action and economy(state, "hero").attacks_left == 0
    assert resource_left(state.creatures["hero"], "action-surge") == 0
    assert _refused(state, _use("action-surge-1-use")) is RefusalCode.ABILITY_SPENT


def _dragonborn() -> Creature:
    choices = default_choices("fighter", "dragonborn", None)
    return build_character(choices, character_registries(), "hero")


def test_golden_dragonborn_breath_weapon() -> None:
    # SRD 5.1 Dragonborn: Breath Weapon, black ancestry = acid, DEX save, DC 8 + CON modifier
    # (13 -> +1) + proficiency 2 = 11; 2d6 damage, half on a success; once per short rest.
    hero = _dragonborn()
    assert "draconic-ancestry-black" in (hero.pc.traits if hero.pc else [])
    state = fight(
        [
            (hero, Side.PARTY, "gate"),
            (_foe("ga"), Side.HOSTILE, "yard"),
            (_foe("gb"), Side.HOSTILE, "yard"),
            (_foe("gc"), Side.HOSTILE, "wall"),
        ]
    )
    actions = [a for a in feature_actions(hero, REGS.chars.features) if a.command]
    breath = next(a for a in actions if a.name == "Breath Weapon")
    assert breath.feature == "draconic-ancestry-black" and breath.target_kind == "area"
    # ga saves with 5 (fails), the shared 2d6 rolls 4 + 5 = 9, gb saves with 18 (half: 4).
    events = do(state, _use(breath.feature, zone="yard"), ScriptedRng(5, 4, 5, 18))
    damage = {e.creature_id: e.total for e in of(events, DamageTaken)}
    assert damage == {"ga": 9, "gb": 4}
    assert state.creatures["gc"].hp == 30
    assert of(events, FeatureUsed)[0].target_ids == ("ga", "gb")
    assert not economy(state, "hero").action
    assert resource_left(state.creatures["hero"], "breath-weapon") == 0
    assert _refused(state, _use(breath.feature, zone="yard")) is RefusalCode.ABILITY_SPENT


def test_breath_weapon_refuses_out_of_range_and_empty_areas() -> None:
    state = fight(
        [
            (_dragonborn(), Side.PARTY, "gate"),
            (_foe("ga"), Side.HOSTILE, "wall"),
        ]
    )
    use = _use("draconic-ancestry-black", zone="wall")
    assert _refused(state, use) is RefusalCode.OUT_OF_RANGE
    empty = _use("draconic-ancestry-black", zone="yard")
    assert _refused(state, empty) is RefusalCode.BAD_TARGETS
    assert economy(state, "hero").action
    assert resource_left(state.creatures["hero"], "breath-weapon") == 1


def test_golden_turn_undead() -> None:
    # SRD 5.1 Cleric: Channel Divinity: Turn Undead: each undead within 30 feet (own and
    # neighbouring zones) makes a WIS save against the spell save DC 8 + 2 + WIS 16 (+3) = 13
    # or is turned for 1 minute (ends when it takes damage).
    state = fight(
        [
            (_hero("cleric", 2), Side.PARTY, "gate"),
            (_foe("zombie", kind="undead"), Side.HOSTILE, "gate"),
            (_foe("gob"), Side.HOSTILE, "gate"),
            (_foe("skeleton", kind="undead"), Side.HOSTILE, "yard"),
            (_foe("wraith", kind="undead"), Side.HOSTILE, "wall"),
        ]
    )
    events = do(state, _use("channel-divinity-turn-undead"), ScriptedRng(5, 13))
    assert of(events, FeatureUsed)[0].target_ids == ("zombie", "skeleton")
    assert "turned" in conditions_of(state, "zombie")
    assert "turned" not in conditions_of(state, "skeleton")
    assert conditions_of(state, "gob") == [] and conditions_of(state, "wraith") == []
    assert resource_left(state.creatures["hero"], "channel-divinity") == 0
    assert _refused(state, _use("channel-divinity-turn-undead")) is RefusalCode.ABILITY_SPENT


def test_turn_undead_refused_without_undead_in_reach() -> None:
    state = fight([(_hero("cleric", 2), Side.PARTY, "gate"), (_foe("gob"), Side.HOSTILE, "gate")])
    assert _refused(state, _use("channel-divinity-turn-undead")) is RefusalCode.BAD_TARGETS
    assert resource_left(state.creatures["hero"], "channel-divinity") == 1


def test_party_ai_uses_second_wind_when_low() -> None:
    hero = _hero("fighter", 1).model_copy(update={"hp": 5})
    state = fight([(hero, Side.PARTY, "gate"), (_foe("gob"), Side.HOSTILE, "gate")])
    command = next_pc_command(state, "hero", REGS, random.Random(1))
    assert command == FeatureActionCommand(actor_id="hero", feature_id="second-wind")
    healthy = fight([(_hero("fighter", 1), Side.PARTY, "gate"), (_foe("g"), Side.HOSTILE, "gate")])
    assert not isinstance(
        next_pc_command(healthy, "hero", REGS, random.Random(1)), FeatureActionCommand
    )


def test_golden_arcane_recovery_on_short_rest() -> None:
    # SRD 5.1 Wizard: Arcane Recovery, once per long rest after a short rest, regain spell slots
    # whose levels total up to half the wizard level rounded up (3 -> 2). Chosen automatically:
    # the highest spent slots first (DECISIONS M7.5b), so one level-2 slot comes back.
    wizard = _hero("wizard", 3)
    one, two = slot_key(SlotKind.STANDARD, 1), slot_key(SlotKind.STANDARD, 2)
    wizard.resources[one] = wizard.resources[one].model_copy(update={"current": 2})
    wizard.resources[two] = wizard.resources[two].model_copy(update={"current": 1})
    state = GameState(campaign_id="rest", seed=1)
    state.creatures["hero"] = wizard
    for event in short_rest(state, REGS.chars.features):
        apply(state, event)
    after = state.creatures["hero"].resources
    assert (after[one].current, after[two].current) == (2, 2)
    assert resource_left(state.creatures["hero"], "arcane-recovery") == 0
    events = short_rest(state, REGS.chars.features)
    assert not [e for e in events if isinstance(e, ResourceSet) and e.key in (one, two)]


def test_m32_short_feature_id_names_the_one_full_id() -> None:
    # M32.1d X17: `action-surge` resolves to `action-surge-1-use`; an unknown name still refuses.
    ogre = _foe("ogre", hp=500)
    state = fight([(_hero("fighter", 2), Side.PARTY, "gate"), (ogre, Side.HOSTILE, "gate")])
    rng = random.Random(3)
    _attack(state, rng)
    surge = do(state, _use("action-surge"), rng)
    assert of(surge, FeatureUsed)[0].name == "Action Surge"
    assert _refused(state, _use("surge")) is RefusalCode.NO_FEATURE
