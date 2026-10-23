"""The finale is a choice (M23.9, GOAL_QUESTS "Finale"). Pure: reads state, returns events.

When the final region resolves (`CampaignState.complete`) and the plan has a finale, the story is
not over yet: the party chooses one of its two endings. The open choice is derived from state
(never stored), so a reconnecting phone gets the card back and replay restores it. A plan
without a finale (old saves) ends at the final resolution as before; a save whose epilogue was
written before M23.9 never asks.

Public API:
- `FinaleRefused` (ValueError): no finale is waiting, or the ending is not one of the two.
- `finale_open(state) -> FinalePlan | None`: the finale waiting for the party's choice.
- `chosen_ending(state) -> FinaleOption | None`: the ending the party chose.
- `finale_texts(state) -> tuple[str, ...]`: what players may know of the finale now (the question
  and both ending titles while it is open or chosen, plus the chosen ending's text).
- `fight_first(state) -> bool`: a fight is under way, so the choice waits (M29.7c R15; the card
  hides meanwhile).
- `choose_events(state, option_id) -> list[AnyEvent]`: `[FinaleChosen]`.
"""

from aidm.models.campaign_events import FinaleChosen
from aidm.models.encounter import EncounterStatus
from aidm.models.events import AnyEvent
from aidm.models.quests import FinaleOption, FinalePlan
from aidm.models.state import GameState


class FinaleRefused(ValueError):
    """There is no finale to choose now, or the ending is unknown."""


def finale_open(state: GameState) -> FinalePlan | None:
    campaign = state.campaign
    if campaign is None or not campaign.complete or campaign.epilogue is not None:
        return None
    if campaign.finale_choice is not None:
        return None
    return campaign.plan.finale


def chosen_ending(state: GameState) -> FinaleOption | None:
    campaign = state.campaign
    finale = campaign.plan.finale if campaign is not None else None
    if campaign is None or finale is None:
        return None
    return next((o for o in finale.options if o.id == campaign.finale_choice), None)


def finale_texts(state: GameState) -> tuple[str, ...]:
    campaign = state.campaign
    finale = campaign.plan.finale if campaign is not None else None
    if finale is None:
        return ()
    chosen = chosen_ending(state)
    if finale_open(state) is None and chosen is None:
        return ()
    titles = tuple(o.title for o in finale.options)
    return (finale.question, *titles, *((chosen.text,) if chosen is not None else ()))


def fight_first(state: GameState) -> bool:
    """M29.7c R15: a fight under way (the party attacked an allied master in the finale) comes
    first; the ending is chosen once it is over."""
    enc = state.encounter
    return enc is not None and enc.status is EncounterStatus.ACTIVE


def choose_events(state: GameState, option_id: str) -> list[AnyEvent]:
    finale = finale_open(state)
    if finale is None:
        raise FinaleRefused("no finale is waiting for a choice")
    if fight_first(state):
        raise FinaleRefused("the fight comes first")
    if option_id not in {o.id for o in finale.options}:
        raise FinaleRefused(f"unknown ending {option_id!r}")
    return [FinaleChosen(option_id=option_id)]
