"""Typed healing out of a fight at the table (M29.5b G2 / G17 / G33).

`heal_intent(core, player, intent)` runs the precheck's `HealIntent` through the ONE engine path
of each kind: a healing consumable through `rules.items.use_item_events` (the sheet's Use; the
carrier's draught is used up, the target heals, a dead target is refused and nothing is used),
a healing spell through `rules.spells.cast_spell` (the lowest fitting slot is spent; a spell
not on the sheet, no slot or a bad target is refused before any event). The events apply and
the storyteller tells them (`telling.conclude`). A refusal is told as the plain engine reason
(`tell_text`): never a heal that did not happen. M30.0b T7: a `CastIntent` (any other typed spell
out of a fight, `dm.cast_intent`) is cast the same way: the same sheet, slot and target checks
of `cast_spell`.

Public API: `heal_intent(core, player, intent)` (a `HealIntent` or a `CastIntent`).
"""

from aidm.dm.cast_intent import CastIntent
from aidm.dm.heal_intent import HealIntent
from aidm.models.events import AnyEvent
from aidm.rules.command_checks import CommandRefused
from aidm.rules.items import use_item_events
from aidm.rules.spells import cast_spell
from aidm.session.table_core import Player, TableCore
from aidm.session.telling import conclude, remember, tell_text


def _events(core: TableCore, intent: HealIntent) -> list[AnyEvent]:
    regs = core.regs.combat
    if intent.spell is not None:
        spell = regs.spells.get(intent.spell)
        return cast_spell(
            core.state, intent.actor_id, spell, None, intent.target_ids, None, core.rng, regs
        )
    assert intent.item is not None and intent.owner_id is not None
    target = intent.target_ids[0]
    return use_item_events(core.rng, core.state, intent.owner_id, intent.item, target, regs)


def _cast_events(core: TableCore, intent: CastIntent) -> list[AnyEvent]:
    regs = core.regs.combat
    spell = regs.spells.get(intent.spell)
    return cast_spell(
        core.state, intent.actor_id, spell, None, intent.target_ids, None, core.rng, regs
    )


async def heal_intent(core: TableCore, player: Player, intent: HealIntent | CastIntent) -> None:
    del player  # the seat already declared the action; the line is public
    try:
        events = (
            _cast_events(core, intent) if isinstance(intent, CastIntent) else _events(core, intent)
        )
    except CommandRefused as refused:
        await remember(core, await tell_text(core, refused.reason))
        return
    await conclude(core, None, core.apply_all(events), actor_id=intent.actor_id)
