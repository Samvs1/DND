"""Fight menu entries for the standard actions and movement (M36.2, SPEC 6.2). Pure.

`move` (every other zone, noted with its walking feet, "needs Dash" or out of reach this turn),
`stand` (prone), `dash`, `disengage`, `dodge`, `hide` and their bonus-action forms when a feature
grants them (`dash:bonus` ..., Cunning Action, from the feature hooks), `help` (allies; a downed
ally is helped up), `shove:prone` and `shove:push` (foes; a push then names the zone), `jump`
(zones the real command accepts), `end:<condition>` (a condition an action can end, the sheet's
`end_label`), `flee`, `surrender:<skill>` (the demand, `rules.surrender.SURRENDER_SKILLS`) and
`end-turn`. Helping and shoving a creature out of reach work like a melee strike: an approach
target or out of reach this turn (`menu_probe`).

Public API: `move_entries(view)`, `touch_entries(view)`, `standard_entries(view)`.
"""

from aidm.models.action_menu import ActionKind, EntryCost, MenuEntry
from aidm.models.commands import (
    AnyCommand,
    FleeCommand,
    HelpCommand,
    JumpCommand,
    RefusalCode,
    ShoveCommand,
)
from aidm.rules.conditions import effective_speed
from aidm.rules.features import feature_actions
from aidm.rules.menu_probe import probe_targets, refusal
from aidm.rules.menu_view import FAR_NOTE, FightView, aim_of, is_spent
from aidm.rules.surrender import SURRENDER_SKILLS
from aidm.rules.zones import MELEE_BAND

PRONE = "prone"
_SIMPLE: dict[str, tuple[ActionKind, str]] = {
    "dash": (ActionKind.DASH, "Dash (double your movement this turn)"),
    "disengage": (ActionKind.DISENGAGE, "Disengage (move away without being held back)"),
    "dodge": (ActionKind.DODGE, "Dodge (attacks against you have disadvantage)"),
    "hide": (ActionKind.HIDE, "Hide (Stealth check, hidden until seen)"),
}
_SURRENDER_ASKS = {  # M36.9 iteration 2: the Persuasion form reads as an offer of mercy
    "intimidation": "Demand the foes surrender",
    "persuasion": "Call on the foes to yield and be spared",
}


def _zone_note(view: FightView, feet: int) -> str:
    left = view.economy.movement_left
    if feet <= left:
        return f"{feet} ft"
    hero = view.state.creatures[view.actor_id]
    if not view.economy.dashed and feet <= left + effective_speed(hero):
        return f"{feet} ft, needs Dash"
    return f"{feet} ft, {FAR_NOTE}"


def move_entries(view: FightView) -> list[MenuEntry]:
    zones = [z for z in view.zone_feet if z != view.zone_id]
    notes = {z: _zone_note(view, view.zone_feet[z]) for z in zones}
    out = [
        MenuEntry(
            id="move",
            kind=ActionKind.MOVE,
            label=f"Move to another area ({view.economy.movement_left} ft of movement left)",
            target_ids=tuple(zones),
            max_targets=1 if zones else 0,
            cost="movement",
            spent=is_spent(view, "movement"),
            target_notes=notes,
            far=tuple(z for z in zones if FAR_NOTE in notes[z]),
        )
    ]
    hero = view.state.creatures[view.actor_id]
    if any(c.name == PRONE for c in hero.conditions):
        out.append(
            MenuEntry(
                id="stand",
                kind=ActionKind.STAND,
                label="Stand up (costs half your movement)",
                cost="movement",
                spent=is_spent(view, "movement"),
            )
        )
    jumps = probe_targets(
        view.ready,
        view.actor_id,
        zones,
        lambda z: JumpCommand(actor_id=view.actor_id, zone_id=z),
        view.regs,
    )
    if jumps.ready:
        out.append(
            MenuEntry(
                id="jump",
                kind=ActionKind.JUMP,
                label="Jump to a neighbouring area (bonus action)",
                target_ids=jumps.ready,
                max_targets=1,
                cost="bonus",
                spent=is_spent(view, "bonus"),
            )
        )
    return out


