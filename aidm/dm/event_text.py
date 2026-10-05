"""Engine events as short, authoritative plain-language lines (SPEC 6.4 section 6, 6.8).

The context builder lists the recent events with these lines so the narrator describes what the
engine resolved; the template narration (M4.5) reuses them when no model is available. Lines are
ASCII, name creatures by their display name and NEVER leak private data: an introduced hidden
feature, an NPC motive or an unrevealed secret is never rendered, and an introduced NPC is named
only when in the party's current place (the campaign cast is introduced up front). Pure
bookkeeping events (turn economy, resources, dice already shown in a check) render as None.

Public API: `event_line(state, event) -> str | None`, `event_lines(state, events) -> list[str]`.
"""

from collections.abc import Callable, Sequence
from typing import Any

from aidm.dm.campaign_text import CAMPAIGN_EVENT_LINES
from aidm.dm.entities import display_name
from aidm.dm.wording import check_subject, with_article
from aidm.models import events as ev
from aidm.models import world_events as we
from aidm.models.combat_events import AttackRolled, CombatantMoved, FeatureUsed, SpellCast
from aidm.models.encounter_events import CombatantWithdrew, EncounterEnded, EncounterStarted
from aidm.models.state import GameState
from aidm.rules.scene import node_display_name


def _who(state: GameState, creature_id: str | None) -> str:
    if creature_id is None:
        return "someone"
    creature = state.creatures.get(creature_id)
    if creature is not None:
        return creature.name
    npc = state.world.npcs.get(creature_id)
    return npc.name if npc is not None else display_name(creature_id)


def _check(state: GameState, e: ev.CheckResolved) -> str:
    r = e.result
    kind = "save" if r.kind.value == "save" else "check"
    verdict = "passed" if r.success else "failed"
    test = with_article(f"{check_subject(r)} {kind}")
    return f"{_who(state, e.creature_id)} {verdict} {test} ({r.roll.total} vs DC {r.dc})."


def _npc(state: GameState, e: we.NpcIntroduced) -> str | None:
    """Only an NPC in the party's current place is 'here'; the cast elsewhere stays unnamed."""
    if e.npc.node_id is None or e.npc.node_id != state.world.current_node:
        return None
    return f"{e.npc.name} ({e.npc.role or 'stranger'}) is here."


def _hp(state: GameState, e: ev.HpChanged) -> str:
    verb = "regains" if e.delta > 0 else "loses"
    return f"{_who(state, e.creature_id)} {verb} {abs(e.delta)} HP (now {e.new_hp})."


def _secret(state: GameState, e: we.SecretRevealed) -> str:
    npc = state.world.npcs.get(e.npc_id)
    if npc is None:
        return "A secret was revealed."
    text = next((s.text for s in npc.secrets if s.id == e.secret_id and s.revealed), "")
    return f"{npc.name} revealed a secret: {text}" if text else f"{npc.name} revealed a secret."


def _feature(state: GameState, e: we.FeatureIntroduced) -> str | None:
    if e.feature.hidden:
        return None
    return f"There is {e.feature.kind.value} here: {e.feature.name}."


def _discovered(state: GameState, e: we.FeatureDiscovered) -> str:
    feature = state.world.features.get(e.feature_id)
    name = feature.name if feature is not None else display_name(e.feature_id)
    return f"{_who(state, e.creature_id)} discovered {name}."


def _encounter_ended(state: GameState, e: EncounterEnded) -> str:
    xp = f" Each survivor gains {e.xp_each} XP." if e.xp_each else ""
    return f"The fight is over ({e.status.value}).{xp}"


def _attack(state: GameState, e: AttackRolled) -> str:
    verdict = "critically hits" if e.crit else ("hits" if e.hit else "misses")
    return f"{_who(state, e.attacker_id)} attacks {_who(state, e.target_id)} and {verdict}."


_LINES: dict[type[Any], Callable[[GameState, Any], str | None]] = {
    ev.CheckResolved: _check,
    ev.HpChanged: _hp,
    ev.ConditionApplied: lambda s, e: f"{_who(s, e.creature_id)} is now {e.condition.name}.",
    ev.ConditionRemoved: lambda s, e: f"{_who(s, e.creature_id)} is no longer {e.name}.",
    ev.CreatureDied: lambda s, e: f"{_who(s, e.creature_id)} is dead.",
    ev.Stabilized: lambda s, e: f"{_who(s, e.creature_id)} is stable.",
    ev.XpGained: lambda s, e: f"{_who(s, e.creature_id)} gains {e.amount} XP.",
    ev.LevelGained: lambda s, e: f"{_who(s, e.creature_id)} reached level {e.pc.level}.",
    ev.GoldChanged: lambda s, e: f"{_who(s, e.creature_id)} now has {e.gold} gold.",
    ev.InventoryChanged: lambda s, e: (
        f"{_who(s, e.creature_id)} {'gains' if e.delta > 0 else 'loses'} {abs(e.delta)} x "
        f"{display_name(e.item)}."
    ),
    ev.ShortRestTaken: lambda s, e: "The party took a short rest.",
    ev.LongRestTaken: lambda s, e: "The party took a long rest and is refreshed.",
    EncounterStarted: lambda s, e: "A fight breaks out.",
    EncounterEnded: _encounter_ended,
    CombatantWithdrew: lambda s, e: f"{_who(s, e.creature_id)} {e.reason.value}.",
    AttackRolled: _attack,
    CombatantMoved: lambda s, e: None,
    SpellCast: lambda s, e: None,
    FeatureUsed: lambda s, e: f"{_who(s, e.creature_id)} uses {e.name}.",
    we.NpcIntroduced: _npc,
    we.FeatureIntroduced: _feature,
    we.FeatureDiscovered: _discovered,
    we.AttitudeChanged: lambda s, e: (
        f"{_who(s, e.npc_id)} turned hostile."
        if e.hostile
        else f"{_who(s, e.npc_id)}'s attitude changed."
    ),
    we.SecretRevealed: _secret,
    we.PartyMoved: lambda s, e: f"The party travelled to {node_display_name(s, e.to_node)}.",
    we.QuestUpdated: lambda s, e: f"Quest '{e.quest.title}' is now {e.quest.state.value}.",
    we.FactRecorded: lambda s, e: None,
    we.ShopOpened: lambda s, e: f"{_who(s, e.npc_id)} opened their shop.",
    we.ItemPlaced: lambda s, e: None if e.item.hidden else f"{e.item.name} lies here.",
    we.ItemRemoved: lambda s, e: None,
    **CAMPAIGN_EVENT_LINES,
}


def event_line(state: GameState, event: ev.AnyEvent) -> str | None:
    render = _LINES.get(type(event))
    return render(state, event) if render is not None else None


def event_lines(state: GameState, events: Sequence[ev.AnyEvent]) -> list[str]:
    out: list[str] = []
    for event in events:
        line = event_line(state, event)
        if line:
            out.append(line)
    return out
