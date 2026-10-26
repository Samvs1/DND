"""M38.4 cause A: names the hero means but the menu cannot act on are not-offered targets, and a
step at a target its entry cannot act on is the storyteller's, never a swapped target (the
M38.3 live eval, docs/playtests/M38_eval.md). Real replayed states, no model."""

from aidm.models.action_menu import ActionMenu, MenuStep
from aidm.rules.acts import OtherIntent
from aidm.rules.menu_steps import step_acts
from aidm.rules.menu_unoffered import (
    MAX_UNOFFERED,
    off_targets,
    unoffered_targets,
    with_unoffered,
)
from tests.ai.chooser_fixtures import FIGHT_SEQ, REGS, TYPED, menu_at, state_at

LOCKET = ("m31-r4-full", 638)  # Elowen; Rook carries the Sister's Locket
CHIME = ("r2-p7", 868)  # Brienne carries the chime; Brother Vale is elsewhere
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


def test_v1_m38_a_person_not_here_is_not_offered() -> None:
    """Row m29-r2-p7:868: the chime carried "back toward Brother Vale" was handed to Elowen."""
    line = "Brienne picks up the unfinished chime and carries it back toward Brother Vale."
    menu = _unoffered(CHIME, "pc-p2", line)
    assert [(t.id, t.label, t.kind) for t in menu.unoffered] == [
        ("brother-vale", "Brother Vale (not here)", "person")
    ]
    step = MenuStep(entry="hand:unfinished-chime", targets=("brother-vale",))
    assert off_targets(menu, step) == ("brother-vale",)


def test_names_the_menu_acts_on_are_never_not_offered() -> None:
    state, menu = state_at(*DOWNED), menu_at(*DOWNED, "pc-p2")
    for line in ("I help Elowen up", "I hand Rook my torch", "We travel to Hollowgate Cross"):
        assert unoffered_targets(state, menu, line) == ()
    assert with_unoffered(state, menu, "I help Elowen up") is menu


def test_a_name_inside_a_shown_name_is_that_one() -> None:
    """ "descending to the Saltwright's forge" names the place, not the master who is away."""
    at = ("r2-p4", 1690)
    line = "We take a long rest here at the gate before descending to the Saltwright's forge"
    assert unoffered_targets(state_at(*at), menu_at(*at, "pc-p2"), line) == ()
    asked = "I ask the peddler what he knows about the Saltwright"
    (master,) = unoffered_targets(state_at(*at), menu_at(*at, "pc-p2"), asked)
    assert master.label == "The Saltwright (not here)"


def test_not_offered_targets_are_capped_in_line_order() -> None:
    state, menu = state_at(*CHIME), menu_at(*CHIME, "pc-p2")
    people = [n.name for n in state.world.npcs.values() if n.node_id != state.world.current_node]
    found = unoffered_targets(state, menu, " and ".join(people))
    assert len(found) == min(MAX_UNOFFERED, len(people))
    assert [t.label.split(" (")[0] for t in found] == people[: len(found)]


def test_v1_m38_help_up_at_a_standing_hero_is_off() -> None:
    """Router line "I help Rook up" (Rook stands): help_up lists only the downed Elowen."""
    menu = menu_at(*DOWNED, "pc-p2")
    assert off_targets(menu, MenuStep(entry="help_up", targets=("pc-p6",))) == ("pc-p6",)
    assert off_targets(menu, MenuStep(entry="help_up", targets=("pc-p4",))) == ()
    acts = step_acts(state_at(*DOWNED), menu, MenuStep(entry="help_up", targets=("pc-p6",)), REGS)
    assert acts == [OtherIntent("pc-p2", "")]


def test_v1_m38_talk_to_a_waiting_monster_and_pay_to_a_hero_are_off() -> None:
    """ "Rook bows low to the thug" became talk to Reeve Hallick; "10 gold for Brienne" a pay."""
    menu = menu_at(*TOLL, "pc-p2")
    assert off_targets(menu, MenuStep(entry="talk", targets=("foe:thug",))) == ("foe:thug",)
    assert off_targets(menu, MenuStep(entry="talk", targets=("pc-p4", "pc-p6"))) == (
        "pc-p4",
        "pc-p6",
    )
    assert off_targets(menu, MenuStep(entry="pay", targets=("pc-p4",), qty=5)) == ("pc-p4",)
    assert off_targets(menu, MenuStep(entry="pay", targets=("the-poor",))) == ("the-poor",)
    assert off_targets(menu, MenuStep(entry="talk", targets=("reeve-hallick",))) == ()


def test_a_misspelt_id_and_area_aims_keep_the_repair() -> None:
    toll = menu_at(*TOLL, "pc-p2")
    assert off_targets(toll, MenuStep(entry="talk", targets=("reeve-halick",))) == ()
    assert off_targets(toll, MenuStep(entry="look", targets=("reeve-hallick",))) == ()
    fight = menu_at(TYPED, FIGHT_SEQ, "pc-p2")
    foe = next(t.id for t in fight.targets if t.kind == "foe")
    assert off_targets(fight, MenuStep(entry="move", targets=(foe,))) == ()
