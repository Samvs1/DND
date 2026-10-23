"""M29.7d round-2 combat rules: aimed self cones and lines (R26), ranged shots in close combat (R3).

Saves: p8 141-150 (Burning Hands aimed at the archway burned three allies in the reeds), p5
549-640 (a crossbow shot at a minotaur in the fighter's own zone rolled at "normal").
"""

from __future__ import annotations

import random
from collections.abc import Sequence

import pytest

from aidm.models.commands import AttackCommand, CastCommand, RefusalCode
from aidm.models.encounter import Side
from aidm.models.events import AttackRolled, DamageTaken
from aidm.models.state import ActiveCondition, Creature, GameState
from aidm.models.zones import Zone, ZoneEdge, ZoneMap
from aidm.rules.ai_options import monster_choices, pc_choices
from aidm.rules.ai_view import ai_view
from aidm.rules.command_checks import CommandRefused
from aidm.rules.condition_timing import new_condition
from aidm.rules.hit_chance import hit_chances, threatened
from aidm.rules.party_ai import next_pc_command
from aidm.rules.spell_targets import area_zones
from tests.unit.rules.combat_fixtures import REGS, Placement, ScriptedRng, do, fight
from tests.unit.rules.encounter_fixtures import make_pc
from tests.unit.rules.monster_fixtures import srd_monster
from tests.unit.rules.spell_fixtures import cast, caster, of


def _reeds_map() -> ZoneMap:
    # The p8 map in short: the archway 25 ft from the reeds, a shack 15 ft away (a cave hop).
    return ZoneMap(
        zones=[
            Zone(id="reeds", name="Cattail Bed"),
            Zone(id="archway", name="Broken Archway"),
            Zone(id="shack", name="Fisher's Shack"),
        ],
        edges=[
            ZoneEdge(a="reeds", b="archway", feet=25),
            ZoneEdge(a="reeds", b="shack", feet=15),
        ],
    )


def _wizard() -> Creature:
    return caster("w", "wizard", spells=["burning-hands", "fear"], level=5, slots={1: 2, 3: 1})


def _reeds_fight(foe_zone: str) -> list[Placement]:
    return [
        (_wizard(), Side.PARTY, "reeds"),
        (make_pc("ally"), Side.PARTY, "reeds"),
        (srd_monster("cultist", "cultist-1"), Side.HOSTILE, foe_zone),
    ]


def _hurt(events: Sequence[object]) -> list[str]:
    return [e.creature_id for e in events if isinstance(e, DamageTaken)]


def test_m29_self_cone_aims_at_the_chosen_zone() -> None:
    state = fight(_reeds_fight("shack"), _reeds_map())
    events = cast(state, "w", "burning-hands", ScriptedRng(1, 3, 3, 3), zone="shack")
    assert _hurt(events) == ["cultist-1"]  # the ally in the reeds is spared, the caster too


def test_m29_self_cone_too_short_for_the_edge_is_refused_and_costs_nothing() -> None:
    state = fight(_reeds_fight("archway"), _reeds_map())
    with pytest.raises(CommandRefused) as refused:
        cast(state, "w", "burning-hands", ScriptedRng(1), zone="archway")
    assert refused.value.code is RefusalCode.OUT_OF_RANGE
    assert "15-ft cone does not reach Broken Archway, 25 ft away" in refused.value.reason
    assert state.creatures["w"].resources["spell-slot-1"].current == 2


def test_m29_self_cone_in_own_zone_still_catches_allies_never_the_caster() -> None:
    state = fight(_reeds_fight("archway"), _reeds_map())
    events = cast(state, "w", "burning-hands", ScriptedRng(1, 3, 3, 3), zone="reeds")
    assert _hurt(events) == ["ally"]


def test_m29_longer_cone_reaches_a_25_ft_edge() -> None:
    state = fight(_reeds_fight("archway"), _reeds_map())
    enc = state.encounter
    assert enc is not None
    fear = REGS.spells.get("fear")
    assert area_zones(enc.zone_map, "reeds", fear) == ("reeds", "archway", "shack")
    burning = REGS.spells.get("burning-hands")
    assert area_zones(enc.zone_map, "reeds", burning) == ("reeds", "shack")
    spirit = REGS.spells.get("spirit-guardians")
    assert area_zones(enc.zone_map, "reeds", spirit) == ("reeds",)


def test_m29_bot_aims_the_cone_away_from_its_friends() -> None:
    state = fight(_reeds_fight("shack"), _reeds_map())
    rng = random.Random(3)
    command = next_pc_command(state, "w", REGS, rng)
    assert command is not None
    if isinstance(command, CastCommand) and command.spell_id == "burning-hands":
        assert command.target_zone == "shack"
    assert "ally" not in _hurt(do(state, command, rng))


