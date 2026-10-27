"""The menu's steps as the acts the session runners take (M36.4, SPEC 6.2) on replayed round-6
states (docs/playtests/M34_round6.md Y9, Y10, Y12, Y13, Y15): each state is the table exactly
before the typed line of the finding, the step is what the line meant.
"""

from functools import cache

from aidm.data.combat_data import combat_registries
from aidm.data.item_catalogue import item_catalogue
from aidm.data.shop_defs import shop_table
from aidm.models.abilities import Skill
from aidm.models.action_menu import ActionMenu, MenuChoice, MenuStep
from aidm.models.campaign_state import OfferChoice
from aidm.models.commands import (
    AttackCommand,
    CastCommand,
    DodgeCommand,
    EndTurnCommand,
    MoveCommand,
)
from aidm.models.protocol_client import AnswerOffer, ShopBuy, ShopSell
from aidm.models.state import GameState
from aidm.rules.action_menu import build_menu
from aidm.rules.acts import (
    AskIntent,
    GiveIntent,
    HelpUpIntent,
    ItemAction,
    ItemIntent,
    ItemIntents,
    LookAroundIntent,
    OfferStrikeIntent,
    OtherIntent,
    ParleyIntent,
    PayIntent,
    QuestAnswerIntent,
    RefusedIntent,
    RestIntent,
    RestKind,
    SearchIntent,
    TakeIntent,
    TravelIntent,
)
from aidm.rules.acts_fight import DrawAttack
from aidm.rules.menu_steps import UNKNOWN_STEP, Act, resume_strike, to_acts
from aidm.rules.menu_trade import TradeData
from tests.session.playtest_saves import replay_until

REGS = combat_registries()
TRADE = TradeData(item_catalogue(), shop_table())
TYPED, QUESTS, FULL = "m35-r6-typed", "m35-r6-quests", "m35-r6-full"
VAULT = "collapsed_vault"


@cache
def _state(run: str, seq: int) -> GameState:
    return replay_until(run, seq)


@cache
def _menu(run: str, seq: int, actor_id: str) -> ActionMenu:
    return build_menu(_state(run, seq), actor_id, REGS, TRADE)


def _acts(
    run: str, seq: int, actor_id: str, *steps: tuple[str, tuple[str, ...], int], text: str = ""
) -> list[Act]:
    choice = MenuChoice(steps=tuple(MenuStep(entry=e, targets=t, qty=q) for e, t, q in steps))
    return to_acts(_state(run, seq), _menu(run, seq, actor_id), choice, REGS, text)


def test_v1_y10_longsword_walks_into_the_crypt_then_strikes() -> None:
    """typed 435 "I drive my longsword into the nearest kobold": moves, then the longsword."""
    acts = _acts(TYPED, 435, "pc-p2", ("attack:longsword", ("kobold-1",), 1))
    assert acts == [
        [MoveCommand(actor_id="pc-p2", zone_id=VAULT)],
        AttackCommand(actor_id="pc-p2", target_id="kobold-1", option="main_hand"),
    ]


def test_menu_steps_move_then_attack_plans_from_where_the_move_ends() -> None:
    acts = _acts(TYPED, 435, "pc-p2", ("move", (VAULT,), 1), ("attack:longsword", ("kobold-1",), 1))
    assert acts == [
        [MoveCommand(actor_id="pc-p2", zone_id=VAULT)],
        AttackCommand(actor_id="pc-p2", target_id="kobold-1", option="main_hand"),
    ]


def test_menu_steps_out_of_reach_is_a_plain_answer_never_a_ranged_swap() -> None:
    state = _state(TYPED, 435)
    enc = state.encounter
    assert enc is not None
    me = enc.combatants["pc-p2"]
    stuck = me.model_copy(update={"economy": me.economy.model_copy(update={"movement_left": 0})})
    combatants = {**enc.combatants, "pc-p2": stuck}
    running = state.model_copy(
        update={"encounter": enc.model_copy(update={"combatants": combatants})}
    )
    step = MenuStep(entry="attack:longsword", targets=("kobold-1",))
    acts = to_acts(running, _menu(TYPED, 435, "pc-p2"), MenuChoice(steps=(step,)), REGS)
    assert acts == [RefusedIntent("pc-p2", "Kobold A is out of reach this turn.")]


