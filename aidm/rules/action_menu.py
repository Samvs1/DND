"""THE menu builder: the acting hero's legal actions right now (M36, SPEC 6.2). Pure.

`build_menu(state, actor_id, regs, trade=None)` picks the scope from where the hero stands and
joins the parts that belong to it:
- `fight`: an active fight the hero is in, on the hero's own open turn: the fight menu
  (`rules.menu_fight`) plus the free answers (put out the light, check the pack, "what now");
- `off_turn`: an active fight, not the hero's turn: only what is allowed off turn (putting out
  the light, which is free on any turn, and the plain answers); the session answers anything
  else "not your turn" with no model call;
- `offer`: out of a fight while an encounter offer waits at the party's place: the offer's
  answers, strikes at its foes (and at the people here) and a surrender demand
  (`rules.menu_offer`), then everything of `explore`; travel notes that the offer is answered
  first (the place itself stays "you are here");
- `explore`: out of a fight with no offer here: all of the scene (people, looking, searching,
  travel, rests, the shop: `rules.menu_scene`), items (`rules.menu_items`), casts and features
  usable out of a fight (`rules.menu_casts`), the quest card, helping up, a strike at a person
  here (`menu_offer.person_strikes`, M36.8c: the engine's point-of-no-return path) and, while a
  shop is open here and `trade` is given, buying and selling (`rules.menu_trade`).
Out of a fight the menu keeps only the targets its entries name. M41.2: in and out of a fight
the menu carries the hero's ready spells it cannot pay for (`rules.spell_ready`, `unready`).
Entry ids are unique: a clash of two data keys (rare) keeps the first and numbers the next
(`give:torch-2`).

Public API: `build_menu(state, actor_id, regs, trade=None) -> ActionMenu`.
"""

from collections.abc import Sequence

from aidm.data.combat_data import CombatRegistries
from aidm.models.action_menu import ActionMenu, MenuEntry, MenuScope
from aidm.models.encounter import EncounterStatus
from aidm.models.state import GameState
from aidm.rules.menu_casts import explore_casts, explore_features
from aidm.rules.menu_fight import fight_menu
from aidm.rules.menu_items import carried_entries, put_out_entries
from aidm.rules.menu_offer import help_up_entries, offer_entries, person_strikes, quest_entries
from aidm.rules.menu_scene import info_entries, scene_entries
from aidm.rules.menu_scene_view import scene_targets, scene_view
from aidm.rules.menu_trade import TradeData, trade_entries
from aidm.rules.spell_ready import unready_spells


def _unique(entries: Sequence[MenuEntry]) -> tuple[MenuEntry, ...]:
    seen: set[str] = set()
    out: list[MenuEntry] = []
    for entry in entries:
        entry_id, n = entry.id, 1
        while entry_id in seen:
            n += 1
            entry_id = f"{entry.id}-{n}"
        seen.add(entry_id)
        out.append(entry if entry_id == entry.id else entry.model_copy(update={"id": entry_id}))
    return tuple(out)


def _free(state: GameState, actor_id: str) -> list[MenuEntry]:
    return [*put_out_entries(state, actor_id), *info_entries()]


def _fight(state: GameState, actor_id: str, regs: CombatRegistries) -> ActionMenu:
    menu = fight_menu(state, actor_id, regs)
    entries = _unique([*menu.entries, *_free(state, actor_id)])
    return menu.model_copy(update={"entries": entries})


def _out_of_fight(
    state: GameState, actor_id: str, regs: CombatRegistries, trade: TradeData | None
) -> ActionMenu:
    view = scene_view(state, actor_id, regs)
    offer_scope = view.offer is not None
    entries = [
        *(offer_entries(view) if offer_scope else person_strikes(view)),
        *quest_entries(view),
        *help_up_entries(view),
        *scene_entries(view),
        *carried_entries(view),
        *explore_casts(view),
        *explore_features(view),
    ]
    if trade is not None:
        entries += trade_entries(view, trade)
    named = {t for e in entries for t in (*e.target_ids, *e.zone_ids)}
    return ActionMenu(
        scope=MenuScope.OFFER if offer_scope else MenuScope.EXPLORE,
        actor_id=actor_id,
        entries=_unique(entries),
        targets=tuple(t for t in scene_targets(view) if t.id in named),
        unready=unready_spells(
            view.state.creatures[actor_id], view.sheet.spellcasting, regs.spells
        ),
    )


def build_menu(
    state: GameState, actor_id: str, regs: CombatRegistries, trade: TradeData | None = None
) -> ActionMenu:
    enc = state.encounter
    if enc is not None and enc.status is EncounterStatus.ACTIVE and actor_id in enc.combatants:
        if enc.turn_open and enc.active_id() == actor_id:
            return _fight(state, actor_id, regs)
        entries = _unique(_free(state, actor_id))
        return ActionMenu(scope=MenuScope.OFF_TURN, actor_id=actor_id, entries=entries)
    creature = state.creatures.get(actor_id)
    if creature is None or creature.pc is None:
        return ActionMenu(scope=MenuScope.EXPLORE, actor_id=actor_id)
    return _out_of_fight(state, actor_id, regs, trade)
