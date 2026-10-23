"""M29.9a T20: a wizard's prepared spells at level-up (docs/playtests/M29_round3.md), from the
r3-full save: Tamsin (wizard, Int 15, then 17 after the level 4 ASI)."""

from aidm.dm.tool_context import tool_registries
from aidm.models.abilities import Ability
from aidm.models.events import LevelGained
from aidm.models.leveling import LevelUpChoices
from aidm.rules.level_options import level_up_options
from aidm.rules.leveling import level_up
from aidm.rules.spellcasting import prepared_spell_limit
from tests.session.playtest_saves import replay_until


def _gained(seq: int, choices: LevelUpChoices) -> LevelGained:
    state = replay_until("r3-full", seq)
    events = level_up(state.creatures["pc-p8"], choices, tool_registries().combat.chars)
    return next(e for e in events if isinstance(e, LevelGained))


def test_golden_m29_wizard_prepared_count() -> None:
    # SRD 5.1 Wizard "Preparing and Casting Spells": Intelligence modifier + wizard level
    # (minimum 1). Int 15 (+2): level 2 -> 4, level 3 -> 5; Int 17 (+3): level 4 -> 7,
    # level 5 -> 8.
    wizard = tool_registries().combat.chars.classes.get("wizard")
    for level, score, count in ((2, 15, 4), (3, 15, 5), (4, 17, 7), (5, 17, 8)):
        assert prepared_spell_limit(wizard, level, {Ability.INT: score}) == count


def test_m29_level_up_keeps_prepared_spells() -> None:
    """r3-full 532: at level 3 the re-picked list dropped thunderwave for two new spells. The
    prepared spells now stay and the new room (one spell) takes the first pick."""
    picks = LevelUpChoices(spells=["scorching-ray", "acid-arrow"], prepared=["scorching-ray"])
    pc = _gained(532, picks).pc
    assert pc.prepared == [
        "magic-missile",
        "burning-hands",
        "sleep",
        "thunderwave",
        "scorching-ray",
    ]


def test_m29_level_up_counts_the_asi() -> None:
    """r3-full 1084: level 4 with +2 Int (15 -> 17) prepared 6, one short of Int 17's 7. With
    no prepared picks the room fills from the spells just written into the book."""
    state = replay_until("r3-full", 1084)
    hero = state.creatures["pc-p8"].pc
    assert hero is not None
    before = list(hero.prepared)
    picks = LevelUpChoices(
        asi={Ability.INT: 2}, cantrips=["chill-touch"], spells=["shatter", "hold-person"]
    )
    pc = _gained(1084, picks).pc
    assert len(pc.prepared) == 7
    assert pc.prepared[: len(before)] == before
    assert {"shatter", "hold-person"} <= set(pc.prepared)


def test_m29_level_up_options_offer_only_the_new_room() -> None:
    state = replay_until("r3-full", 532)
    tamsin = state.creatures["pc-p8"]
    options = level_up_options(tamsin, tool_registries().combat.chars)
    assert options is not None and options.prepared is not None
    assert options.prepared.choose == 1
    assert tamsin.pc is not None
    assert not {o.id for o in options.prepared.options} & set(tamsin.pc.prepared)
