"""The opening strike (M19.2, owner choice "rolled right away as the fight starts, BG3 style").

When a hero starts a fight by attacking a present NPC, the adjudicator names that NPC in
`start_encounter(opening_strike_on=..., opening_attack=...)`. Right after the fight's events are
applied (the NPC now stands in the party's zone as a combat creature of the same name), the attack
the hero named (a spell with an attack roll or a weapon; M20.5) is rolled through
`rules.opening_strike.opening_strike` and applied, so the narration that follows tells the real
result. The fight then runs by initiative as usual; a strike that drops the last
foe ends it at once (`combat_flow.advance` checks the outcome before the first turn).

Public API: `strike_if_opening(core, call, actor_id, events) -> list[AnyEvent]`.
"""

from collections.abc import Sequence

from aidm.dm.llm_types import ToolCall
from aidm.dm.tools import StartEncounterArgs
from aidm.models.encounter_events import EncounterStarted
from aidm.models.events import AnyEvent, CreatureAdded
from aidm.rules.opening_strike import opening_strike
from aidm.session.table_core import TableCore


def _target(events: Sequence[AnyEvent], name: str) -> str | None:
    added = (e.creature for e in events if isinstance(e, CreatureAdded))
    return next((c.id for c in added if c.name == name), None)


def strike_if_opening(
    core: TableCore, call: ToolCall, actor_id: str | None, events: Sequence[AnyEvent]
) -> list[AnyEvent]:
    """Roll and apply the opening strike of a fight `call` just started; [] when there is none."""
    args = call.args
    if not isinstance(args, StartEncounterArgs) or args.opening_strike_on is None:
        return []
    if actor_id is None or not any(isinstance(e, EncounterStarted) for e in events):
        return []
    npc = core.state.world.npcs.get(args.opening_strike_on)
    target = _target(events, npc.name) if npc is not None else None
    attacker = core.state.creatures.get(actor_id)
    if target is None or attacker is None or attacker.dead or attacker.hp <= 0:
        return []
    regs, attack = core.regs.combat, args.opening_attack
    strike = opening_strike(core.state, actor_id, target, regs, core.rng, attack)
    return core.apply_all(strike) if strike else []
