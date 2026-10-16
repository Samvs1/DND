"""THE public projection of a roll (M9.4, M26.2): what the dice tray and the dice show read.

`dice_view(event) -> DiceView | None` turns an applied roll event into its view (every roll is
public): an attack (`kind` attack, its target, the advantage reasons), a check or save (`kind`
check/save, the creature that forced a save, the named bonuses, the advantage reasons, the DC
tier word), a death save ("Death save", DC 10) and plain dice (damage and healing land on
`target_id` when the rules know it). Other events give None. Every number comes from the event.

`event_subject(event) -> (subject_id, amount)`: the creature a damage, HP or death event is
about and the damage taken (`DamageTaken.total`) or HP healed (a positive `HpChanged.delta`).

Public API: `dice_view`, `event_subject`.
"""

from aidm.dm.wording import check_subject
from aidm.models.checks import CheckKind
from aidm.models.combat_events import AttackRolled
from aidm.models.dice import AdvState, D20Roll, RollKind
from aidm.models.events import (
    AnyEvent,
    CheckResolved,
    CreatureDied,
    DamageTaken,
    DeathSaveRolled,
    DiceRolled,
    HpChanged,
)
from aidm.models.protocol_views import DiceView
from aidm.rules.checks import difficulty_word

DEATH_SAVE_DC = 10


def _d20(roller: str | None, label: str, roll: D20Roll, target: int | None) -> DiceView:
    return DiceView(
        roller_id=roller,
        label=label,
        expression="1d20" if roll.adv is AdvState.NORMAL else "2d20",
        rolls=roll.rolls,
        adv=roll.adv,
        modifier=roll.modifier,
        total=roll.total,
        target=target,
        crit=roll.is_crit,
    )


def _attack(event: AttackRolled) -> DiceView:
    view = _d20(event.attacker_id, event.attack, event.roll, event.target_ac)
    return view.model_copy(
        update={
            "success": event.hit,
            "crit": event.crit,
            "kind": RollKind.ATTACK,
            "target_id": event.target_id,
            "adv_why": event.adv_why,
        }
    )


def _check(event: CheckResolved) -> DiceView:
    r = event.result
    save = r.kind is CheckKind.SAVE
    view = _d20(event.creature_id, check_subject(r) + (" save" if save else ""), r.roll, r.dc)
    return view.model_copy(
        update={
            "success": r.success,
            "kind": RollKind.SAVE if save else RollKind.CHECK,
            "source_id": event.source_id,
            "parts": r.parts,
            "adv_why": r.adv_why,
            "difficulty": difficulty_word(r.tier) if r.tier is not None else None,
        }
    )


def dice_view(event: AnyEvent) -> DiceView | None:
    if isinstance(event, AttackRolled):
        return _attack(event)
    if isinstance(event, CheckResolved):
        return _check(event)
    if isinstance(event, DeathSaveRolled):
        view = _d20(event.creature_id, "Death save", event.roll, DEATH_SAVE_DC)
        success = event.roll.total >= DEATH_SAVE_DC
        return view.model_copy(update={"success": success, "kind": RollKind.DEATH_SAVE})
    if isinstance(event, DiceRolled):
        r = event.roll
        return DiceView(
            roller_id=event.roller_id,
            label=event.label,
            expression=r.expression,
            rolls=tuple(d.value for d in r.dice if d.kept),
            modifier=r.modifier,
            total=r.total,
            kind=event.kind,
            target_id=event.target_id,
        )
    return None


def event_subject(event: AnyEvent) -> tuple[str | None, int | None]:
    if isinstance(event, DamageTaken):
        return event.creature_id, event.total
    if isinstance(event, HpChanged):
        return event.creature_id, event.delta if event.delta > 0 else None
    if isinstance(event, CreatureDied):
        return event.creature_id, None
    return None, None
