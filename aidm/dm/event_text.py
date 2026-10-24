"""Engine events as short, authoritative plain-language lines (SPEC 6.4 section 6, 6.8).

The context builder lists the recent events with these lines so the narrator describes what the
engine resolved; the template narration (M4.5) reuses them when no model is available. Lines are
ASCII, name creatures by their display name and NEVER leak private data: an introduced hidden
feature, an NPC motive or an unrevealed secret is never rendered, and an introduced NPC is named
only when in the party's current place (the campaign cast is introduced up front). Pure
bookkeeping events (turn economy, resources, dice already shown in a check) render as None.
Conditions read by display name in plain words (`aidm.dm.condition_text`, M20.7). Gear lines
(light lit/put out, a gear use, a lock opened, the fight start a light gave away) come from
`aidm.dm.item_text` (M27.5).
An impossible action (M30.1) reads "<hero> cannot do that: <why>." (`aidm.dm.impossible_text`).
A spell cast at the scene (M30.2b) reads "<hero> casts <spell> (outside a fight: <what it cannot
do>)." with a model-only note (`aidm.dm.cast_text`); other casts render None (their effects tell).

Lines are facts only, since the public feed shows them too; the instructions that go with some
of them (do not choose the finale for the party, tell no new deed for a step) are
`event_notes(state, events)`, for the narrator alone (M29.5c G36).

Public API: `event_line(state, event) -> str | None`, `event_lines(state, events) -> list[str]`,
`event_notes(state, events) -> list[str]`.
"""

from collections.abc import Callable, Sequence
from typing import Any

from aidm.dm.campaign_text import CAMPAIGN_EVENT_LINES, CAMPAIGN_EVENT_NOTES
from aidm.dm.cast_text import CAST_EVENT_LINES, CAST_EVENT_NOTES
from aidm.dm.condition_text import applied_line, removed_line
from aidm.dm.entities import display_name
from aidm.dm.impossible_text import IMPOSSIBLE_EVENT_LINES, IMPOSSIBLE_EVENT_NOTES
from aidm.dm.item_text import ITEM_EVENT_LINES
from aidm.dm.quest_text import QUEST_EVENT_LINES, QUEST_EVENT_NOTES
from aidm.dm.wording import attack_label, check_subject, with_article
from aidm.models import events as ev
from aidm.models import world_events as we
from aidm.models.combat_events import AttackRolled, CombatantMoved, FeatureUsed
from aidm.models.encounter_events import CombatantWithdrew, EncounterEnded
from aidm.models.scribe import CharacterRewritten
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


def _damage_modifiers(state: GameState, e: ev.DamageTaken) -> str | None:
    """M31.1e: say when immunity, resistance or vulnerability changed a damage packet (the facts
    are the packet's rolled and taken numbers: 0 taken, half rounded down, or double)."""
    who = _who(state, e.creature_id)
    bits: list[str] = []
    for p in e.parts:
        count = f"{p.rolled} rolled, {p.taken} taken"
        kind = p.damage_type.value
        if p.rolled > 1 and p.taken == 0:
            bits.append(f"{who} is immune to {kind} damage ({count})")
        elif p.rolled > 0 and p.taken == p.rolled // 2:
            bits.append(f"{who} resists {kind} damage ({count})")
        elif p.taken > p.rolled:
            bits.append(f"{who} is vulnerable to {kind} damage ({count})")
    return "; ".join(bits) + "." if bits else None


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
    """M29.5c G7: the line names the weapon, so the narrator cannot swap a crossbow for a mace."""
    verdict = "critically hits" if e.crit else ("hits" if e.hit else "misses")
    weapon = with_article(attack_label(e.attack))
    who, whom = _who(state, e.attacker_id), _who(state, e.target_id)
    return f"{who} attacks {whom} with {weapon} and {verdict}."


