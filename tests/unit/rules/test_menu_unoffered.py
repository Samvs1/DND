"""M38.4 cause A: names the hero means but the menu cannot act on are not-offered targets, and a
step at a target its entry cannot act on is the storyteller's, never a swapped target (the
M38.3 live eval, docs/playtests/M38_eval.md). Real replayed states, no model."""

from aidm.models.action_menu import ActionMenu, MenuStep
from aidm.rules.acts import HeroHandIntent, RefusedIntent
from aidm.rules.menu_steps import step_acts
from aidm.rules.menu_unoffered import (
    MAX_UNOFFERED,
    named_off,
    not_offered,
    off_targets,
    takers,
    unoffered_targets,
    with_unoffered,
)
from tests.ai.chooser_fixtures import FIGHT_SEQ, REGS, TYPED, menu_at, state_at

LOCKET = ("m31-r4-full", 638)  # Elowen; Rook carries the Sister's Locket
CHIME = ("r2-p7", 868)  # Brienne carries the chime; Brother Vale is elsewhere
CROWBAR = ("r2-p7", 68)  # "Brienne gives the spare crowbar to Elowen."
DOWNED = ("m32-r5-typed", 281)  # Brienne; Elowen down, Rook standing
TOLL = ("m32-r5-typed", 61)  # Brienne; a thug waits, Reeve Hallick stands by


def _unoffered(at: tuple[str, int], actor: str, text: str) -> ActionMenu:
    return with_unoffered(state_at(*at), menu_at(*at, actor), text)


def test_v1_m38_an_allys_keepsake_is_not_offered() -> None:
    """Row m31-r4-full:638: the model swapped a carried item in for Rook's locket."""
    line = "Elowen holds up the Sister's Locket and calls softly to Brother Mallow"
    menu = _unoffered(LOCKET, "pc-p4", line)
    (locket,) = menu.unoffered
    assert (locket.id, locket.label, locket.kind) == (
        "sister-s-locket",
        "Sister's Locket (Rook carries it)",
        "thing",
    )
    named = {t for e in menu.entries for t in (*e.target_ids, *e.zone_ids, e.id)}
    assert "sister-s-locket" not in named and "sister-s-locket" not in {t.id for t in menu.targets}


def test_a_person_not_here_is_never_not_offered() -> None:
    """M38.5 fix: "we head back to Bramble Pike's stall" named a person who is away as colour and
    drew a stray other; people not here are no longer listed."""
    line = "Brienne picks up the unfinished chime and carries it back toward Brother Vale."
    assert _unoffered(CHIME, "pc-p2", line).unoffered == ()
    at = ("m32-r5-typed", 588)
    pike = "With coin in our pockets we head back to Bramble Pike's stall at the Briar Vein"
    assert unoffered_targets(state_at(*at), menu_at(*at, "pc-p6"), pike) == ()
    step = MenuStep(entry="hand:unfinished-chime", targets=("brother-vale",))
    assert named_off(menu_at(*CHIME, "pc-p2"), step) == ("brother-vale",)


def test_names_the_menu_acts_on_are_never_not_offered() -> None:
    state, menu = state_at(*DOWNED), menu_at(*DOWNED, "pc-p2")
    for line in ("I help Elowen up", "I hand Rook my torch", "We travel to Hollowgate Cross"):
        assert unoffered_targets(state, menu, line) == ()
    shown = with_unoffered(state, menu, "I help Elowen up")
    assert shown.unoffered == ()
    assert shown.entries is menu.entries and shown.targets is menu.targets
    assert menu.helpers == ("pc-p6", "pc-p8") and shown.helpers == ()  # M41.3: none named


def test_a_name_inside_a_shown_name_is_that_one() -> None:
    """ "descending to the Saltwright's forge" names the place."""
    at = ("r2-p4", 1690)
    line = "We take a long rest here at the gate before descending to the Saltwright's forge"
    assert unoffered_targets(state_at(*at), menu_at(*at, "pc-p2"), line) == ()


def test_not_offered_targets_are_capped_in_line_order() -> None:
    state, menu = state_at(*LOCKET), menu_at(*LOCKET, "pc-p4")
    line = "I hold up the Sister's Locket " * (MAX_UNOFFERED + 2)
    assert len(unoffered_targets(state, menu, line)) == 1  # one thing, however often named
    assert MAX_UNOFFERED == 4


