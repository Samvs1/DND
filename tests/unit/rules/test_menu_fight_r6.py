"""The fight menu on replayed round-6 states (M36.2, docs/playtests/M34_round6.md Y10, Y11).

Each state is the table exactly before the typed line of the finding (tests/fixtures/saves/
m35-r6-typed): the menu must offer the entry the player meant, with the target they named.
"""

from functools import cache

from aidm.data.combat_data import combat_registries
from aidm.models.action_menu import ActionKind, ActionMenu, MenuEntry, MenuScope
from aidm.models.commands import MoveCommand
from aidm.models.world_events import ActionDeclared
from aidm.rules.action_menu import build_menu
from aidm.rules.approach import approach_moves
from aidm.rules.attack_profiles import find_option
from tests.session.playtest_saves import logged, replay_until

RUN = "m35-r6-typed"
REGS = combat_registries()


@cache
def _menu(seq: int, actor_id: str) -> ActionMenu:
    return build_menu(replay_until(RUN, seq), actor_id, REGS)


def _entry(menu: ActionMenu, entry_id: str) -> MenuEntry:
    return next(e for e in menu.entries if e.id == entry_id)


def test_v1_r6_fixture_lines_are_the_findings() -> None:
    lines = {
        161: "I put an arrow in its chest",
        179: "Rook flings a bolt of fire at the swarm",
        435: "I drive my longsword into the nearest kobold",
        1165: "I raise my holy symbol and command the undead cantor to turn away",
    }
    for seq, text in lines.items():
        event = logged(RUN, seq).event
        assert isinstance(event, ActionDeclared) and event.text == text


def test_v1_y11_arrow_in_its_chest_offers_the_bow() -> None:
    menu = _menu(161, "pc-p4")
    assert menu.scope is MenuScope.FIGHT
    bow = _entry(menu, "attack:shortbow")
    assert bow.kind is ActionKind.ATTACK and bow.option == "ranged"
    assert bow.target_ids == ("swarm-of-rats-1",)
    assert bow.label.startswith("Shortbow (ranged, ")
    assert "% vs Swarm of Rats" in bow.label


def test_v1_y11_bolt_of_fire_offers_fire_bolt_at_the_swarm() -> None:
    menu = _menu(179, "pc-p6")
    bolt = _entry(menu, "cast:fire-bolt")
    assert bolt.kind is ActionKind.CAST and bolt.spell_id == "fire-bolt"
    assert "swarm-of-rats-1" in bolt.target_ids
    assert bolt.label == "Fire Bolt (cantrip, fire, 120 ft)"
    assert bolt.slot_level is None


def test_v1_y11_turn_undead_is_offered_at_the_cantor() -> None:
    menu = _menu(1165, "pc-p8")
    turn = _entry(menu, "feature:turn-undead")
    assert turn.feature_id == "channel-divinity-turn-undead"
    assert turn.max_targets == 0 and not turn.spent
    assert turn.label == (
        "Turn Undead (Channel Divinity, action, 1 left, undead nearby: Cantor Ashmere Voll)"
    )


def test_v1_y10_longsword_keeps_the_kobold_out_of_reach() -> None:
    menu = _menu(435, "pc-p2")
    sword = _entry(menu, "attack:longsword")
    assert sword.option == "main_hand"
    assert {"kobold-1", "kobold-2", "swarm-of-bats-1"} <= set(sword.target_ids)
    assert sword.approach == {"kobold-1": 30, "kobold-2": 30}
    assert sword.target_notes["kobold-1"].startswith("moves 30 ft first, ")
    assert "kobold-1" not in sword.far


def test_v1_y10_approach_moves_walk_into_the_crypt() -> None:
    state = replay_until(RUN, 435)
    hero = state.creatures["pc-p2"]
    sword = find_option(hero, REGS.chars, "main_hand")
    assert sword is not None
    moves = approach_moves(state, "pc-p2", "kobold-1", sword, REGS)
    assert moves == [MoveCommand(actor_id="pc-p2", zone_id="collapsed_vault")]


def test_v1_y10_melee_is_never_swapped_to_the_crossbow() -> None:
    sword = _entry(_menu(435, "pc-p2"), "attack:longsword")
    assert sword.option == "main_hand" and sword.item == "longsword"
    assert "ranged" not in sword.label


def test_menu_target_labels_name_distance_and_state() -> None:
    labels = {t.id: t.label for t in _menu(435, "pc-p2").targets}
    assert labels["kobold-1"] == "Kobold A, 30 ft, unhurt"
    assert labels["swarm-of-bats-1"] == "Swarm of Bats, here, hurt"
    assert labels["collapsed_vault"] == "Caved-In Crypt (Kobold A; Kobold B), 30 ft"  # M36.9


def test_menu_stowed_rapier_draws_first() -> None:
    rapier = _entry(_menu(161, "pc-p4"), "attack:rapier")
    assert rapier.draw == "rapier" and rapier.note == "draws first"
    assert "draws first" in rapier.label


def test_menu_off_turn_has_no_fight_entries() -> None:
    """M36.3: off turn only the free answers (pack, "what now", putting out a light) remain."""
    menu = build_menu(replay_until(RUN, 435), "pc-p4", REGS)
    assert menu.scope is MenuScope.OFF_TURN
    free = {ActionKind.INVENTORY, ActionKind.WHAT_NOW, ActionKind.PUT_OUT}
    assert {e.kind for e in menu.entries} <= free and menu.targets == ()