def test_menu_steps_stowed_rapier_is_drawn_first() -> None:
    acts = _acts(TYPED, 161, "pc-p4", ("attack:rapier", ("swarm-of-rats-1",), 1))
    assert isinstance(acts[-1], DrawAttack) and acts[-1].item == "rapier"
    assert acts[-1].attack.target_id == "swarm-of-rats-1"


def test_menu_steps_end_turn_ends_the_steps() -> None:
    acts = _acts(
        TYPED, 435, "pc-p2", ("dodge", (), 1), ("end-turn", (), 1), ("attack:longsword", (), 1)
    )
    assert acts == [DodgeCommand(actor_id="pc-p2"), EndTurnCommand(actor_id="pc-p2")]


def test_v1_y15_travel_to_the_place_itself_is_already_at() -> None:
    acts = _acts(TYPED, 797, "pc-p2", ("travel", ("lamplighters-rest",), 1))
    assert acts == [RefusedIntent("pc-p2", "You are already at Lamplighters' Rest.")]


def test_menu_steps_travel_next_door_and_hop_by_hop() -> None:
    near = _acts(TYPED, 770, "pc-p2", ("travel", ("lamplighters-rest",), 1))
    assert near == [TravelIntent("lamplighters-rest")]
    far = _acts(QUESTS, 563, "pc-p2", ("travel", ("steeple-of-the-still-bell",), 1))
    assert len(far) == 1 and isinstance(far[0], TravelIntent)
    assert far[0].goal == "steeple-of-the-still-bell" and far[0].node_id != far[0].goal


def test_menu_steps_travel_while_an_offer_waits_answers_it_first() -> None:
    acts = _acts(TYPED, 750, "pc-p2", ("travel", ("gullmere-quay-docks",), 1))
    assert len(acts) == 1 and isinstance(acts[0], RefusedIntent)
    assert acts[0].text.startswith("The waiting encounter is answered first")


def test_v1_y13_give_three_blocks_of_incense() -> None:
    acts = _acts(QUESTS, 563, "pc-p2", ("give:block-of-incense", ("widow-cabrelle",), 3))
    thing = "block-of-incense"
    assert acts == [GiveIntent("pc-p2", "widow-cabrelle", thing, (thing, thing), 3)]


def test_menu_steps_give_the_incense_then_talk_to_the_widow_in_order() -> None:
    words = "I give her the incense and ask about the bell"
    acts = _acts(
        QUESTS,
        563,
        "pc-p2",
        ("give:block-of-incense", ("widow-cabrelle",), 1),
        ("talk", ("widow-cabrelle",), 1),
        text=words,
    )
    assert acts == [
        GiveIntent("pc-p2", "widow-cabrelle", "block-of-incense", (), 1),
        AskIntent("pc-p2", "widow-cabrelle", said=words),
    ]


def test_menu_steps_counted_pay_drop_and_trade() -> None:
    assert _acts(QUESTS, 563, "pc-p2", ("pay", ("widow-cabrelle",), 5)) == [
        PayIntent("pc-p2", "widow-cabrelle", 5)
    ]
    drop = ItemIntent("pc-p2", ItemAction.DROP, "block-of-incense")
    assert _acts(QUESTS, 563, "pc-p2", ("drop:block-of-incense", (), 2)) == [
        ItemIntents((drop, drop))
    ]
    keeper = "halan-s-rest-peddler"
    buy = _acts(QUESTS, 563, "pc-p2", ("buy:herbal-poultice", (), 2))
    assert buy == [ShopBuy(npc_id=keeper, item_id="herbal-poultice", qty=2)]
    sell = _acts(QUESTS, 563, "pc-p2", ("sell:crowbar", (), 1))
    assert sell == [ShopSell(npc_id=keeper, item_id="crowbar", qty=1)]


