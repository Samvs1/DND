"""Menu gaps closed in M36.8c (labelling review of the typed-line corpus), on replayed playtest
states: each state is the table exactly before the typed line, and the menu must offer what the
player asked for; the steps must become the engine's own acts.
"""

from aidm.models.action_menu import ActionKind, ActionMenu, MenuEntry, MenuScope, MenuStep
from aidm.models.character import Keepsake
from aidm.models.state import GameState
from aidm.rules.action_menu import build_menu
from aidm.rules.acts import HealIntent, LiftIntent, OfferStrikeIntent, PersonStrikeIntent
from aidm.rules.menu_items import FEED_OPTION
from aidm.rules.menu_scene_view import person_twins, twin_boss
from aidm.rules.menu_steps import step_acts
from tests.ai.chooser_fixtures import REGS, menu_at, state_at


def _entry(menu: ActionMenu, entry_id: str) -> MenuEntry:
    return next(e for e in menu.entries if e.id == entry_id)


def _acts(run: str, seq: int, actor: str, entry: str, *targets: str) -> list[object]:
    menu = menu_at(run, seq, actor)
    step = MenuStep(entry=entry, targets=targets)
    return list(step_acts(state_at(run, seq), menu, step, REGS))


def test_v1_m36_search_while_foes_wait() -> None:
    """r5-quests 658 "Rook searches the fallen planks ... for the Betrothal Ring" (foes wait)."""
    menu = menu_at("m32-r5-quests", 658, "pc-p6")
    assert menu.scope is MenuScope.OFFER
    assert _entry(menu, "search:investigation").kind is ActionKind.SEARCH
    assert _entry(menu, "search:perception").skill == "perception"


def test_v1_m36_attack_a_person_out_of_a_fight() -> None:
    """r1 p6 104 "Brienne draws her longsword and attacks Old Broker Tann without warning"."""
    menu = menu_at("p6", 104, "pc-p2")
    sword = _entry(menu, "attack:longsword")
    assert menu.scope is MenuScope.EXPLORE and not sword.starts_fight
    assert "old-broker-tann" in sword.target_ids and sword.option == "main_hand"
    acts = _acts("p6", 104, "pc-p2", "attack:longsword", "old-broker-tann")
    assert acts == [PersonStrikeIntent("pc-p2", "old-broker-tann", "main_hand")]
    assert not any(e.id.startswith("offhand:") for e in menu.entries)


def test_menu_offer_strike_at_a_bystander_is_a_person_strike() -> None:
    """r5-typed 332: the peddler stands by while a fungus waits: a strike at him is a person
    strike, a strike at the fungus stays the offer strike."""
    menu = menu_at("m32-r5-typed", 332, "pc-p2")
    sword = _entry(menu, "attack:longsword")
    assert sword.starts_fight and sword.target_ids == ("foe:violet-fungus", "bramble-pike")
    person = _acts("m32-r5-typed", 332, "pc-p2", "attack:longsword", "bramble-pike")
    assert person == [PersonStrikeIntent("pc-p2", "bramble-pike", "main_hand")]
    foe = _acts("m32-r5-typed", 332, "pc-p2", "attack:longsword", "foe:violet-fungus")
    assert foe and isinstance(foe[0], OfferStrikeIntent)


def test_v1_m36_downed_ally_gets_their_own_potion() -> None:
    """r1 p2 662 "Elowen kneels by Rook and pours his Potion of Healing between his lips"."""
    menu = menu_at("p2", 662, "pc-p4")
    feed = _entry(menu, "feed:potion-of-healing")
    assert feed.kind is ActionKind.ITEM and feed.option == FEED_OPTION
    assert feed.target_ids == ("pc-p6",)
    acts = _acts("p2", 662, "pc-p4", "feed:potion-of-healing", "pc-p6")
    assert acts == [HealIntent("pc-p4", ("pc-p6",), item="potion-of-healing", owner_id="pc-p6")]


def test_v1_m36_trade_button_while_an_offer_waits() -> None:
    """r5-typed 332 "trade with Bramble Pike": the shop panel shows the button: the menu too."""
    menu = menu_at("m32-r5-typed", 332, "pc-p2")
    assert menu.scope is MenuScope.OFFER
    assert _entry(menu, "shop").target_ids == ("bramble-pike",)


def test_v1_m36_one_person_one_target() -> None:
    """r1 p3 415 / 856: a region master's boss record and its cast twin stand at one place; the
    menu shows one target (the cast record, marked master) and a strike maps to the boss."""
    state = state_at("p3", 415)
    assert person_twins(state) == {"boss-pale-creek-reaches": "ranna-the-brine-widow"}
    assert twin_boss(state, "ranna-the-brine-widow") == "boss-pale-creek-reaches"
    menu = menu_at("p3", 415, "pc-p6")
    ids = {t.id for t in menu.targets}
    assert "boss-pale-creek-reaches" not in ids and "ranna-the-brine-widow" in ids
    label = next(t.label for t in menu.targets if t.id == "ranna-the-brine-widow")
    assert label.endswith(", master")
    assert _entry(menu, "give:receipt-scroll").target_ids == ("ranna-the-brine-widow",)
    strike = _acts("p3", 415, "pc-p6", "attack:dagger", "ranna-the-brine-widow")
    assert strike == [
        OfferStrikeIntent(
            "pc-p6", MenuStep(entry="attack:dagger", targets=("boss-pale-creek-reaches",))
        )
    ]
    varek = menu_at("p3", 856, "pc-p6")
    assert _entry(varek, "talk").target_ids == ("regent-varek",)


def test_menu_lift_from_a_hidden_twin_maps_to_its_holder() -> None:
    state: GameState = state_at("p3", 415).model_copy(deep=True)
    keep = Keepsake(id="kp-test-lantern", name="Test Lantern")
    state.world.npcs["boss-pale-creek-reaches"].keepsakes.append(keep)
    menu = build_menu(state, "pc-p6", REGS)
    lift = _entry(menu, "lift:kp-test-lantern")
    assert lift.target_ids == ("ranna-the-brine-widow",)
    acts = step_acts(state, menu, MenuStep(entry=lift.id, targets=lift.target_ids), REGS)
    assert acts == [LiftIntent("pc-p6", "boss-pale-creek-reaches", keep.id)]
