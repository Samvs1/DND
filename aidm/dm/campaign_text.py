"""Plain-language lines for the campaign events (M5.4): one set for the model, one for templates.

`CAMPAIGN_EVENT_LINES` join `aidm.dm.event_text` (authoritative lines with numbers, for the
model); `CAMPAIGN_TEMPLATE_LINES` join `aidm.dm.narration_templates` (no digits, for players when
no model is available). The encounter offer IS the warning beat, so its template line always
names the danger and the choices. Never renders motives, secrets or ally paths.
"""

from collections import Counter
from collections.abc import Callable
from typing import Any

from aidm.dm.entities import display_name
from aidm.dm.wording import counted
from aidm.models import campaign_events as ce
from aidm.models.campaign_state import EncounterOffer, RegionResolution
from aidm.models.state import GameState
from aidm.rules.scene import node_display_name

CHOICES_LINE = "Fight, strike first, slip away, or try to talk?"


def _foes(state: GameState, offer: EncounterOffer, *, digits: bool) -> str:
    """The boss, then each kind of foe with its count (M20.6: two rats are two rats)."""
    counts = Counter(offer.monster_ids)
    names = [counted(display_name(m).lower(), n, digits=digits) for m, n in counts.items()]
    boss = state.world.npcs.get(offer.boss_npc_id or "")
    if boss is not None:
        names.insert(0, boss.name)
    return ", ".join(names) or "something"


def _offer_fact(state: GameState, e: ce.EncounterOffered) -> str:
    o = e.offer
    return (
        f"WARNING BEAT at {node_display_name(state, o.node_id)}: {_foes(state, o, digits=True)} "
        f"({o.difficulty}). The party chooses: fight, surprise (Stealth DC {o.surprise_dc}), "
        f"escape (DC {o.escape_dc}) or parley (DC {o.parley_dc}). Nothing has started yet: "
        "nobody has attacked, cast, hit, fallen or fled."
    )


def _offer_story(state: GameState, e: ce.EncounterOffered) -> str:
    boss = state.world.npcs.get(e.offer.boss_npc_id or "")
    if boss is not None:
        return f"{boss.name} is waiting for you here, and the air turns cold. {CHOICES_LINE}"
    return f"Danger stirs ahead: {_foes(state, e.offer, digits=False)}. {CHOICES_LINE}"


def _resolved_fact(state: GameState, e: ce.RegionResolved) -> str:
    end = " The campaign is complete." if e.final else " The way to the next region is open."
    return f"Region {e.region_id} resolved by {e.how.value}.{end}"


def _resolved_story(state: GameState, e: ce.RegionResolved) -> str:
    if e.final:
        return "The last shadow lifts, and your tale draws to its close."
    if e.how is RegionResolution.ALLIANCE:
        return "An uneasy alliance is struck, and the way onward opens."
    return "With its master fallen, the land breathes again, and the way onward opens."


def _answer_story(state: GameState, e: ce.OfferResolved) -> str | None:
    if e.success and e.choice.value == "escape":
        return "You slip away before the danger can close in."
    if e.success and e.choice.value == "parley":
        return "Words win out, and no blade is drawn."
    return None


CAMPAIGN_EVENT_LINES: dict[type[Any], Callable[[GameState, Any], str | None]] = {
    ce.EncounterOffered: _offer_fact,
    ce.OfferResolved: lambda s, e: (
        f"The party chose {e.choice.value}"
        + ("" if e.success is None else f" ({'success' if e.success else 'failure'})")
        + f": {e.detail}."
    ),
    ce.RegionResolved: _resolved_fact,
    ce.CampaignInstalled: lambda s, e: None,
}

CAMPAIGN_TEMPLATE_LINES: dict[type[Any], Callable[[GameState, Any], str | None]] = {
    ce.EncounterOffered: _offer_story,
    ce.OfferResolved: _answer_story,
    ce.RegionResolved: _resolved_story,
}