def test_v1_m38_help_up_at_a_standing_hero_is_off() -> None:
    """Router line "I help Rook up" (Rook stands): help_up lists only the downed Elowen."""
    menu = menu_at(*DOWNED, "pc-p2")
    assert off_targets(menu, MenuStep(entry="help_up", targets=("pc-p6",))) == ("pc-p6",)
    assert off_targets(menu, MenuStep(entry="help_up", targets=("pc-p4",))) == ()
    acts = step_acts(state_at(*DOWNED), menu, MenuStep(entry="help_up", targets=("pc-p6",)), REGS)
    help_up = next(e for e in menu.entries if e.id == "help_up")
    assert acts == [RefusedIntent("pc-p2", f"{help_up.label} cannot be done now.")]  # M43.2


def test_v1_m38_talk_to_a_waiting_monster_and_pay_to_a_hero_are_off() -> None:
    """ "Rook bows low to the thug" became talk to Reeve Hallick; "10 gold for Brienne" a pay.
    M41.1 (round 7 Z3): the one gold entry takes the heroes too, so gold for a hero is a
    hand-over to that hero (never a pay to the person standing by)."""
    menu = menu_at(*TOLL, "pc-p2")
    assert off_targets(menu, MenuStep(entry="talk", targets=("foe:thug",))) == ("foe:thug",)
    assert off_targets(menu, MenuStep(entry="talk", targets=("pc-p4", "pc-p6"))) == (
        "pc-p4",
        "pc-p6",
    )
    to_hero = MenuStep(entry="pay", targets=("pc-p4",), qty=5)
    assert off_targets(menu, to_hero) == ()
    assert step_acts(state_at(*TOLL), menu, to_hero, REGS) == [
        HeroHandIntent("pc-p2", "pc-p4", None, gold=5)
    ]
    assert off_targets(menu, MenuStep(entry="pay", targets=("the-poor",))) == ("the-poor",)
    assert off_targets(menu, MenuStep(entry="talk", targets=("reeve-hallick",))) == ()


def test_a_misspelt_id_and_area_aims_keep_the_repair() -> None:
    toll = menu_at(*TOLL, "pc-p2")
    assert off_targets(toll, MenuStep(entry="talk", targets=("reeve-halick",))) == ()
    assert off_targets(toll, MenuStep(entry="look", targets=("reeve-hallick",))) == ()
    fight = menu_at(TYPED, FIGHT_SEQ, "pc-p2")
    foe = next(t.id for t in fight.targets if t.kind == "foe")
    assert off_targets(fight, MenuStep(entry="move", targets=(foe,))) == ()


def test_v1_m38_named_off_targets_get_the_repair_not_other() -> None:
    """M38.5 pass 1: "Brienne gives the spare crowbar to Elowen" (m29-r2-p7:68) became other;
    a hero named for give is a repair that points at hand:crowbar, not a drop to other."""
    menu = menu_at(*CROWBAR, "pc-p2")
    give = MenuStep(entry="give:crowbar", targets=("pc-p4",))
    assert named_off(menu, give) == ("pc-p4",) and not_offered(menu, give) == ()
    assert takers(menu, "give:crowbar", "pc-p4") == ("hand:crowbar",)
    talk = MenuStep(entry="talk", targets=("pc-p4",))  # m29-r2-p7:64 "tells her to keep it"
    assert named_off(menu, talk) == ("pc-p4",) and takers(menu, "talk", "pc-p4") == ()


def test_places_and_things_on_the_wrong_entry_keep_the_plain_repair() -> None:
    """A place or feature named as colour never makes a step other (M38.5 fix)."""
    toll = menu_at(*TOLL, "pc-p2")
    place = next(t.id for t in toll.targets if t.kind == "place")
    step = MenuStep(entry="talk", targets=(place,))
    assert off_targets(toll, step) == (place,) and named_off(toll, step) == ()


def test_a_move_to_the_heros_own_area_is_named_off() -> None:
    """syn:goblin_fight:8 "I move to the Gorse Patch" (the hero's own area) failed three repairs."""
    state, fight = state_at(TYPED, FIGHT_SEQ), menu_at(TYPED, FIGHT_SEQ, "pc-p2")
    enc = state.encounter
    assert enc is not None
    here = enc.combatant("pc-p2").zone_id
    step = MenuStep(entry="move", targets=(here,))
    assert named_off(fight, step) == (here,)
