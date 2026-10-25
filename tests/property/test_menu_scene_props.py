"""Every button or job the UI can send out of a fight has a menu entry (M36.3, SPEC 6.2).

Walks committed playtest fixtures through the one reducer and, at each typed line out of a fight,
checks the menu against what the client could send in that state: the offer card's answers, the
quest card, the shop (visit, buy, sell what a trader pays for), the item cards (give, hand, equip,
unequip, drop, use here, potions, copy a scroll, put out the light), helping a downed hero up,
picking up what lies here, "what now" and the travel map's exits.
"""

from collections.abc import Iterator

from aidm.data.combat_data import combat_registries
from aidm.data.item_catalogue import item_catalogue
from aidm.data.shop_defs import shop_table
from aidm.models.action_menu import ActionKind, ActionMenu, MenuEntry
from aidm.models.campaign_state import OfferChoice
from aidm.models.encounter import EncounterStatus
from aidm.models.state import GameState
from aidm.models.world_events import ActionDeclared
from aidm.rules.action_menu import build_menu
from aidm.rules.light import hero_light
from aidm.rules.menu_items import same_lying
from aidm.rules.menu_scene_view import scene_view
from aidm.rules.menu_trade import TradeData
from aidm.rules.menu_view import slug
from aidm.rules.offer_answer import PARLEY_SKILLS
from aidm.rules.scene import current_scene
from aidm.rules.shop import is_shop, npc_shop_stock, sell_price
from aidm.session.reducer import apply
from tests.session.playtest_saves import events_of, replay_until

REGS = combat_registries()
TRADE = TradeData(item_catalogue(), shop_table())
RUNS = (
    "m35-r6-full",
    "m35-r6-quests",
    "m35-r6-typed",
    "m32-r5-quests",
    "m31-r4-quests",
    "r3-items",
)
EVERY = 1


def _lines(run: str) -> Iterator[tuple[GameState, str]]:
    """The state before every third typed line out of a fight (and every one with a hero down)."""
    log = events_of(run)
    state = replay_until(run, log[0].seq)
    seen = 0
    for entry in log:
        event = entry.event
        enc = state.encounter
        calm = enc is None or enc.status is not EncounterStatus.ACTIVE
        if isinstance(event, ActionDeclared) and calm and event.creature_id in state.creatures:
            seen += 1
            downed = any(c.pc and not c.dead and c.hp <= 0 for c in state.creatures.values())
            if seen % EVERY == 0 or downed:
                yield state, event.creature_id
        apply(state, event)


def _entry(menu: ActionMenu, entry_id: str) -> MenuEntry:
    found = next((e for e in menu.entries if e.id == entry_id), None)
    assert found is not None, f"{entry_id} missing"
    return found


def _offer_buttons(state: GameState, menu: ActionMenu) -> None:
    offer = state.campaign.offer if state.campaign is not None else None
    if offer is None or offer.node_id != state.world.current_node:
        return
    answers = {(e.option, e.skill) for e in menu.entries if e.kind is ActionKind.OFFER}
    for choice in offer.options:
        if choice is OfferChoice.PARLEY:
            assert all((choice.value, s.value) in answers for s in PARLEY_SKILLS)
        else:
            assert (choice.value, None) in answers


def _cards(state: GameState, actor_id: str, menu: ActionMenu) -> None:
    view = scene_view(state, actor_id, REGS)
    ask = state.world.quest_ask
    if ask is not None and ask.npc_id in view.people:
        assert _entry(menu, "quest:accept").quest_id == ask.quest_id
        assert _entry(menu, "quest:decline").quest_id == ask.quest_id
    downed = [h for h in view.heroes if state.creatures[h].hp <= 0]
    if downed:
        assert set(downed) <= set(_entry(menu, "help_up").target_ids)
    if hero_light(state, actor_id) is not None:
        _entry(menu, "put_out")
    _entry(menu, "what_now")
    takes = [e.item for e in menu.entries if e.kind is ActionKind.TAKE and e.id.startswith("take:")]
    lying = {i.id for first in takes for i in same_lying(state, first or "")}  # M36.4: grouped
    assert set(current_scene(state).item_ids) <= lying


def _travel_map(state: GameState, menu: ActionMenu) -> None:
    exits = current_scene(state).exits
    if exits:
        assert set(exits) <= set(_entry(menu, "travel").target_ids)


def _shop(state: GameState, actor_id: str, menu: ActionMenu) -> None:
    view = scene_view(state, actor_id, REGS)
    world = state.world
    keepers = {
        n for n in view.people if is_shop(state, world.npcs[n]) and not world.npcs[n].hostile
    }
    if keepers:  # M36.8c: the shop panel shows the visit while an offer waits too
        assert keepers <= set(_entry(menu, "shop").target_ids)
    keeper = world.npcs.get(world.shop_npc_id or "")
    if keeper is None or keeper.id not in view.people or keeper.hostile:
        return
    for stock in npc_shop_stock(state, keeper.id, TRADE.catalogue, TRADE.shops):
        _entry(menu, f"buy:{stock.item}")
    for row in view.sheet.inventory:
        item = TRADE.catalogue.find(row.item)
        if item is not None and sell_price(item.value_gp, 1, TRADE.shops) >= 1:
            _entry(menu, f"sell:{row.item}")  # the panel's Sell buttons (worth at least 1 gp)


def _item_cards(state: GameState, actor_id: str, menu: ActionMenu) -> None:
    view = scene_view(state, actor_id, REGS)
    for row in view.sheet.inventory:
        _entry(menu, f"drop:{row.item}")
        if row.equipped_slot:
            _entry(menu, f"unequip:{row.item}")
        if view.people:
            give = _entry(menu, f"give:{row.item}")
            assert give.qty_max == row.qty and set(view.people) <= set(give.target_ids)
        if view.heroes:
            assert set(view.heroes) <= set(_entry(menu, f"hand:{row.item}").target_ids)
        if REGS.consumables.find(row.item) is not None:
            party = {actor_id, *view.heroes}
            assert party <= set(_entry(menu, f"item:{row.item}").target_ids)
        for use in row.uses:
            _entry(menu, f"use:{use.use_id}")
    for line in view.sheet.scroll_copies:
        _entry(menu, f"copy:{line.item}")
    gives = {e.item for e in menu.entries if e.kind is ActionKind.GIVE}
    for keepsake in view.sheet.keepsakes if view.people else []:
        same = [k.id for k in view.sheet.keepsakes if slug(k.name) == slug(keepsake.name)]
        assert gives & set(same), keepsake.name


def test_every_ui_job_out_of_a_fight_has_a_menu_entry() -> None:
    checked = 0
    for run in RUNS:
        for state, actor_id in _lines(run):
            creature = state.creatures[actor_id]
            if creature.pc is None or creature.dead:
                continue
            menu = build_menu(state, actor_id, REGS, TRADE)
            _offer_buttons(state, menu)
            _cards(state, actor_id, menu)
            _travel_map(state, menu)
            _shop(state, actor_id, menu)
            _item_cards(state, actor_id, menu)
            checked += 1
    assert checked >= 60
