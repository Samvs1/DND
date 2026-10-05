"""Deterministic template narration from engine events (SPEC 6.8: no key, outage, bad output).

Used whenever the narrator cannot use the model (disabled, failure, timeout, empty answer) and
as the guard's safe fallback (SPEC 6.5). It is built ONLY from engine events and state, never
from model text, so it cannot hallucinate: names come from state, features and items from the
registry, and private data (hidden features, motives, unrevealed secrets) is never rendered.
Prose carries no mechanics numbers (the dice tray shows them). Every resolution narrates:
`template_narration` never returns an empty list (v1: failed checks produced no narration).

Public API:
- `template_narration(events, state, notice=None) -> list[str]`: one in-fiction sentence per
  meaningful event (duplicates collapsed); when nothing renders, `notice` or `QUIET_LINE`.
- `template_line(state, event) -> str | None`.
- `QUIET_LINE`, `CLOSING_LINE` (the graceful ending appended to a cut-off model stream).
"""

from collections.abc import Callable, Sequence
from typing import Any

from aidm.dm.campaign_text import CAMPAIGN_TEMPLATE_LINES
from aidm.dm.entities import display_name
from aidm.dm.wording import ABILITY_NAMES, check_subject
from aidm.models import events as ev
from aidm.models import world_events as we
from aidm.models.combat_events import (
    AttackRolled,
    CombatantMoved,
    CreatureRevived,
    FeatureUsed,
    MonsterActionUsed,
    SpellCast,
)
from aidm.models.encounter import EncounterStatus, WithdrawReason
from aidm.models.encounter_events import CombatantWithdrew, EncounterEnded, EncounterStarted
from aidm.models.state import GameState
from aidm.models.world import QuestState
from aidm.rules.scene import node_display_name

QUIET_LINE = "The moment passes, and the world waits for what you do next."
CLOSING_LINE = "The moment settles, and the scene waits on your next move."

_ENDINGS = {
    EncounterStatus.VICTORY: "The last foe falls, and the fight is won.",
    EncounterStatus.DEFEAT: "The party falls, and darkness closes in.",
    EncounterStatus.FLED: "You break away and leave the fight behind.",
    EncounterStatus.PARLEY: "Weapons lower as the fighting stops.",
    EncounterStatus.ACTIVE: "The fight goes on.",
}
_QUESTS = {
    QuestState.OFFERED: "A new task is offered: {title}.",
    QuestState.ACTIVE: "A task now lies before you: {title}.",
    QuestState.COMPLETED: "You have seen {title} through to the end.",
    QuestState.FAILED: "{title} has slipped beyond your reach.",
}


def _who(state: GameState, creature_id: str | None) -> str:
    if creature_id is None:
        return "Someone"
    creature = state.creatures.get(creature_id)
    if creature is not None:
        return creature.name
    npc = state.world.npcs.get(creature_id)
    return npc.name if npc is not None else display_name(creature_id)


def _check(state: GameState, e: ev.CheckResolved) -> str:
    r = e.result
    who = _who(state, e.creature_id)
    if r.kind.value == "save":
        ability = ABILITY_NAMES[r.ability]
        if r.success:
            return f"{who} resists, and the {ability} save holds."
        return f"{who} cannot shake it off; the {ability} save fails."
    what = check_subject(r)
    if r.success:
        return f"{who} pulls it off, and the {what} attempt succeeds."
    return f"{who} gives it everything, but the {what} attempt fails."


def _attack(state: GameState, e: AttackRolled) -> str:
    attacker, target = _who(state, e.attacker_id), _who(state, e.target_id)
    if e.crit:
        return f"{attacker} lands a devastating blow on {target}."
    if e.hit:
        return f"{attacker} strikes {target}."
    return f"{attacker} attacks {target} but misses."


def _hp(state: GameState, e: ev.HpChanged) -> str | None:
    who = _who(state, e.creature_id)
    if e.delta > 0:
        return f"Strength flows back into {who}."
    if e.delta < 0 and e.new_hp > 0:
        return f"{who} is wounded."
    return None


def _moved(state: GameState, e: CombatantMoved) -> str:
    who = _who(state, e.creature_id)
    return f"{who} is forced back." if e.reason == "push" else f"{who} moves to a new position."


def _feature(state: GameState, e: we.FeatureIntroduced) -> str | None:
    return None if e.feature.hidden else f"You notice {e.feature.name}."


