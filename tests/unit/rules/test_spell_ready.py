"""M41.2 round 7 Z5 (docs/playtests/M39_round7.md): a ready spell the hero has no slot for is a
NOT OFFERED target with the reason, never a stand-in. r7b-typed 1277 "Tamsin sends a guiding bolt
at the armor" (both of Tamsin's slot levels at 0 since 981 and 1128) cast Sacred Flame (1279).
Cantrips stay offered, and so does a spell a higher slot can pay for (upcasting). Fixture
m39-r7-typed, no model."""

from aidm.data.combat_data import combat_registries
from aidm.models.action_menu import ActionMenu, MenuStep
from aidm.models.state import GameState
from aidm.rules.action_menu import build_menu
from aidm.rules.menu_unoffered import not_offered, with_unoffered
from aidm.rules.spell_ready import no_slot_reason
from tests.ai.chooser_fixtures import menu_at, state_at

R7, BOLT_SEQ = "m39-r7-typed", 1277
TAMSIN, ARMOR = "pc-p8", "animated-armor-1"
LINE = "Tamsin sends a guiding bolt at the armor"
NO_SLOT = "Tamsin has no slot of 1st level or higher left"


def _menu(text: str = LINE) -> ActionMenu:
    return with_unoffered(state_at(R7, BOLT_SEQ), menu_at(R7, BOLT_SEQ, TAMSIN), text)


def _with_slot(key: str) -> GameState:
    state = state_at(R7, BOLT_SEQ).model_copy(deep=True)
    hero = state.creatures[TAMSIN]
    pool = hero.resources[key]
    hero.resources[key] = pool.model_copy(update={"current": 1})
    return state


def test_v1_m41_a_spell_with_no_slot_is_not_offered() -> None:
    menu = _menu()
    assert menu.scope.value == "fight"
    assert "cast:guiding-bolt" not in {e.id for e in menu.entries}
    (bolt,) = menu.unoffered
    assert (bolt.id, bolt.label) == ("guiding-bolt", f"Guiding Bolt ({NO_SLOT})")


def test_v1_m41_a_step_at_the_spell_is_other_never_a_stand_in() -> None:
    menu = _menu()
    by_entry = MenuStep(entry="cast:guiding-bolt", targets=(ARMOR,))
    by_target = MenuStep(entry="cast:sacred-flame", targets=("guiding-bolt",))
    assert not_offered(menu, by_entry) == ("guiding-bolt",)
    assert not_offered(menu, by_target) == ("guiding-bolt",)
    assert not_offered(menu, MenuStep(entry="cast:sacred-flame", targets=(ARMOR,))) == ()


def test_cantrips_stay_offered() -> None:
    menu = _menu()
    assert {"cast:sacred-flame", "cast:guidance"} <= {e.id for e in menu.entries}
    assert "sacred-flame" not in {t.id for t in menu.unready}


def test_a_higher_slot_still_pays_upcasting_stays_offered() -> None:
    state = _with_slot("spell-slot-2")
    menu = build_menu(state, TAMSIN, combat_registries())
    bolt = next(e for e in menu.entries if e.id == "cast:guiding-bolt")
    assert bolt.slot_level == 2
    assert not with_unoffered(state, menu, LINE).unoffered
    # M44.2: Tamsin's Preserve Life is the one unready thing (a use the table cannot play)
    assert {t.id for t in menu.unready} == {"preserve-life"}


def test_the_reason_names_the_level_when_no_higher_pool_exists() -> None:
    hero = state_at(R7, BOLT_SEQ).creatures[TAMSIN]
    assert no_slot_reason(hero, 1) == NO_SLOT
    assert no_slot_reason(hero, 2) == "Tamsin has no 2nd-level slot left"


def test_a_line_naming_no_spell_gets_none() -> None:
    menu = _menu("Tamsin calls down sacred flame on the armor")
    assert not menu.unoffered
    assert {t.id for t in menu.unready} >= {"guiding-bolt", "bless", "cure-wounds"}


def test_out_of_a_fight_the_spent_entry_names_the_spell() -> None:
    """M36.10a stays: out of a fight a no-slot spell is a spent entry the rules refuse in plain
    words. M44.2 (round 9 BB4, r9-typed 231 "Tamsin casts Bless on the party" read `other`): the
    spent entry no longer hides the spell, so a line naming it has it NOT OFFERED with the
    no-slot reason; a step at the spent entry is still the rules' plain answer."""
    at = ("p2", 662)
    state = state_at(*at)
    menu = with_unoffered(state, menu_at(*at, "pc-p4"), "Elowen casts cure wounds on Rook")
    cure = next(e for e in menu.entries if e.id == "cast:cure-wounds")
    assert cure.spent and "cure-wounds" in {t.id for t in menu.unready}
    assert [t.label for t in menu.unoffered] == ["Cure Wounds (Elowen has no 1st-level slot left)"]
    assert not not_offered(menu, MenuStep(entry=cure.id, targets=("pc-p6",)))
