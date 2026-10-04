"""Hypothesis helpers that draw events valid for the current state (shared by property tests)."""

from __future__ import annotations

import functools
import random
from collections.abc import Callable

from hypothesis import strategies as st

from aidm.data.character_data import character_registries
from aidm.models.abilities import Ability, Skill
from aidm.models.checks import DcTier
from aidm.models.conditions import (
    Concentration,
    ConditionDuration,
    ConditionLink,
    SaveEnds,
    TurnBoundary,
)
from aidm.models.damage import DamagePart, DamageType
from aidm.models.events import (
    AnyEvent,
    CampSuppliesChanged,
    CheckResolved,
    ConcentrationEnded,
    ConcentrationStarted,
    ConditionApplied,
    ConditionRemoved,
    ConditionTicked,
    CreatureAdded,
    CreatureDied,
    CreatureRemoved,
    DamageTaken,
    DeathSaveRolled,
    DeathSavesSet,
    DiceRolled,
    HpChanged,
    LongRestTaken,
    ResourceSet,
    ShortRestTaken,
    Stabilized,
    TempHpSet,
)
from aidm.models.state import (
    ActiveCondition,
    Creature,
    CreatureKind,
    GameState,
    RechargeKind,
    Resource,
)
from aidm.rules.checks import dc_for_tier, saving_throw, skill_check
from aidm.rules.creation import build_character
from aidm.rules.d20 import roll_d20
from aidm.rules.dice import roll
from tests.unit.rules.creation_fixtures import default_choices

CONDITIONS = ["prone", "poisoned", "frightened", "blinded"]
SOURCES = [None, "src1", "src2"]
DAMAGE_TYPE_LISTS = st.lists(st.sampled_from(list(DamageType)), unique=True, max_size=3)
NAMES = st.text(alphabet="abcdefghijklmnopqrstuvwxyz '-", min_size=1, max_size=12)


@functools.cache
def _pc_template(class_index: str) -> Creature:
    choices = default_choices(class_index, "human", None)
    return build_character(choices, character_registries(), "template")


def draw_creature(data: st.DataObject, cid: str) -> Creature:
    if data.draw(st.integers(0, 4)) == 0:
        template = _pc_template(data.draw(st.sampled_from(["fighter", "wizard", "warlock"])))
        return template.model_copy(update={"id": cid}, deep=True)
    max_hp = data.draw(st.integers(min_value=1, max_value=200))
    scores = data.draw(st.lists(st.integers(1, 30), min_size=6, max_size=6))
    return Creature(
        id=cid,
        name=data.draw(NAMES),
        kind=data.draw(st.sampled_from(list(CreatureKind))),
        abilities=dict(zip(Ability, scores, strict=True)),
        max_hp=max_hp,
        hp=data.draw(st.integers(min_value=0, max_value=max_hp)),
        ac=data.draw(st.integers(min_value=5, max_value=25)),
        proficiency_bonus=data.draw(st.integers(2, 6)),
        save_proficiencies=data.draw(st.lists(st.sampled_from(list(Ability)), unique=True)),
        skill_proficiencies=data.draw(st.lists(st.sampled_from(list(Skill)), unique=True)),
        skill_expertise=data.draw(st.lists(st.sampled_from(list(Skill)), unique=True)),
        resistances=data.draw(DAMAGE_TYPE_LISTS),
        immunities=data.draw(DAMAGE_TYPE_LISTS),
        vulnerabilities=data.draw(DAMAGE_TYPE_LISTS),
        death_saves=data.draw(st.sampled_from([None, True, False])),
    )


def _hp(data: st.DataObject, c: Creature) -> AnyEvent:
    new_hp = data.draw(st.integers(min_value=0, max_value=c.max_hp))
    return HpChanged(creature_id=c.id, delta=new_hp - c.hp, new_hp=new_hp)


def _temp(data: st.DataObject, c: Creature) -> AnyEvent:
    return TempHpSet(creature_id=c.id, temp_hp=data.draw(st.integers(0, 50)))


def _cond_on(data: st.DataObject, c: Creature) -> AnyEvent:
    rounds = data.draw(st.one_of(st.none(), st.integers(0, 10)))
    if rounds is None:
        duration = data.draw(
            st.sampled_from([ConditionDuration.UNTIL_REMOVED, ConditionDuration.UNTIL_LONG_REST])
        )
    else:
        duration = ConditionDuration.ROUNDS
    save = data.draw(st.sampled_from([None, SaveEnds(ability=Ability.WIS, dc=13)]))
    cond = ActiveCondition(
        name=data.draw(st.sampled_from(CONDITIONS)),
        source_id=data.draw(st.sampled_from(SOURCES)),
        duration=duration,
        rounds_left=rounds,
        tick_on=data.draw(st.sampled_from(list(TurnBoundary))),
        tick_creature_id=data.draw(st.sampled_from(SOURCES)),
        save_ends=save,
    )
    return ConditionApplied(creature_id=c.id, condition=cond)


def _cond_off(data: st.DataObject, c: Creature) -> AnyEvent:
    return ConditionRemoved(
        creature_id=c.id,
        name=data.draw(st.sampled_from(CONDITIONS)),
        source_id=data.draw(st.sampled_from(SOURCES)),
        exact_source=data.draw(st.booleans()),
    )