def _item_found(state: GameState, e: we.ItemDiscovered) -> str:
    item = state.world.items.get(e.item_id)
    name = item.name if item is not None else "something hidden"
    # M29.5b G19: a hidden thing is found against its OWN DC, so the search may find it while
    # the check missed its stated goal; the model is told so, and that it is an object.
    # M31.1c V17: found is not taken (round 4: searched things told tucked away)
    return (
        f"{_who(state, e.creature_id)}'s search turns up the {name}, an object that lies here"
        " ready to pick up (found even if the check missed its own goal); it still lies where"
        " it was found: nobody has picked it up, pocketed it or carries it yet."
    )


def _attitude(state: GameState, e: we.AttitudeChanged) -> str:
    who = _who(state, e.npc_id)
    if e.turned:  # M32.1a X7: a change while already hostile is no turn
        return f"{who} turned hostile."
    if e.gift:  # M31.1c V17: the gift went to THIS person (round 4: told as to the peddler)
        return f"{who} received the gift ({display_name(e.gift)}) and holds it now; nobody else."
    return f"{who}'s attitude changed."


def _kept(state: GameState, e: we.KeepsakeGained) -> str:
    who = _who(state, e.creature_id)
    return f"{who} keeps the {e.keepsake.name}: it is in {who}'s hands now."


_LINES: dict[type[Any], Callable[[GameState, Any], str | None]] = {
    ev.CheckResolved: _check,
    ev.HpChanged: _hp,
    ev.DamageTaken: _damage_modifiers,
    ev.ConditionApplied: lambda s, e: applied_line(_who(s, e.creature_id), e.condition.name),
    ev.ConditionRemoved: lambda s, e: removed_line(_who(s, e.creature_id), e.name),
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
    EncounterEnded: _encounter_ended,
    CombatantWithdrew: lambda s, e: f"{_who(s, e.creature_id)} {e.reason.value}.",
    AttackRolled: _attack,
    CombatantMoved: lambda s, e: None,
    FeatureUsed: lambda s, e: f"{_who(s, e.creature_id)} uses {e.name}.",
    we.NpcIntroduced: _npc,
    we.FeatureIntroduced: _feature,
    we.FeatureDiscovered: _discovered,
    we.AttitudeChanged: _attitude,
    we.SecretRevealed: _secret,
    we.PartyMoved: lambda s, e: f"The party travelled to {node_display_name(s, e.to_node)}.",
    we.FactRecorded: lambda s, e: None,
    we.ShopOpened: lambda s, e: f"{_who(s, e.npc_id)} opened their shop.",
    we.ItemPlaced: lambda s, e: (
        None
        if e.item.hidden or e.item.node_id != s.world.current_node
        else f"{e.item.name} lies here."
    ),
    we.ItemDiscovered: _item_found,
    we.ItemRemoved: lambda s, e: None,
    we.KeepsakeGained: _kept,
    CharacterRewritten: lambda s, e: f"The Scribe rewrites {_who(s, e.target_id)} into the story.",
    **CAMPAIGN_EVENT_LINES,
    **QUEST_EVENT_LINES,
    **ITEM_EVENT_LINES,
    **IMPOSSIBLE_EVENT_LINES,
    **CAST_EVENT_LINES,
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


_NOTES: dict[type[Any], Callable[[GameState, Any], str | None]] = {
    we.KeepsakeGained: lambda s, e: (  # M31.1c V19: a keepsake hand-over is always told
        f"Tell the {e.keepsake.name} reaching {_who(s, e.creature_id)} in this narration."
    ),
    **CAMPAIGN_EVENT_NOTES,
    **QUEST_EVENT_NOTES,
    **IMPOSSIBLE_EVENT_NOTES,
    **CAST_EVENT_NOTES,
}


def event_notes(state: GameState, events: Sequence[ev.AnyEvent]) -> list[str]:
    """M29.5c G36: the model-only instructions that go with these events (never public)."""
    notes: list[str] = []
    for event in events:
        render = _NOTES.get(type(event))
        note = render(state, event) if render is not None else None
        if note and note not in notes:
            notes.append(note)
    return notes
