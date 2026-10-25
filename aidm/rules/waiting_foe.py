"""A hostile encounter offer waiting where the party stands (M35.2, round 6 Y4 and Y9). Pure.

The offer is the warning beat before a fight: the foes have seen the party and nothing has
started yet. Two acts at that moment are not what they would be anywhere else:
- a rest (Y4: a long rest was taken in front of a waiting master, who "had not moved"). Making
  camp in front of a foe is possible, so it is never refused (owner rule); the foe takes the
  opening: the offer is answered as a fight and the party is caught off guard (surprised, SRD
  5.1 "Surprise"), and no rest is taken (docs/DECISIONS.md M35.2);
- a hostile spell (Y9: Sleep typed at the waiting kobolds was cast "at the scene", the slot
  spent and the offer still waiting). It is the opening act of the fight (M32.1a's rule), so it
  is never cast at the scene: the session starts the fight and plays the cast on the hero's turn
  (`session.offer_strike`), and `rules.spells.scene_cast` refuses it before any slot is spent.

Public API:
- `waiting_foe(state) -> EncounterOffer | None`: the offer waiting at the party's place whose
  foes are still a threat (not settled peacefully, `progression.settled_offer`; foes not gone,
  `offer_answer.foes_gone`).
- `cast_starts_fight(state, spell) -> bool`: a hostile spell (`spell_targets.strikes_creatures`:
  an attack, a save, damage or an HP pool) while such an offer waits.
- `FOE_WAITS`: the refusal of such a spell cast at the scene (it belongs to the fight).
- `rest_ambush_events(state, data, rng) -> list[AnyEvent]`: `[]` with no foe waiting; else the
  offer's `OfferResolved` (fight) and the fight's start with the party surprised.
"""

from aidm.data.spell_defs import SpellDef
from aidm.models.campaign_state import EncounterOffer, OfferChoice
from aidm.models.encounter import SurpriseKind
from aidm.models.events import AnyEvent
from aidm.models.state import GameState
from aidm.rules.dice import Rng
from aidm.rules.encounter_offer import offer_fight_events
from aidm.rules.offer_answer import foes_gone
from aidm.rules.offer_spokes import OfferData
from aidm.rules.progression import offer_closed, settled_offer
from aidm.rules.spell_targets import strikes_creatures

FOE_WAITS = "A foe waits here: a harmful spell starts the fight and is cast in it."
_AMBUSH_DETAIL = "the foes strike while the party makes camp: no rest, the party is surprised"


def waiting_foe(state: GameState) -> EncounterOffer | None:
    campaign = state.campaign
    offer = campaign.offer if campaign is not None else None
    if offer is None or offer.node_id != state.world.current_node:
        return None
    if settled_offer(state) is not None or foes_gone(state, offer):
        return None
    return offer


def cast_starts_fight(state: GameState, spell: SpellDef) -> bool:
    return strikes_creatures(spell) and waiting_foe(state) is not None


def rest_ambush_events(state: GameState, data: OfferData, rng: Rng) -> list[AnyEvent]:
    offer = waiting_foe(state)
    if offer is None:
        return []
    return [
        offer_closed(offer, OfferChoice.FIGHT, detail=_AMBUSH_DETAIL),
        *offer_fight_events(state, offer, data, rng, SurpriseKind.PARTY),
    ]
