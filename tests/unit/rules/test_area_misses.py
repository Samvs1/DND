"""Who an area spell left untouched, and why (M40.5, round 7 Z10): `rules.area_misses`."""

from aidm.data.combat_data import combat_registries
from aidm.models.combat_events import SpellCast
from aidm.models.damage import DamageType
from aidm.models.events import AnyEvent
from aidm.models.state import GameState
from aidm.rules.area_misses import AreaMiss, MissReason, area_misses
from tests.unit.rules.combat_fixtures import ScriptedRng
from tests.unit.rules.spell_fixtures import battle, cast, caster, conditions_of


def _misses(state: GameState, events: list[AnyEvent]) -> tuple[AreaMiss, ...]:
    spell_cast = next(e for e in events if isinstance(e, SpellCast))
    spell = combat_registries().spells.find(spell_cast.spell_id)
    assert spell is not None
    return area_misses(state, spell, spell_cast, events)


def test_sleep_names_the_undead_and_the_one_its_pool_did_not_reach() -> None:
    # SRD 5.1 Sleep: 5d8 hit points, lowest current HP first; undead and the charm-immune are
    # not affected. Pool 15: gob2 (5) sleeps, gob (12 > 10 left) does not.
    wiz = caster("w", "wizard", spells=["sleep"], slots={1: 1})
    state = battle(wiz, ("gob", "yard"), ("gob2", "yard"), ("gbone", "yard"))
    state.creatures["gob"].hp, state.creatures["gob2"].hp = 12, 5
    state.creatures["gbone"].creature_type = "undead"
    events = cast(state, "w", "sleep", ScriptedRng(3, 3, 3, 3, 3), zone="yard")
    assert conditions_of(state, "gob2") == ["asleep"]
    assert _misses(state, events) == (
        AreaMiss("gob", MissReason.POOL),
        AreaMiss("gbone", MissReason.EXCLUDED, "undead"),
    )


def test_a_save_that_succeeds_is_named_saved() -> None:
    # Hypnotic Pattern: WIS save or charmed and incapacitated; gob fails (5), gob2 saves (20).
    wiz = caster("w", "wizard", spells=["hypnotic-pattern"], level=5, slots={3: 1})
    state = battle(wiz, ("gob", "yard"), ("gob2", "yard"))
    events = cast(state, "w", "hypnotic-pattern", ScriptedRng(5, 20), zone="yard")
    assert _misses(state, events) == (AreaMiss("gob2", MissReason.SAVED),)


def test_damage_that_does_no_harm_is_named_no_harm() -> None:
    wiz = caster("w", "wizard", spells=["burning-hands"], slots={1: 1})
    state = battle(wiz, ("gob", "gate"))
    state.creatures["gob"].immunities = [DamageType.FIRE]
    events = cast(state, "w", "burning-hands", ScriptedRng(5, 3, 4, 5))
    assert _misses(state, events) == (AreaMiss("gob", MissReason.NO_HARM),)


def test_a_creature_the_spell_affected_is_no_miss() -> None:
    wiz = caster("w", "wizard", spells=["sleep"], slots={1: 1})
    state = battle(wiz, ("gob", "yard"))
    state.creatures["gob"].hp = 5
    events = cast(state, "w", "sleep", ScriptedRng(3, 3, 3, 3, 3), zone="yard")
    assert _misses(state, events) == ()
