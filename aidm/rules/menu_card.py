"""The confirm card waiting for the acting hero's player, as two menu entries (M40.1, SPEC 6.2).
Pure.

Round 7 Z1: with the parley card up ("This answers the fight offer as a parley: one roll, a
failure starts the fight. Confirm?") the player typed "Yes, go ahead, I mean it"; the chooser's
menu had no trace of the card, so the model picked the offer's Fight answer. A card is part of
the hero's situation, so while one waits for this hero's player their menu carries it:
- `card:yes` plays what the card's **Yes, do it** button plays (`ConfirmHostile`: the held parley
  roll, the held hostile act, the held crossing), `card:no` what **No, hold back** plays
  (`CancelHostile`). They carry the card's own button words, and the yes the held act itself:
  the card's own prompt (`WaitingCard.prompt`, its closing "Confirm?" dropped), never phrases
  (so a typed "Yes, do it" is the card's yes on the exact path, with no model call).
- A card held for another hero is not in this hero's menu (`with_card` checks the actor).
- Any other pick keeps the rule the manual states (a new action counts as No): the session drops
  the card when the chosen steps hold no card entry (`picks_card`).
Fight menus never carry a card (a fight that starts clears it).

Public API: `CARD_YES`, `CARD_NO`, `WaitingCard`, `card_act(prompt)`, `card_entries(card)`,
`with_card(menu, card)`, `picks_card(choice)`.
"""

from dataclasses import dataclass

from aidm.models.action_menu import ActionKind, ActionMenu, MenuChoice, MenuEntry, MenuScope

CARD_YES = "card:yes"
CARD_NO = "card:no"
YES_LABEL = "Yes, do it (your waiting card: {act})"  # the card's own button words
NO_LABEL = "No, hold back (your waiting card)"
_ASK = "Confirm?"
_CARD_SCOPES = (MenuScope.EXPLORE, MenuScope.OFFER)


@dataclass(frozen=True)
class WaitingCard:
    """A confirm card held for one hero's player: the hero and what the card says."""

    actor_id: str
    prompt: str


def card_act(prompt: str) -> str:
    """The held act as the card states it, without the closing question."""
    text = prompt.strip()
    if text.endswith(_ASK):
        text = text[: -len(_ASK)].rstrip()
    return text.rstrip(".").strip() or text


def card_entries(card: WaitingCard) -> tuple[MenuEntry, MenuEntry]:
    act = card_act(card.prompt)
    yes = MenuEntry(
        id=CARD_YES,
        kind=ActionKind.CARD,
        label=YES_LABEL.format(act=act),
        cost="free",
        option="yes",
    )
    no = MenuEntry(id=CARD_NO, kind=ActionKind.CARD, label=NO_LABEL, cost="free", option="no")
    return yes, no


def with_card(menu: ActionMenu, card: WaitingCard | None) -> ActionMenu:
    """The menu with the card's two entries first, only when the card waits for this hero."""
    if card is None or card.actor_id != menu.actor_id or menu.scope not in _CARD_SCOPES:
        return menu
    taken = {e.id for e in menu.entries}
    if CARD_YES in taken or CARD_NO in taken:
        return menu
    return menu.model_copy(update={"entries": (*card_entries(card), *menu.entries)})


def picks_card(choice: MenuChoice) -> bool:
    return any(step.entry in (CARD_YES, CARD_NO) for step in choice.steps)
