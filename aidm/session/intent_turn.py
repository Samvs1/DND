"""One act of a typed line out of a fight, played from its intent (split out of `session.explore` in
M32.1a; SPEC 6.1, 6.2).

`run_intent(core, player, actor, entry, intent)`: the menu's acts (`session.menu_turn`) run here:
the deterministic intents, or the storyteller (`held.adjudicated`) for a line off the menu.
M32.1a: an attack at the waiting offer starts the fight and waits for the hero's turn
(`offer_strike`); a plain no-roll answer (`RefusedIntent`: the dead do not surrender) is a notice
and the offer still waits; an impossible feat logs `ActionImpossible` with no dice and is told.
M35.2 (round 6 Y9): a harmful spell read as a cast at the scene while a foe's offer waits here is
the same fight-starting act (`offer_strike.cast_opens_fight`): never a slot spent at the scene.
M36.4: `run_intent` also runs the menu's own acts (`rules.menu_steps`; not yet produced from a
typed line until M36.6): taking from a fallen hero's pack, a feature out of a fight, the menu's
look (the look-around text written here) and a line off the menu (the storyteller).
M41.1 (round 7 Z4): a typed hand-over or payment the rules refuse (more gold than the hero
has) moves nothing and is told as an impossible attempt with the rules' reason (`_refused`).

Public API: `run_intent` (the pack listing is `dm.scene_text.inventory_text`).
"""

from aidm.dm.scene_text import inventory_text, look_around_text
from aidm.models.impossible import MAX_IMPOSSIBLE_REASON, MAX_IMPOSSIBLE_TEXT, ActionImpossible
from aidm.models.protocol_client import AnswerQuestOffer
from aidm.models.protocol_server import NoticeKind
from aidm.models.protocol_views import QueueEntry
from aidm.models.state import Creature
from aidm.rules.acts import (
    AskIntent,
    BarredIntent,
    CastIntent,
    FeatureUseIntent,
    GiveIntent,
    HealIntent,
    HelpUpIntent,
    HeroHandIntent,
    ImpossibleIntent,
    Intent,
    InventoryIntent,
    ItemIntent,
    ItemIntents,
    LiftIntent,
    LookAroundIntent,
    LookIntent,
    LootIntent,
    OfferStrikeIntent,
    OtherIntent,
    ParleyIntent,
    PayIntent,
    PersonStrikeIntent,
    QuestAnswerIntent,
    RefusedIntent,
    RestIntent,
    SearchIntent,
    ShopIntent,
    TakeIntent,
    TravelIntent,
    UseIntent,
)
from aidm.rules.lore import place_lore_events
from aidm.session import (
    gear_actions,
    hand_over,
    heal_actions,
    party_actions,
    quest_people,
    scene_votes,
)
from aidm.session.held import adjudicated, hold_parley, strike_person
from aidm.session.lore_turn import lore_turn
from aidm.session.offer_strike import cast_opens_fight, offer_strike_turn
from aidm.session.search_turn import search_turn
from aidm.session.table_core import Player, TableCore
from aidm.session.telling import conclude, remember, tell_text


async def run_intent(
    core: TableCore, player: Player, actor: Creature, entry: QueueEntry, intent: Intent
) -> None:
    if isinstance(intent, LookIntent | BarredIntent):
        await _look(core, entry, intent)
    elif isinstance(intent, InventoryIntent):
        core.notice(player.id, NoticeKind.INFO, inventory_text(actor))
    elif isinstance(intent, ItemIntent | ItemIntents):
        await party_actions.item_intent(core, player, intent)
    elif isinstance(intent, TakeIntent):
        await hand_over.take_intent(core, player, intent)
    elif isinstance(intent, HelpUpIntent):
        await party_actions.help_up_intent(core, player, intent)
    elif isinstance(intent, GiveIntent):
        await hand_over.give_intent(core, player, intent)
    elif isinstance(intent, HeroHandIntent):  # M41.1: a refusal is told as impossible
        await _refused(core, entry, intent.actor_id, await hand_over.hand_intent(core, intent))
    elif isinstance(intent, PayIntent):
        await _pay(core, entry, intent)
    elif isinstance(intent, LiftIntent):
        await hand_over.lift_intent(core, player, intent)
    elif isinstance(intent, LootIntent):  # M36.4 Y14: from a fallen hero's pack
        await hand_over.loot_intent(core, player, intent)
    elif isinstance(intent, FeatureUseIntent):  # M36.4: Second Wind out of a fight
        await heal_actions.feature_intent(core, player, intent)
    elif isinstance(intent, LookAroundIntent):  # M36.4: the menu's look
        await _look(core, entry, LookIntent(look_around_text(core.state)))
    elif isinstance(intent, OtherIntent):  # M36.4: off the menu, the storyteller's call
        await adjudicated(core, entry.model_copy(update={"text": intent.text}))
    else:
        await _run_other(core, player, entry, intent)