def _touch(
    view: FightView, entry_id: str, kind: ActionKind, label: str, cost: EntryCost, build: str
) -> MenuEntry | None:
    allies = build == "help"
    candidates = view.allies if allies else view.foes

    def command(cid: str) -> AnyCommand:
        if allies:
            return HelpCommand(actor_id=view.actor_id, target_id=cid)
        return ShoveCommand(actor_id=view.actor_id, target_id=cid, mode="prone")

    reach = probe_targets(
        view.ready, view.actor_id, candidates, command, view.regs, MELEE_BAND, True
    )
    if not reach.listed:
        return None
    down = {c: "down: helps them up" for c in reach.listed if view.state.creatures[c].hp <= 0}
    aim = aim_of(reach, down if allies else None)
    zones = tuple(view.zone_feet) if entry_id == "shove:push" else ()
    return MenuEntry(
        id=entry_id,
        kind=kind,
        label=label,
        target_ids=aim.target_ids,
        max_targets=1,
        zone_ids=zones,
        cost=cost,
        spent=is_spent(view, cost),
        note="then pick the area to push into" if zones else "",
        target_notes=aim.notes,
        approach=aim.approach,
        far=aim.far,
    )


def touch_entries(view: FightView) -> list[MenuEntry]:
    made = [
        _touch(
            view,
            "help",
            ActionKind.HELP,
            "Help an ally (advantage, or up from 0 HP)",
            "action",
            "help",
        ),
        _touch(
            view,
            "shove:prone",
            ActionKind.SHOVE,
            "Shove a foe prone (bonus action)",
            "bonus",
            "shove",
        ),
        _touch(
            view,
            "shove:push",
            ActionKind.SHOVE,
            "Shove a foe away (bonus action)",
            "bonus",
            "shove",
        ),
    ]
    return [e for e in made if e is not None]


def _simple(view: FightView, key: str, cost: EntryCost, source: str = "") -> MenuEntry:
    kind, label = _SIMPLE[key]
    if cost == "bonus":
        label = label.replace(" (", f" (bonus action, {source}, ", 1)
    return MenuEntry(
        id=key if cost == "action" else f"{key}:bonus",
        kind=kind,
        label=label,
        cost=cost,
        spent=is_spent(view, cost),
    )


def _bonus_forms(view: FightView) -> list[MenuEntry]:
    hero = view.state.creatures[view.actor_id]
    out: list[MenuEntry] = []
    for option in feature_actions(hero, view.regs.chars.features):
        if option.action in _SIMPLE and option.economy.value == "bonus_action":
            entry = _simple(view, option.action, "bonus", option.name)
            if all(e.id != entry.id for e in out):
                out.append(entry)
    return out


def _ending(view: FightView) -> list[MenuEntry]:
    out: list[MenuEntry] = []
    for line in view.sheet.conditions:
        entry_id = f"end:{line.name}"
        if line.end_label and all(e.id != entry_id for e in out):
            out.append(
                MenuEntry(
                    id=entry_id,
                    kind=ActionKind.END_CONDITION,
                    label=f"{line.end_label} (action)",
                    spent=is_spent(view, "action"),
                    condition=line.name,
                )
            )
    return out


def _closing(view: FightView) -> list[MenuEntry]:
    flee = refusal(view.state, FleeCommand(actor_id=view.actor_id), view.regs)
    out = [
        MenuEntry(
            id="flee",
            kind=ActionKind.FLEE,
            label="Flee the fight",
            cost="free",
            note="needs Disengage first" if flee is RefusalCode.ENGAGED else "",
        )
    ]
    bonus = {s.skill: s.bonus for s in view.sheet.skills}
    if view.foes:
        for skill in SURRENDER_SKILLS:
            sign = f"{bonus[skill]:+d}"
            out.append(
                MenuEntry(
                    id=f"surrender:{skill.value}",
                    kind=ActionKind.SURRENDER,
                    label=f"{_SURRENDER_ASKS[skill.value]} ({skill.value.title()} {sign}, action)",
                    spent=is_spent(view, "action"),
                    skill=skill.value,
                )
            )
    out.append(MenuEntry(id="end-turn", kind=ActionKind.END_TURN, label="End turn", cost="free"))
    return out


def standard_entries(view: FightView) -> list[MenuEntry]:
    simple = [_simple(view, key, "action") for key in _SIMPLE]
    return [*simple, *_bonus_forms(view), *_ending(view), *_closing(view)]
