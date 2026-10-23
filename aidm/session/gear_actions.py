"""Typed gear use at the table (M27.5, docs/next/GOAL_ITEMS.md "Design", "Light and darkness").

- `use_intent(core, player, intent) -> bool` (out of a fight, from the precheck): a put-out
  (`rules.light.put_out`, free) or THE interpreter (`rules.item_use.use_item`); the events apply
  and the narrator tells them (`telling.conclude`; the engine lines of `dm.item_text` go out as
  they apply). A refused use returns False: the caller hands the words to the adjudicator, which
  tells the attempt (the model meets the same refusal through `use_item`). A put-out with no
  light gets a notice. A long-rest use (herbalism) proposes the long rest WITH the crafting.
- `rest_with_crafts(core, crafts) -> Job`: the long rest, then each `(hero, item)` long-rest use
  with `resting=True`; a craft the rules refuse after the rest (supplies spent by the rest, no
  proficiency) is told as a notice and nothing is made.
- `fight_gear(core, player, entry) -> bool` (a fight): a typed put-out (free, on any turn) or a
  typed light (a bonus action on the hero's own turn, the interpreter spends it) is scheduled
  here (a refusal is a notice). M27.6: any other typed gear use on the hero's own turn ("throw
  the acid at the goblin", "scatter the caltrops", "use my healer's kit on Bryn") runs the
  interpreter too when it fits (checked first with a throwaway RNG); a use the rules refuse
  returns False and keeps the fight's own path (the AI meets the same refusal). Anything else
  returns False.

Public API: `use_intent`, `rest_with_crafts`, `fight_gear`.
"""

import random

from aidm.dm.precheck import gear_intent
from aidm.dm.use_intent import UseIntent
from aidm.models.events import AnyEvent
from aidm.models.item_events import ItemUseRefused
from aidm.models.protocol_server import CombatState, NoticeKind
from aidm.models.protocol_views import QueueEntry, VoteKind
from aidm.rules.dice import Rng
from aidm.rules.item_effects import gear_name
from aidm.rules.item_use import use_item
from aidm.rules.light import put_out
from aidm.rules.rests import RestRefused, long_rest, rest_refused_text
from aidm.session import combat_flow, votes
from aidm.session.declared import declare
from aidm.session.table_core import Job, Player, TableCore
from aidm.session.telling import conclude
from aidm.session.views import public_combat

_LIGHT_VERBS = ("light", "ignite", "kindle")


def _refusal(events: list[AnyEvent]) -> str | None:
    return next((e.message for e in events if isinstance(e, ItemUseRefused)), None)


def _events(core: TableCore, intent: UseIntent, rng: Rng | None = None) -> list[AnyEvent]:
    if intent.put_out:
        return put_out(core.state, intent.actor_id)
    return use_item(
        core.state,
        intent.actor_id,
        intent.item,
        intent.target,
        rng=rng or core.rng,
        use_id=intent.use_id,
        regs=core.regs.combat,
    )


async def use_intent(core: TableCore, player: Player, intent: UseIntent) -> bool:
    if intent.at_rest:
        detail = f"make camp for a long rest and use the {gear_name(intent.item).lower()}"
        job = rest_with_crafts(core, ((intent.actor_id, intent.item),))
        if votes.open_vote(core, VoteKind.LONG_REST, detail, player, job):
            core.notice(None, NoticeKind.INFO, f"{player.name} proposes to {detail}.")
        return True
    events = _events(core, intent)
    refused = _refusal(events)
    if refused is not None:
        if intent.put_out:
            core.notice(player.id, NoticeKind.REFUSED, refused)
        return intent.put_out
    applied = core.apply_all(events)
    await conclude(core, None, applied, actor_id=intent.actor_id)
    return True


def rest_with_crafts(core: TableCore, crafts: tuple[tuple[str, str], ...]) -> Job:
    async def job() -> None:
        try:
            events = core.apply_all(long_rest(core.state))
        except RestRefused as refused:
            core.notice(None, NoticeKind.REFUSED, rest_refused_text(refused))
            return
        for actor_id, item in crafts:
            made = use_item(
                core.state, actor_id, item, rng=core.rng, resting=True, regs=core.regs.combat
            )
            refused = _refusal(made)
            if refused is not None:
                core.notice(None, NoticeKind.REFUSED, refused)
                continue
            events += core.apply_all(made)
        await conclude(core, None, events)

    return job


def fight_gear(core: TableCore, player: Player, entry: QueueEntry) -> bool:
    intent = gear_intent(core.state, entry.creature_id, entry.text)
    if intent is None or intent.at_rest:
        return False
    enc = core.state.encounter
    if not intent.put_out and (enc is None or enc.active_id() != entry.creature_id):
        return False
    lighting = intent.put_out or intent.verb in _LIGHT_VERBS
    if not lighting and _refusal(_events(core, intent, random.Random(0))) is not None:
        return False

    async def job() -> None:
        events = _events(core, intent)
        refused = _refusal(events)
        if refused is not None:
            core.notice(player.id, NoticeKind.REFUSED, refused)
            return
        declare(core, entry)
        core.apply_all(events)
        if intent.put_out or core.state.encounter is None:
            core.broadcast(CombatState(combat=public_combat(core.state)))
            return
        await combat_flow.after_player_step(core, entry.creature_id)  # a throw may end the fight

    core.schedule(job)
    return True