def _cond_tick(data: st.DataObject, c: Creature) -> AnyEvent:
    ticking = [x for x in c.conditions if x.rounds_left is not None]
    if not ticking:
        return _cond_on(data, c)
    target = data.draw(st.sampled_from(ticking))
    return ConditionTicked(
        creature_id=c.id,
        name=target.name,
        source_id=target.source_id,
        rounds_left=data.draw(st.integers(1, 10)),
    )


def _conc_on(data: st.DataObject, c: Creature) -> AnyEvent:
    links = data.draw(
        st.lists(
            st.builds(
                ConditionLink,
                creature_id=st.sampled_from(["c0", "c1", "c2"]),
                name=st.sampled_from(CONDITIONS),
            ),
            max_size=3,
        )
    )
    spell = data.draw(st.sampled_from(["bless", "hold-person", "hex"]))
    return ConcentrationStarted(
        creature_id=c.id, concentration=Concentration(spell_id=spell, links=tuple(links))
    )


def _death_save(data: st.DataObject, c: Creature) -> AnyEvent:
    d20 = roll_d20(random.Random(data.draw(st.integers(0, 10_000))))
    return DeathSaveRolled(
        creature_id=c.id,
        roll=d20,
        successes=data.draw(st.integers(0, 3)),
        failures=data.draw(st.integers(0, 3)),
    )


def _dice(data: st.DataObject, c: Creature) -> AnyEvent:
    expr = data.draw(st.sampled_from(["1d20+5", "2d6+3", "8d6", "4d6kh3", "1d4-1"]))
    rolled = roll(expr, random.Random(data.draw(st.integers(0, 10_000))))
    return DiceRolled(roll=rolled, roller_id=c.id, label=data.draw(NAMES))


def _check(data: st.DataObject, c: Creature) -> AnyEvent:
    rng = random.Random(data.draw(st.integers(0, 10_000)))
    dc = dc_for_tier(data.draw(st.sampled_from(list(DcTier))))
    if data.draw(st.booleans()):
        result = skill_check(rng, c, data.draw(st.sampled_from(list(Skill))), dc)
    else:
        result = saving_throw(rng, c, data.draw(st.sampled_from(list(Ability))), dc)
    return CheckResolved(creature_id=c.id, result=result, reason=data.draw(NAMES))


def _damage_log(data: st.DataObject, c: Creature) -> AnyEvent:
    rolled = data.draw(st.integers(0, 40))
    part = DamagePart(
        damage_type=data.draw(st.sampled_from(list(DamageType))),
        rolled=rolled,
        taken=data.draw(st.integers(0, rolled * 2)),
    )
    return DamageTaken(
        creature_id=c.id,
        parts=(part,),
        total=part.taken,
        temp_absorbed=min(part.taken, c.temp_hp),
        crit=data.draw(st.booleans()),
        source_id=data.draw(st.sampled_from(SOURCES)),
    )


def _death_state(data: st.DataObject, c: Creature) -> AnyEvent:
    return DeathSavesSet(
        creature_id=c.id,
        successes=data.draw(st.integers(0, 3)),
        failures=data.draw(st.integers(0, 3)),
        stable=data.draw(st.booleans()),
    )


def _resource(data: st.DataObject, c: Creature) -> AnyEvent:
    maximum = data.draw(st.integers(0, 4))
    resource = Resource(
        current=data.draw(st.integers(0, maximum)),
        maximum=maximum,
        recharge=data.draw(st.sampled_from(list(RechargeKind))),
    )
    key = data.draw(st.sampled_from(["pact-slot-1", "rage", "ki"]))
    return ResourceSet(creature_id=c.id, key=key, resource=resource)


def _party(data: st.DataObject, _c: Creature) -> AnyEvent:
    supplies = data.draw(st.integers(0, 200))
    return data.draw(
        st.sampled_from(
            [
                CampSuppliesChanged(delta=data.draw(st.integers(-50, 50)), camp_supplies=supplies),
                ShortRestTaken(short_rests_used=data.draw(st.integers(1, 2))),
                LongRestTaken(supplies_spent=data.draw(st.integers(0, 40)), camp_supplies=supplies),
            ]
        )
    )


TARGETED: list[Callable[[st.DataObject, Creature], AnyEvent]] = [
    _hp,
    _temp,
    _cond_on,
    _cond_off,
    _cond_tick,
    _conc_on,
    lambda _d, c: ConcentrationEnded(creature_id=c.id, spell_id="bless", reason="test"),
    _death_save,
    _resource,
    _party,
    _dice,
    _check,
    _damage_log,
    _death_state,
    lambda _d, c: Stabilized(creature_id=c.id),
    lambda _d, c: CreatureDied(creature_id=c.id),
    lambda _d, c: CreatureRemoved(creature_id=c.id),
]


def draw_event(data: st.DataObject, state: GameState, next_id: int) -> AnyEvent:
    """Draw one event that is valid for `state` (adds a creature when there are none)."""
    if not state.creatures or data.draw(st.integers(0, 5)) == 0:
        return CreatureAdded(creature=draw_creature(data, f"c{next_id}"))
    target = state.creatures[data.draw(st.sampled_from(sorted(state.creatures)))]
    return data.draw(st.sampled_from(TARGETED))(data, target)
