"""Offer, quest-card and helping-up entries of the out-of-fight menu (M36.3, SPEC 6.2). Pure.

While an encounter offer waits at the party's place (the `offer` scope):
- `offer:fight`, `offer:surprise`, `offer:escape`, `offer:parley:<skill>` (Persuasion,
  Intimidation, Deception): the offer card's answers that the offer allows
  (`rules.offer_answer.answer_offer`);
- strikes at the offer's foes while they are still a threat (`rules.waiting_foe`): one attack
  per weapon the sheet lists (`attack:<item>`, `offhand:<item>`, `attack:unarmed`), each stowed
  weapon (`attack:<item>`, drawn first) and every hostile spell (`menu_casts.strike_casts`), all
  `starts_fight`: the offer is answered as Fight and the strike plays as typed on the hero's turn
  (M32.1a X3, M35.2 Y9, `session.offer_strike`);
- `surrender`: a demand that the foes yield, a parley with Intimidation; when every foe is a kind
  that never yields the note carries the rules' plain line (`rules.surrender`, M32.1a X5).
M36.8c (round 1 G-104 "attacks Old Broker Tann without warning"): every weapon the hero holds
(not the off hand: a bonus action never opens a fight) also aims at the people standing here, out
of a fight with or without an offer (`person_strikes` when none waits). Chosen, it is the
engine's own path for an attack on a person (`PersonStrikeIntent`: `start_encounter` against
them with the opening strike; a non-hostile person asks the point-of-no-return question first).
At any place out of a fight:
- `quest:accept`, `quest:decline`: the quest card's answers while a quest is asked by a living
  person standing here (`world.quest_ask`);
- `help_up`: helping a downed hero up to 1 HP (`rules.downed.help_up_events`).

Public API: `offer_entries(view)`, `person_strikes(view)`, `quest_entries(view)`,
`help_up_entries(view)`.
"""

from aidm.models.action_menu import ActionKind, MenuEntry
from aidm.models.campaign_state import EncounterOffer, OfferChoice
from aidm.models.sheet import AttackLine
from aidm.rules.attack_profiles import UNARMED_KEY
from aidm.rules.menu_casts import strike_casts
from aidm.rules.menu_labels import strike_label
from aidm.rules.menu_scene_view import SceneMenuView, offer_foes
from aidm.rules.offer_answer import PARLEY_SKILLS
from aidm.rules.surrender import offer_never_yield_line

_FIGHT_NOTE = "starts the fight"
_PERSON_NOTE = "starts a fight"
_ANSWERS = {
    OfferChoice.FIGHT: "Fight them (the fight starts)",
    OfferChoice.SURPRISE: "Sneak up and strike first (a group Stealth check, then the fight)",
    OfferChoice.ESCAPE: "Slip away to where you came from (group Stealth or Athletics)",
}


def _answers(offer: EncounterOffer) -> list[MenuEntry]:
    out: list[MenuEntry] = []
    for choice in offer.options:
        if choice is OfferChoice.PARLEY:
            for skill in PARLEY_SKILLS:
                label = f"Talk them out of fighting ({skill.value.title()})"
                out.append(
                    MenuEntry(
                        id=f"offer:parley:{skill.value}",
                        kind=ActionKind.OFFER,
                        label=label,
                        option=choice.value,
                        skill=skill.value,
                    )
                )
            continue
        entry_id = f"offer:{choice.value}"
        label = _ANSWERS[choice]
        out.append(MenuEntry(id=entry_id, kind=ActionKind.OFFER, label=label, option=choice.value))
    return out


def _strike(
    line: AttackLine, entry_id: str, foes: tuple[str, ...], people: tuple[str, ...]
) -> MenuEntry:
    aimed = foes + (people if line.hand != "off_hand" else ())
    note = _FIGHT_NOTE if foes else _PERSON_NOTE
    return MenuEntry(
        id=entry_id,
        kind=ActionKind.ATTACK,
        label=strike_label(line.name, line.range_band, line.damage),
        target_ids=aimed,
        max_targets=1,
        cost="bonus" if line.hand == "off_hand" else "attack",
        note=note,
        option=line.hand,
        item=line.item,
        starts_fight=bool(foes),
    )


