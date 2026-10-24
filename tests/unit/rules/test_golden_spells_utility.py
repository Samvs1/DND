"""Golden data for the utility cantrips (M31.2a, SRD 5.1 spell descriptions) and the two generic
effect kinds they use: `light_source` (a carried light, a torch's path) and `utility` (a no-op the
story fills). Light must give the party away in a dark place exactly as a torch does."""

from __future__ import annotations

from aidm.data.combat_data import combat_registries
from aidm.data.spell_defs import LightSourceEffect, UtilityEffect, spell_defs
from aidm.dm.item_text import ITEM_EVENT_LINES
from aidm.models.abilities import Skill
from aidm.models.combat_events import SpellCast
from aidm.models.events import AnyEvent
from aidm.models.item_events import LightLit, PlaceAlerted
from aidm.models.state import GameState
from aidm.rules.item_effects import gear_name
from aidm.rules.light import hero_light, sight_darkness
from aidm.rules.spells import cast_spell
from aidm.session.reducer import apply
from tests.unit.rules.combat_fixtures import REGS, ScriptedRng
from tests.unit.rules.item_fixtures import CAVE, DOCKS, at, hero, run, use
from tests.unit.rules.spell_fixtures import battle, cast, caster, of

REACH = {"light": "touching", "dancing-lights": "zone"}


def _spell(index: str, *, rng: str, minutes: bool = False) -> None:
    spell = spell_defs().get(index)
    assert spell.level == 0 and spell.targeting.kind == "self" and spell.range.kind == "self"
    assert (spell.casting_time == "minutes") == minutes
    assert rng  # the SRD range is in the comment of the caller; the cast is always on the caster


def _cast_out(state: GameState, who: str, spell: str) -> list[AnyEvent]:
    events = cast_spell(
        state, who, spell_defs().get(spell), None, [who], None, ScriptedRng(), combat_registries()
    )
    for event in events:
        apply(state, event)
    return events


def test_golden_spell_light() -> None:
    # SRD 5.1 Light: touch, 1 hour, bright light 20 ft (a torch's), no concentration; the
    # classes are bard, cleric, sorcerer, wizard.
    _spell("light", rng="touch")
    spell = spell_defs().get("light")
    assert spell.concentration is False and spell.duration_rounds is None
    assert spell.effects == (LightSourceEffect(reach="touching"),)
    assert set(spell.classes) == {"bard", "cleric", "sorcerer", "wizard"}


def test_golden_spell_dancing_lights() -> None:
    # SRD 5.1 Dancing Lights: 120 ft, concentration up to 1 minute (10 rounds), torch-like lights.
    _spell("dancing-lights", rng="120 ft")
    spell = spell_defs().get("dancing-lights")
    assert (spell.concentration, spell.duration_rounds) == (True, 10)
    assert spell.effects == (LightSourceEffect(reach="zone"),)
    assert set(spell.classes) == {"bard", "sorcerer", "wizard"}


def test_golden_spell_mage_hand() -> None:
    # SRD 5.1 Mage Hand: 30 ft, 1 minute, no concentration listed in the SRD data.
    _spell("mage-hand", rng="30 ft")
    assert spell_defs().get("mage-hand").concentration is False
    assert set(spell_defs().get("mage-hand").classes) == {"bard", "sorcerer", "warlock", "wizard"}


def test_golden_spell_prestidigitation() -> None:
    # SRD 5.1 Prestidigitation: 10 ft, up to 1 hour, bard sorcerer warlock wizard.
    _spell("prestidigitation", rng="10 ft")
    assert set(spell_defs().get("prestidigitation").classes) == {
        "bard",
        "sorcerer",
        "warlock",
        "wizard",
    }


def test_golden_spell_thaumaturgy() -> None:
    # SRD 5.1 Thaumaturgy: 30 ft, 1 minute, cleric only.
    _spell("thaumaturgy", rng="30 ft")
    assert spell_defs().get("thaumaturgy").classes == ("cleric",)


def test_golden_spell_minor_illusion() -> None:
    # SRD 5.1 Minor Illusion: 30 ft, 1 minute, illusion.
    _spell("minor-illusion", rng="30 ft")
    assert spell_defs().get("minor-illusion").school == "illusion"


def test_golden_spell_mending() -> None:
    # SRD 5.1 Mending: touch, casting time 1 minute (a "minutes" spell: never in a fight).
    _spell("mending", rng="touch", minutes=True)
    assert set(spell_defs().get("mending").classes) == {
        "bard",
        "cleric",
        "druid",
        "sorcerer",
        "wizard",
    }


def test_golden_spell_message() -> None:
    # SRD 5.1 Message: 120 ft, 1 round, bard sorcerer wizard.
    _spell("message", rng="120 ft")
    assert set(spell_defs().get("message").classes) == {"bard", "sorcerer", "wizard"}


def test_utility_effect_changes_nothing_but_the_cast() -> None:
    # The interpreter runs `utility` as a no-op: the cast is told, nothing else moves.
    wiz = caster("w", "wizard", cantrips=["mage-hand"])
    state = battle(wiz, ("gob", "yard"))
    before = state.creatures["gob"].hp
    events = cast(state, "w", "mage-hand", ScriptedRng(), targets=["w"])
    assert [type(e).__name__ for e in events if isinstance(e, SpellCast)] == ["SpellCast"]
    assert not of(events, LightLit) and state.creatures["gob"].hp == before
    assert all(isinstance(e, UtilityEffect) for e in spell_defs().get("mage-hand").effects)


def test_light_source_effect_lights_the_caster_like_a_torch() -> None:
    state = at(DOCKS, caster("w", "wizard", cantrips=["light"]))
    events = _cast_out(state, "w", "light")
    lit = of(events, LightLit)
    assert [(e.creature_id, e.item, e.reach) for e in lit] == [("w", "light", "touching")]
    assert hero_light(state, "w") is not None
    assert not of(events, PlaceAlerted)  # a daylit place: nothing to be seen against
    assert gear_name("dancing-lights") == "dancing lights"


def test_light_shows_the_stealth_effect_the_way_a_torch_does() -> None:
    # Light in a dark place: LightLit, then PlaceAlerted("light"), and the same warning line.
    wiz = caster("w", "wizard", cantrips=["light"])
    state = at(CAVE, wiz)
    events = _cast_out(state, "w", "light")
    assert [e.reason for e in of(events, PlaceAlerted)] == ["light"]
    assert (state.world.alerted, state.world.alerted_by) == (CAVE, "light")
    assert sight_darkness(state, Skill.PERCEPTION) == ()  # lit: no darkness penalty either
    spell_line = ITEM_EVENT_LINES[LightLit](state, of(events, LightLit)[0])
    torch_state = at(CAVE, hero("hero", gear=[("torch", 1)]))
    torch_events = use(torch_state, "torch")
    run(torch_state, torch_events)
    torch_line = ITEM_EVENT_LINES[LightLit](torch_state, of(torch_events, LightLit)[0])
    assert spell_line is not None and torch_line is not None
    warning = torch_line.split(". ", 1)[1]
    assert warning and spell_line.endswith(warning)
    assert [type(e) for e in torch_events if isinstance(e, PlaceAlerted)] == [PlaceAlerted]


def test_light_does_not_alert_twice() -> None:
    state = at(CAVE, caster("w", "wizard", cantrips=["light"]))
    _cast_out(state, "w", "light")
    again = _cast_out(state, "w", "light")
    assert not of(again, PlaceAlerted)
    assert REGS.spells.find("light") is not None
