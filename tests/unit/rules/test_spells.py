"""Spell DSL interpreter: refusals (nothing consumed), concentration, every effect kind, replay."""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from aidm.data.combat_data import CombatRegistries
from aidm.data.registry import Registry
from aidm.data.spell_defs import SpellDef
from aidm.models.commands import RefusalCode
from aidm.models.conditions import Concentration
from aidm.models.encounter import Side
from aidm.models.events import AnyEvent, CheckResolved, TempHpSet
from aidm.models.state import GameState
from aidm.rules.command_checks import CommandRefused
from aidm.rules.condition_timing import new_condition
from aidm.rules.spells import cast_spell
from aidm.session.reducer import apply, replay
from tests.unit.rules.combat_fixtures import REGS, ScriptedRng, economy, fight, monster
from tests.unit.rules.encounter_fixtures import make_pc
from tests.unit.rules.spell_fixtures import cast, caster, slots_left

CLERIC_SPELLS = ["cure-wounds", "bless", "shield-of-faith", "healing-word"]


def _cleric_fight() -> GameState:
    cleric = caster("c", "cleric", cantrips=["sacred-flame"], spells=CLERIC_SPELLS)
    return fight(
        [
            (cleric, Side.PARTY, "gate"),
            (make_pc("b"), Side.PARTY, "gate"),
            (monster("gob", hp=30), Side.HOSTILE, "yard"),
            (monster("far", hp=30), Side.HOSTILE, "wall"),
        ]
    )


def _refused(
    state: GameState,
    spell: str,
    code: RefusalCode,
    *,
    targets: Sequence[str] = (),
    slot: int | None = None,
) -> None:
    before = state.model_dump()
    with pytest.raises(CommandRefused) as refused:
        cast(state, "c", spell, ScriptedRng(), targets=targets, slot=slot)
    assert refused.value.code is code
    assert state.model_dump() == before


def test_cast_refusals_consume_nothing() -> None:
    state = _cleric_fight()
    _refused(state, "sleep", RefusalCode.UNKNOWN_SPELL, targets=["gob"])
    _refused(state, "magic-missile", RefusalCode.SPELL_NOT_READY, targets=["gob"])
    _refused(state, "sacred-flame", RefusalCode.NO_SLOT, targets=["gob"], slot=1)
    _refused(state, "sacred-flame", RefusalCode.OUT_OF_RANGE, targets=["far"])
    _refused(state, "sacred-flame", RefusalCode.BAD_TARGETS, targets=["gob", "far"])
    _refused(state, "sacred-flame", RefusalCode.BAD_TARGETS)
    _refused(state, "bless", RefusalCode.BAD_TARGETS, targets=["b", "b"])
    _refused(state, "bless", RefusalCode.BAD_TARGETS, targets=["c", "b", "gob", "far"])
    _refused(state, "cure-wounds", RefusalCode.OUT_OF_RANGE, targets=["gob"])
    _refused(state, "cure-wounds", RefusalCode.NO_SLOT, targets=["b"], slot=3)
    _refused(state, "cure-wounds", RefusalCode.UNKNOWN_TARGET, targets=["nobody"])
    assert economy(state, "c").action and slots_left(state.creatures["c"], 1) == 2


def test_non_caster_and_empty_slots_are_refused() -> None:
    state = fight([(make_pc("c"), Side.PARTY, "gate"), (monster("gob"), Side.HOSTILE, "gate")])
    _refused(state, "cure-wounds", RefusalCode.NOT_A_CASTER, targets=["gob"])
    state = _cleric_fight()
    state.creatures["c"].resources["spell-slot-1"] = (
        state.creatures["c"].resources["spell-slot-1"].model_copy(update={"current": 0})
    )
    _refused(state, "bless", RefusalCode.NO_SLOT, targets=["b"])


def test_bonus_action_spell_needs_the_bonus_action() -> None:
    state = _cleric_fight()
    cast(state, "c", "healing-word", ScriptedRng(1), targets=["b"])
    _refused(state, "shield-of-faith", RefusalCode.NO_BONUS_ACTION, targets=["b"])
    cast(state, "c", "bless", ScriptedRng(), targets=["b"])
    assert not economy(state, "c").action


def test_blessed_save_adds_1d4() -> None:
    state = _cleric_fight()
    state.creatures["gob"].conditions.append(new_condition("blessed"))
    events = cast(state, "c", "sacred-flame", ScriptedRng(3, 10), targets=["gob"])
    save = [e for e in events if isinstance(e, CheckResolved)][0].result
    assert save.roll.total == 13 and save.success


def test_incapacitated_target_loses_concentration() -> None:
    cleric = caster("c", "cleric", spells=["hold-person"], level=3, slots={2: 1})
    state = fight([(cleric, Side.PARTY, "gate"), (make_pc("w"), Side.HOSTILE, "gate")])
    state.creatures["w"].concentrating_on = Concentration(spell_id="bless")
    cast(state, "c", "hold-person", ScriptedRng(1), targets=["w"])
    assert state.creatures["w"].concentrating_on is None