def test_v1_y12_take_one_of_three_lumps_of_resin() -> None:
    menu = _menu(QUESTS, 297, "pc-p8")
    resin = next(e for e in menu.entries if e.id == "take:softening-resin")
    assert resin.qty_max == 3 and resin.label == "Pick up Softening Resin (3 here)"
    one = _acts(QUESTS, 297, "pc-p8", ("take:softening-resin", (), 1))
    first = "qi-main-the-muted-vale-smother-the-wax-0-0"
    assert one == [TakeIntent("pc-p8", first)]
    every = _acts(QUESTS, 297, "pc-p8", ("take:softening-resin", (), 3))
    assert [a.item_id for a in every if isinstance(a, TakeIntent)] == [
        f"qi-main-the-muted-vale-smother-the-wax-0-{n}" for n in range(3)
    ]


def test_v1_y9_sleep_at_the_waiting_kobolds_starts_the_fight() -> None:
    acts = _acts(TYPED, 378, "pc-p6", ("cast:sleep", ("foe:kobold",), 1), ("look", (), 1))
    step = MenuStep(entry="cast:sleep", targets=("foe:kobold",))
    assert acts == [OfferStrikeIntent("pc-p6", step)]


def test_menu_steps_offer_strike_is_played_on_the_spawned_kobolds() -> None:
    """typed 424 is Rook's first turn of that fight: `foe:kobold` becomes the kobolds."""
    state = _state(TYPED, 424)
    sleep = resume_strike(
        state, "pc-p6", MenuStep(entry="cast:sleep", targets=("foe:kobold",)), REGS
    )
    assert sleep == [
        CastCommand(actor_id="pc-p6", spell_id="sleep", slot_level=1, target_zone=VAULT)
    ]
    bolt = MenuStep(entry="cast:fire-bolt", targets=("foe:kobold",))
    assert resume_strike(state, "pc-p6", bolt, REGS) == [
        CastCommand(actor_id="pc-p6", spell_id="fire-bolt", target_ids=("kobold-1",))
    ]
    gone = MenuStep(entry="cast:sleep", targets=("foe:goblin",))
    assert resume_strike(state, "pc-p6", gone, REGS) == [
        RefusedIntent("pc-p6", "That strike cannot be made now.")
    ]


def test_menu_steps_offer_answers() -> None:
    fight = _acts(TYPED, 750, "pc-p2", ("offer:fight", (), 1), ("look", (), 1))
    assert fight == [AnswerOffer(choice=OfferChoice.FIGHT)]
    talk = _acts(TYPED, 750, "pc-p2", ("offer:parley:persuasion", (), 1))
    assert talk == [ParleyIntent("pc-p2", Skill.PERSUASION)]
    demand = _acts(TYPED, 750, "pc-p2", ("surrender", (), 1))
    assert demand == [ParleyIntent("pc-p2", Skill.INTIMIDATION)]


def test_menu_steps_quest_card_help_up_look_search_rest() -> None:
    assert _acts(TYPED, 31, "pc-p2", ("quest:accept", (), 1)) == [
        QuestAnswerIntent("pc-p2", "missing-ledger", True)
    ]
    assert _acts(FULL, 469, "pc-p2", ("help_up", (), 1)) == [HelpUpIntent("pc-p2", "pc-p8")]
    plain = _acts(
        QUESTS,
        563,
        "pc-p2",
        ("look", (), 1),
        ("search:investigation", (), 1),
        ("rest:short", (), 1),
        ("look", (), 1),
    )
    assert plain == [
        LookAroundIntent("pc-p2"),
        SearchIntent("pc-p2", Skill.INVESTIGATION),
        RestIntent(RestKind.SHORT),
    ]


def test_menu_steps_other_goes_to_the_storyteller_an_unknown_entry_is_refused() -> None:
    menu = _menu(QUESTS, 563, "pc-p2")
    words = "I juggle three apples for the widow"
    state = _state(QUESTS, 563)
    assert to_acts(state, menu, MenuChoice(other=True), REGS, words) == [
        OtherIntent("pc-p2", words)
    ]
    odd = MenuChoice(steps=(MenuStep(entry="attack:nothing"),))  # M43.2: never the storyteller's
    assert to_acts(state, menu, odd, REGS, words) == [RefusedIntent("pc-p2", UNKNOWN_STEP)]
