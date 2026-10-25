"""A typed attack while the encounter offer waits (M32.1a X3, round 5: "Rook attacks the bandit
with his shortbow", "I cast Burning Hands at the violet fungus" and "I fling a scorching ray at
the gnoll" only started the fight; the attack or the cast never happened while the story told
"Rook's arrow flies true" and "flame roars from his palms").

`offer_strike_turn(core, player, entry, intent)`: the line answers the offer as its Fight button
does (`rules.offer_answer.answer_offer`, every foe of the offer fielded, initiative as always:
the engine's own order, no free first blow), and the same words wait on the player's seat
(`waiting_line.keep`) until the hero's turn opens; then they are played as typed (the attack
rolls, the spell is cast, or the rules say why not). The player is told plainly that the fight
started and the act waits for the turn, and the story of the fight's start is told without the
player's words, so it never tells the blow or the spell before the engine does. An offer that
closes without a fight (its foes are gone, the region is settled) goes to the storyteller.

M35.2 (round 6 Y9: "I cast Sleep on the kobolds behind the spur" at a waiting offer was cast at
the scene, the slot spent and the offer still waiting): a typed cast of a harmful spell while a
foe's offer waits here (`rules.waiting_foe.cast_starts_fight`) is the same act
(`cast_opens_fight`): the fight starts and the cast waits for the hero's turn.

M36.6 (menu interpreter): an offer strike chosen from the menu carries its step
(`OfferStrikeIntent.step`); the seat keeps it as a job (`menu_fight_turn.held_strike`) that aims
the step at the spawned foes on the hero's turn (`rules.menu_steps.resume_strike`).

Public API: `WAITS`, `offer_strike_turn`, `cast_opens_fight`.
"""

from aidm.dm.arrival import offer_data
from aidm.models.campaign_state import OfferChoice
from aidm.models.protocol_server import NoticeKind
from aidm.models.protocol_views import QueueEntry
from aidm.rules.acts import CastIntent, OfferStrikeIntent
from aidm.rules.offer_answer import OfferRefused, answer_offer
from aidm.rules.waiting_foe import cast_starts_fight
from aidm.session import combat_flow, waiting_line
from aidm.session.held import adjudicated
from aidm.session.menu_fight_turn import held_strike
from aidm.session.table_core import Player, TableCore
from aidm.session.telling import conclude

WAITS = "The fight starts. What you typed waits for {name}'s turn and is played then, as typed."


def cast_opens_fight(core: TableCore, intent: CastIntent) -> bool:
    spell = core.regs.combat.spells.find(intent.spell)
    return spell is not None and cast_starts_fight(core.state, spell)


async def offer_strike_turn(
    core: TableCore, player: Player, entry: QueueEntry, intent: OfferStrikeIntent
) -> None:
    hero = core.state.creatures[intent.actor_id]
    try:
        events = answer_offer(
            core.state, OfferChoice.FIGHT, offer_data(core.regs), core.rng, actor_id=hero.id
        )
    except OfferRefused:
        await adjudicated(core, entry)
        return
    core.apply_all(events)
    if core.combat_active():
        step = intent.step
        strike = held_strike(core, player, hero.id, step, entry.text) if step else None
        waiting_line.keep(player, entry.text, strike)
        core.notice(player.id, NoticeKind.INFO, WAITS.format(name=hero.name))
    every = await conclude(core, None, events, actor_id=hero.id)
    await combat_flow.after_resolution(core, every)
