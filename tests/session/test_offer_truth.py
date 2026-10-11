"""Offers tell no blows (M20.6, playtest 3: the offer narration had the warlock blast the stirge
into the water before any choice, memory kept it as a fact, and the victory invented "a second
stirge"; two giant rats were announced as "a giant rat")."""

from aidm.dm.campaign_text import CAMPAIGN_EVENT_LINES, CAMPAIGN_TEMPLATE_LINES
from aidm.dm.guard import check_prose
from aidm.dm.guard_types import ViolationKind
from aidm.dm.narration_weight import OFFER_STANDOFF, truth_notes
from aidm.models.campaign_events import EncounterOffered
from aidm.models.state import GameState
from tests.session.progression_fixtures import campaign_state, move, pending

BLAST = (
    "Slendee's hand is already up, and the burst of eldritch light catches it mid-flight,"
    " sending it tumbling into the black water."
)


def _offered() -> tuple[GameState, EncounterOffered]:
    _, state, log = campaign_state()
    region = state.campaign.plan.acts[0].region if state.campaign is not None else None
    assert region is not None
    events = move(state, region.spokes[0].id, log)
    offered = next(e for e in events if isinstance(e, EncounterOffered))
    return state, offered


def test_offer_narration_is_told_that_nothing_happened_yet() -> None:
    state, offered = _offered()
    assert OFFER_STANDOFF in truth_notes([offered])
    fact = CAMPAIGN_EVENT_LINES[EncounterOffered](state, offered)
    assert fact is not None and "nobody has attacked" in fact


def test_offer_lines_count_the_foes() -> None:
    state, offered = _offered()
    offer = offered.offer.model_copy(update={"monster_ids": ("giant-rat", "giant-rat")})
    twin = offered.model_copy(update={"offer": offer})
    fact = CAMPAIGN_EVENT_LINES[EncounterOffered](state, twin) or ""
    story = CAMPAIGN_TEMPLATE_LINES[EncounterOffered](state, twin) or ""
    assert "2 giant rats" in fact and "two giant rats" in story


def test_guard_flags_a_blow_while_the_offer_waits() -> None:
    state, _ = _offered()
    assert pending(state) is not None
    kinds = {v.kind for v in check_prose(BLAST, state).violations}
    assert ViolationKind.OFFER_BLOW in kinds
    calm = "The creature hangs in the reeds, watching you."
    assert ViolationKind.OFFER_BLOW not in {v.kind for v in check_prose(calm, state).violations}