async def _run_other(core: TableCore, player: Player, entry: QueueEntry, intent: Intent) -> None:
    if isinstance(intent, QuestAnswerIntent):  # M31.1a V8: the card's Accept / Not now
        answer = AnswerQuestOffer(quest_id=intent.quest_id, accept=intent.accept)
        await quest_people.answer_quest(core, player, answer)
    elif isinstance(intent, ParleyIntent):  # M31.1a V4: asked first, then one roll answers
        hold_parley(core, player, intent.actor_id, intent.skill)
    elif isinstance(intent, UseIntent):
        await _gear_use(core, player, entry, intent)
    elif isinstance(intent, SearchIntent):  # M31.1a V9: one discovery check at the hidden DC
        await search_turn(core, entry, intent)
    elif isinstance(intent, AskIntent):  # M31.1b V13: what the person teaches, then the telling
        await lore_turn(core, entry, intent)
    elif isinstance(intent, CastIntent) and cast_opens_fight(core, intent):  # M35.2 Y9
        await offer_strike_turn(core, player, entry, OfferStrikeIntent(intent.actor_id))
    elif isinstance(intent, HealIntent | CastIntent):  # M30.0b T7: a typed spell out of a fight
        await heal_actions.heal_intent(core, player, intent)
    elif isinstance(intent, OfferStrikeIntent):  # M32.1a X3: the fight, then this line
        await offer_strike_turn(core, player, entry, intent)
    elif isinstance(intent, PersonStrikeIntent):  # M36.8c: the point-of-no-return path
        await strike_person(core, entry, intent)
    elif isinstance(intent, RefusedIntent):  # M32.1a X5: no roll, the offer still waits
        core.notice(player.id, NoticeKind.REFUSED, intent.text)
    elif isinstance(intent, ImpossibleIntent):  # M32.1a X8: no dice, told failing
        await _impossible(core, entry, intent)
    elif isinstance(intent, TravelIntent | RestIntent | ShopIntent):
        scene_votes.propose_intent(core, player, entry, intent)


async def _look(core: TableCore, entry: QueueEntry, intent: LookIntent | BarredIntent) -> None:
    lore = (
        place_lore_events(core.state, entry.creature_id) if isinstance(intent, LookIntent) else []
    )
    await remember(core, await tell_text(core, intent.text))
    if lore:  # M31.1b V13c: looking around the place teaches what its name holds
        await conclude(core, None, core.apply_all(lore), actor_id=entry.creature_id)


async def _impossible(core: TableCore, entry: QueueEntry, intent: ImpossibleIntent) -> None:
    event = ActionImpossible(
        creature_id=intent.actor_id,
        text=intent.text[:MAX_IMPOSSIBLE_TEXT],
        reason=intent.reason[:MAX_IMPOSSIBLE_REASON],
    )
    events = core.apply_all([event])
    await conclude(core, None, events, actor_id=intent.actor_id, player_text=entry.text)


async def _refused(core: TableCore, entry: QueueEntry, actor_id: str, reason: str | None) -> None:
    """M41.1 (round 7 Z4): a typed hand-over or payment the rules refuse (more gold than the hero
    has, not that many carried) moves nothing and is told as an impossible attempt with the
    rules' reason, never partly done. It counts as a refusal, so the line's later steps stop
    as after any refused act (`menu_pick.play_steps`)."""
    if reason is not None:
        await _impossible(core, entry, ImpossibleIntent(actor_id, entry.text, reason))
        core.refusals += 1


async def _pay(core: TableCore, entry: QueueEntry, intent: PayIntent) -> None:
    """M29.9a T17: the coins move first; "pay Rutter and ask him about the girl" then asks."""
    paid = hand_over.pay_first(core, intent)
    if isinstance(paid, str):
        await _refused(core, entry, intent.actor_id, paid)
        return
    if intent.rest is None:
        await conclude(core, None, paid, actor_id=intent.actor_id)
        return
    await adjudicated(core, entry.model_copy(update={"text": intent.rest}), prior=paid)


async def _gear_use(core: TableCore, player: Player, entry: QueueEntry, intent: UseIntent) -> None:
    """A typed gear use; M29.7a R17: "light a candle, then look around" lights it (or says why
    not in an engine line) AND the other act goes to the adjudicator, told together."""
    if intent.rest is None:
        if not await gear_actions.use_intent(core, player, intent):
            await adjudicated(core, entry)
        return
    prior = await gear_actions.first_act(core, player, intent)
    await adjudicated(core, entry.model_copy(update={"text": intent.rest}), prior=prior)