def _discovered(state: GameState, e: we.FeatureDiscovered) -> str:
    feature = state.world.features.get(e.feature_id)
    name = feature.name if feature is not None else "something hidden"
    return f"{_who(state, e.creature_id)} discovers {name}."


def _secret(state: GameState, e: we.SecretRevealed) -> str:
    npc = state.world.npcs.get(e.npc_id)
    if npc is None:
        return "A secret comes to light."
    text = next((s.text for s in npc.secrets if s.id == e.secret_id and s.revealed), "")
    return f"{npc.name} shares a secret: {text}" if text else f"{npc.name} shares a secret."


def _inventory(state: GameState, e: ev.InventoryChanged) -> str:
    who, item = _who(state, e.creature_id), display_name(e.item).lower()
    return f"{who} receives {item}." if e.delta > 0 else f"{who} parts with {item}."


def _npc(state: GameState, e: we.NpcIntroduced) -> str | None:
    if e.npc.node_id is None or e.npc.node_id != state.world.current_node:
        return None
    role = f", {e.npc.role}," if e.npc.role else ""
    return f"{e.npc.name}{role} is here."


def _withdrew(state: GameState, e: CombatantWithdrew) -> str:
    who = _who(state, e.creature_id)
    return f"{who} flees the fight." if e.reason is WithdrawReason.FLED else f"{who} surrenders."


def _attitude(state: GameState, e: we.AttitudeChanged) -> str:
    who = _who(state, e.npc_id)
    return f"{who} turns hostile." if e.hostile else f"{who}'s manner toward you shifts."


_LINES: dict[type[Any], Callable[[GameState, Any], str | None]] = {
    ev.CheckResolved: _check,
    AttackRolled: _attack,
    ev.HpChanged: _hp,
    ev.ConditionApplied: lambda s, e: f"{_who(s, e.creature_id)} is now {e.condition.name}.",
    ev.ConditionRemoved: lambda s, e: f"{_who(s, e.creature_id)} is no longer {e.name}.",
    ev.CreatureDied: lambda s, e: f"{_who(s, e.creature_id)} falls and does not rise again.",
    ev.Stabilized: lambda s, e: f"{_who(s, e.creature_id)} steadies, no longer slipping away.",
    CreatureRevived: lambda s, e: f"{_who(s, e.creature_id)} gasps back to life.",
    SpellCast: lambda s, e: f"{_who(s, e.caster_id)} casts {display_name(e.spell_id)}.",
    MonsterActionUsed: lambda s, e: f"{_who(s, e.creature_id)} unleashes {e.name}.",
    FeatureUsed: lambda s, e: f"{_who(s, e.creature_id)} uses {e.name}.",
    CombatantMoved: _moved,
    CombatantWithdrew: _withdrew,
    EncounterStarted: lambda s, e: "Weapons are drawn: a fight breaks out!",
    EncounterEnded: lambda s, e: _ENDINGS[e.status],
    ev.XpGained: lambda s, e: "The party grows more experienced.",
    ev.LevelGained: lambda s, e: f"{_who(s, e.creature_id)} feels new power awaken.",
    ev.InventoryChanged: _inventory,
    ev.ShortRestTaken: lambda s, e: "You rest a while and catch your breath.",
    ev.LongRestTaken: lambda s, e: "You make camp, and morning finds you refreshed.",
    we.NpcIntroduced: _npc,
    we.FeatureIntroduced: _feature,
    we.FeatureDiscovered: _discovered,
    we.AttitudeChanged: _attitude,
    we.SecretRevealed: _secret,
    we.PartyMoved: lambda s, e: f"You travel on to {node_display_name(s, e.to_node)}.",
    we.QuestUpdated: lambda s, e: _QUESTS[e.quest.state].format(title=e.quest.title),
    we.ShopOpened: lambda s, e: f"{_who(s, e.npc_id)} lays out their wares.",
    we.ItemPlaced: lambda s, e: None if e.item.hidden else f"{e.item.name} lies here.",
    we.HostileActPending: lambda s, e: "You stand on the brink of violence.",
    **CAMPAIGN_TEMPLATE_LINES,
}


def template_line(state: GameState, event: ev.AnyEvent) -> str | None:
    render = _LINES.get(type(event))
    return render(state, event) if render is not None else None


def template_narration(
    events: Sequence[ev.AnyEvent], state: GameState, notice: str | None = None
) -> list[str]:
    lines: list[str] = []
    for event in events:
        line = template_line(state, event)
        if line and line not in lines:
            lines.append(line)
    if lines:
        return lines
    return [notice or QUIET_LINE]