def _archer() -> Creature:
    return make_pc("pa", dex=18, class_index="ranger")


def test_golden_ranged_attack_in_close_combat() -> None:
    # SRD 5.1 "Ranged Attacks in Close Combat": a ranged attack has disadvantage while a hostile
    # creature that can see you and is not incapacitated is within 5 ft (here: the same zone).
    # Fighter +5 against goblin AC 15 needs a natural 10: 11/20 = 0.55; at disadvantage
    # (11/20)^2 = 0.3025, also against a goblin in another zone.
    placements: list[Placement] = [
        (make_pc("pa"), Side.PARTY, "yard"),
        (srd_monster("goblin", "goblin-1"), Side.HOSTILE, "yard"),
        (srd_monster("goblin", "goblin-2"), Side.HOSTILE, "gate"),
    ]
    state = fight(placements)
    near = {h.option: h for h in hit_chances(state, "pa", "goblin-1", REGS.chars)}
    far = {h.option: h for h in hit_chances(state, "pa", "goblin-2", REGS.chars)}
    assert near["main_hand"].probability == pytest.approx(0.55)
    assert near["ranged"].probability == pytest.approx(0.3025)
    assert far["ranged"].probability == pytest.approx(0.3025)
    shot = AttackCommand(actor_id="pa", target_id="goblin-1", option="ranged")
    rolled = of(do(state, shot, ScriptedRng(15, 4, 3)), AttackRolled)[0]
    assert rolled.roll.adv.value == "disadvantage" and "close combat" in rolled.adv_why


def test_m29_close_combat_needs_a_foe_that_can_see() -> None:
    placements: list[Placement] = [
        (make_pc("pa"), Side.PARTY, "yard"),
        (srd_monster("goblin", "goblin-1"), Side.HOSTILE, "gate"),
    ]
    state = fight(placements)
    alone = {h.option: h for h in hit_chances(state, "pa", "goblin-1", REGS.chars)}
    assert alone["ranged"].adv.value == "normal"
    blind = srd_monster("goblin", "goblin-2")
    blind.conditions.append(_condition("blinded"))
    sleepy = srd_monster("goblin", "goblin-3")
    sleepy.conditions.append(_condition("asleep"))
    state = fight([*placements, (blind, Side.HOSTILE, "yard"), (sleepy, Side.HOSTILE, "yard")])
    still = {h.option: h for h in hit_chances(state, "pa", "goblin-1", REGS.chars)}
    assert still["ranged"].adv.value == "normal"


def _values(state: GameState, actor: str, *, monster: bool) -> dict[str, float]:
    view = ai_view(state, actor, REGS)
    assert view is not None
    if monster:
        found = monster_choices(state, view, REGS)
    else:
        found = pc_choices(state, view, REGS, "action")
    return {c.label.split("->")[0]: c.value for c in found}


def test_m29_monsters_shoot_at_disadvantage_in_close_combat_too() -> None:
    placements: list[Placement] = [
        (srd_monster("goblin", "goblin-1"), Side.HOSTILE, "yard"),
        (make_pc("pa"), Side.PARTY, "yard"),
    ]
    state = fight(placements)
    enc = state.encounter
    assert enc is not None and threatened(state, enc, "goblin-1")
    values = _values(state, "goblin-1", monster=True)
    assert values["scimitar"] > values["shortbow"]


def test_m29_bot_prefers_melee_in_close_combat() -> None:
    near: list[Placement] = [
        (_archer(), Side.PARTY, "yard"),
        (srd_monster("goblin", "goblin-1"), Side.HOSTILE, "yard"),
    ]
    state = fight(near)
    values = _values(state, "pa", monster=False)
    assert values["main_hand"] > values["ranged"]
    command = next_pc_command(state, "pa", REGS, random.Random(1))
    shoots_here = isinstance(command, AttackCommand) and command.option == "ranged"
    assert not shoots_here  # it fights in melee or steps out of reach first
    far: list[Placement] = [
        (_archer(), Side.PARTY, "gate"),
        (srd_monster("goblin", "goblin-1"), Side.HOSTILE, "yard"),
    ]
    state = fight(far)
    command = next_pc_command(state, "pa", REGS, random.Random(1))
    assert isinstance(command, AttackCommand) and command.option == "ranged"


def _condition(name: str) -> ActiveCondition:
    return new_condition(name, source_id="test")