def _stowed(view: SceneMenuView, foes: tuple[str, ...], taken: set[str]) -> list[MenuEntry]:
    out: list[MenuEntry] = []
    equipment = view.regs.chars.equipment
    for row in view.sheet.inventory:
        weapon = equipment.find(row.item)
        entry_id = f"attack:{row.item}"
        if (
            weapon is None
            or weapon.weapon_category is None
            or row.equipped_slot
            or entry_id in taken
        ):
            continue
        taken.add(entry_id)
        band = "ranged" if weapon.weapon_range == "Ranged" else "melee"
        out.append(
            MenuEntry(
                id=entry_id,
                kind=ActionKind.ATTACK,
                label=f"{row.name} ({band}, draws first)",
                target_ids=foes,
                max_targets=1,
                cost="attack",
                note=f"draws first, {_FIGHT_NOTE}",
                item=row.item,
                draw=row.item,
                starts_fight=True,
            )
        )
    return out


def _weapon_strikes(
    view: SceneMenuView, foes: tuple[str, ...], people: tuple[str, ...]
) -> list[MenuEntry]:
    out: list[MenuEntry] = []
    taken: set[str] = set()
    for line in view.sheet.attacks:
        if not foes and line.hand == "off_hand":
            continue
        prefix = "offhand" if line.hand == "off_hand" else "attack"
        entry_id = f"{prefix}:{line.item or UNARMED_KEY}"
        if entry_id in taken:
            entry_id = f"{entry_id}:{line.hand.replace('_', '-')}"
        taken.add(entry_id)
        out.append(_strike(line, entry_id, foes, people))
    return out + (_stowed(view, foes, taken) if foes else [])


def _surrender(view: SceneMenuView) -> MenuEntry:
    never = offer_never_yield_line(view.state, view.regs.monsters)
    return MenuEntry(
        id="surrender",
        kind=ActionKind.SURRENDER,
        label="Demand that they surrender (Intimidation)",
        note=never or "",
        skill="intimidation",
    )


def offer_entries(view: SceneMenuView) -> list[MenuEntry]:
    offer = view.offer
    if offer is None:
        return []
    out = _answers(offer)
    foes = tuple(t.id for t in offer_foes(view)) if view.threat else ()
    people = tuple(p for p in view.people if p not in foes)
    if foes or people:
        out += _weapon_strikes(view, foes, people)
    if foes:
        out += strike_casts(view, foes)
    if view.threat:
        out.append(_surrender(view))
    return out


def person_strikes(view: SceneMenuView) -> list[MenuEntry]:
    """M36.8c: no offer waits here: each held weapon at the people standing here."""
    return _weapon_strikes(view, (), view.people) if view.people else []


def quest_entries(view: SceneMenuView) -> list[MenuEntry]:
    world = view.state.world
    ask = world.quest_ask
    if ask is None or (ask.npc_id not in view.people and ask.npc_id not in view.twins):
        return []
    quest = world.quests.get(ask.quest_id)
    title = quest.title if quest is not None else ask.quest_id.replace("-", " ")
    who = world.npcs[ask.npc_id].name
    return [
        MenuEntry(
            id=f"quest:{answer}",
            kind=ActionKind.QUEST,
            label=f"{verb} the quest {title} (asked by {who})",
            option=answer,
            quest_id=ask.quest_id,
        )
        for answer, verb in (("accept", "Accept"), ("decline", "Decline"))
    ]


def help_up_entries(view: SceneMenuView) -> list[MenuEntry]:
    creatures = view.state.creatures
    downed = tuple(h for h in view.heroes if creatures[h].hp <= 0)
    if not downed:
        return []
    return [
        MenuEntry(
            id="help_up",
            kind=ActionKind.HELP_UP,
            label="Help a downed hero up (to 1 hit point)",
            target_ids=downed,
            max_targets=1,
        )
    ]