SYNTHETIC: list[dict[str, object]] = [
    {
        "index": "false-life",
        "level": 1,
        "school": "necromancy",
        "classes": ["wizard"],
        "range": {"kind": "self"},
        "targeting": {"kind": "self"},
        "effects": [{"type": "temp_hp", "dice": "1d4+4", "upcast_dice": "5"}],
    },
    {
        "index": "grease",
        "level": 1,
        "school": "conjuration",
        "classes": ["wizard"],
        "range": {"kind": "feet", "feet": 60},
        "targeting": {"kind": "area", "area": "zone"},
        "effects": [
            {"type": "surface", "surface": "oil", "rounds": 10},
            {
                "type": "save",
                "ability": "dex",
                "on_fail": [{"type": "apply_condition", "condition": "prone"}],
            },
        ],
    },
    {
        "index": "lesser-restoration",
        "level": 2,
        "school": "abjuration",
        "classes": ["cleric"],
        "range": {"kind": "touch"},
        "targeting": {"kind": "creature"},
        "effects": [{"type": "remove_condition", "conditions": ["blinded", "poisoned"]}],
    },
    {
        "index": "acid-splash",
        "level": 0,
        "school": "conjuration",
        "classes": ["wizard"],
        "range": {"kind": "feet", "feet": 60},
        "targeting": {"kind": "creature"},
        "effects": [
            {
                "type": "save",
                "ability": "dex",
                "on_fail": [{"type": "damage", "dice": "1d6", "damage_type": "acid"}],
            },
            {
                "type": "multi_target",
                "area": "zone",
                "effects": [
                    {
                        "type": "save",
                        "ability": "dex",
                        "on_fail": [{"type": "damage", "dice": "1d6", "damage_type": "acid"}],
                    }
                ],
            },
        ],
    },
]
CUSTOM = CombatRegistries(
    chars=REGS.chars,
    consumables=REGS.consumables,
    spells=Registry(SpellDef.model_validate(s) for s in SYNTHETIC),
)


def _wizard_fight() -> GameState:
    wiz = caster(
        "w",
        "wizard",
        cantrips=["acid-splash"],
        spells=["false-life", "grease", "lesser-restoration"],
        level=3,
        slots={1: 2, 2: 2},
    )
    return fight(
        [
            (wiz, Side.PARTY, "gate"),
            (make_pc("b"), Side.PARTY, "gate"),
            (monster("gob", hp=30), Side.HOSTILE, "yard"),
            (monster("gob2", hp=30), Side.HOSTILE, "yard"),
        ]
    )


def _cast_custom(
    state: GameState,
    spell: str,
    rng: ScriptedRng,
    *,
    targets: Sequence[str] = (),
    zone: str | None = None,
    slot: int | None = None,
) -> list[AnyEvent]:
    events = cast_spell(state, "w", CUSTOM.spells.get(spell), slot, targets, zone, rng, CUSTOM)
    for event in events:
        apply(state, event)
    return events


def test_temp_hp_with_upcast() -> None:
    state = _wizard_fight()
    events = _cast_custom(state, "false-life", ScriptedRng(2), slot=2)
    assert [e.temp_hp for e in events if isinstance(e, TempHpSet)] == [11]


def test_surface_and_area_condition() -> None:
    state = _wizard_fight()
    _cast_custom(state, "grease", ScriptedRng(5, 20), zone="yard")
    assert state.encounter is not None
    surfaces = state.encounter.zone_map.zone("yard").surfaces
    assert [(s.kind, s.rounds_left, s.source_id) for s in surfaces] == [("oil", 10, "w")]
    assert [c.name for c in state.creatures["gob"].conditions] == ["prone"]
    assert state.creatures["gob2"].conditions == []


def test_remove_condition() -> None:
    state = _wizard_fight()
    state.creatures["b"].conditions.append(new_condition("poisoned"))
    _cast_custom(state, "lesser-restoration", ScriptedRng(), targets=["b"])
    assert state.creatures["b"].conditions == []


def test_multi_target_splash_hits_the_rest_of_the_zone() -> None:
    state = _wizard_fight()
    _cast_custom(state, "acid-splash", ScriptedRng(5, 4, 5, 3), targets=["gob"])
    assert (state.creatures["gob"].hp, state.creatures["gob2"].hp) == (26, 27)


def test_out_of_combat_healing_works_but_attack_spells_need_a_fight() -> None:
    cleric = caster("c", "cleric", cantrips=["sacred-flame"], spells=CLERIC_SPELLS)
    state = GameState(campaign_id="calm", seed=1)
    state.creatures["c"] = cleric
    state.creatures["b"] = make_pc("b")
    state.creatures["b"].hp = 2
    spells = REGS.spells
    events = cast_spell(
        state, "c", spells.get("cure-wounds"), None, ["b"], None, ScriptedRng(5), REGS
    )
    for event in events:
        apply(state, event)
    assert state.creatures["b"].hp == 12
    with pytest.raises(CommandRefused) as refused:
        cast_spell(state, "c", spells.get("sacred-flame"), None, ["b"], None, ScriptedRng(), REGS)
    assert refused.value.code is RefusalCode.NOT_IN_COMBAT


def test_spell_events_replay_to_the_same_state() -> None:
    state = _cleric_fight()
    initial = state.model_copy(deep=True)
    log: list[AnyEvent] = []
    log += cast(state, "c", "shield-of-faith", ScriptedRng(), targets=["b"])
    log += cast(state, "c", "bless", ScriptedRng(), targets=["c", "b"])
    assert replay(initial, log).model_dump() == state.model_dump()
