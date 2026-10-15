"""THE public projection of the event log (SPEC 9, 10, 12): what every seat may read.

`public_line(state, event)` decides, with the state right AFTER the event was applied, whether
an event is public and returns its player-visible line (else None):
1. an event about an NPC (`npc_id` or an embedded `npc`) is public only while that NPC is in the
   party's current place: the campaign cast and the bosses are introduced up front, so a boss
   is named only once the party stands where the boss is (met);
2. the line is `dm.event_text.event_line`, which never renders hidden features, motives,
   unrevealed secrets or campaign setup; no line means not public;
3. defence in depth: a line containing any private text of the current state (an NPC motive,
   an unrevealed secret, the name or description of a hidden undiscovered feature) is dropped.
Non-public events are never sent: their seq is simply skipped (the snapshot seq still covers
them). `private_texts` + `leaks` also filter the fact lines of the snapshot (`views`).

`PublicFeed` keeps the public `EventMsg`s (live broadcast and seq catch-up), the recent
narration, the recent typed actions (M22.1: an `ActionDeclared` is projected as a
`PlayerActionMsg`, a player's own words are always public) and the recent dice rolls
(`dice_view`: every roll is public; M9.4 restores the dice panel on reconnect), and builds the
`StoryHistory` a (re)connecting client gets after its snapshot. A restored table rebuilds it by
replaying the log (`PublicFeed.rebuild`; narration then comes from the logged
`NarrationRecorded` events).

Public API: `private_texts`, `leaks`, `public_line`, `dice_view`, `action_entry`, `PublicFeed`.
"""

from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass, field

from aidm.dm.event_text import event_line
from aidm.dm.narration_templates import template_line
from aidm.dm.wording import check_subject
from aidm.models.checks import CheckKind
from aidm.models.combat_events import AttackRolled
from aidm.models.dice import AdvState, D20Roll
from aidm.models.events import AnyEvent, CheckResolved, DeathSaveRolled, DiceRolled, LoggedEvent
from aidm.models.narration import NarrationTone
from aidm.models.protocol_server import EventMsg, PlayerActionMsg, StoryHistory
from aidm.models.protocol_views import DiceView, RollEntry, StoryEntry
from aidm.models.quest_events import QuestAsked
from aidm.models.state import GameState
from aidm.models.world import WorldNpc
from aidm.models.world_events import ActionDeclared, NarrationRecorded
from aidm.session.reducer import apply as reduce

MIN_PRIVATE_CHARS = 4
MAX_NARRATIONS = 24
MAX_ACTIONS = 24
HISTORY_EVENTS = 60
HISTORY_MAX = 80
MAX_ROLLS = 12


def private_texts(state: GameState) -> list[str]:
    """Lower-cased texts no client may read in the current state."""
    texts: list[str] = []
    for npc in state.world.npcs.values():
        texts.append(npc.motive)
        texts += [s.text for s in npc.secrets if not s.revealed]
    for feature in state.world.features.values():
        if feature.hidden and not feature.discovered:
            texts += [feature.name, feature.description]
    return [t.strip().lower() for t in texts if len(t.strip()) >= MIN_PRIVATE_CHARS]


def leaks(text: str, private: Sequence[str]) -> bool:
    lower = text.lower()
    return any(p in lower for p in private)


def _npc_ids(event: AnyEvent) -> list[str]:
    ids: list[str] = []
    npc_id = getattr(event, "npc_id", None)
    if isinstance(npc_id, str):
        ids.append(npc_id)
    npc = getattr(event, "npc", None)
    if isinstance(npc, WorldNpc):
        ids.append(npc.id)
    return ids


def _present(state: GameState, npc_id: str) -> bool:
    npc = state.world.npcs.get(npc_id)
    if npc is None:
        return True
    return npc.node_id is not None and npc.node_id == state.world.current_node


def public_line(state: GameState, event: AnyEvent) -> str | None:
    if not all(_present(state, npc_id) for npc_id in _npc_ids(event)):
        return None
    # the ask is told to the narrator with instructions; the table sees the plain giver line
    line = (
        template_line(state, event) if isinstance(event, QuestAsked) else event_line(state, event)
    )
    if not line or leaks(line, private_texts(state)):
        return None
    return line


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


def dice_view(event: AnyEvent) -> DiceView | None:
    if isinstance(event, AttackRolled):
        view = _d20(event.attacker_id, event.attack, event.roll, event.target_ac)
        return view.model_copy(update={"success": event.hit, "crit": event.crit})
    if isinstance(event, CheckResolved):
        r = event.result
        label = check_subject(r) + (" save" if r.kind is CheckKind.SAVE else "")
        view = _d20(event.creature_id, label, r.roll, r.dc)
        return view.model_copy(update={"success": r.success})
    if isinstance(event, DeathSaveRolled):
        view = _d20(event.creature_id, "death save", event.roll, 10)
        return view.model_copy(update={"success": event.roll.total >= 10})
    if isinstance(event, DiceRolled):
        r = event.roll
        return DiceView(
            roller_id=event.roller_id,
            label=event.label,
            expression=r.expression,
            rolls=tuple(d.value for d in r.dice if d.kept),
            modifier=r.modifier,
            total=r.total,
        )
    return None


def action_entry(state: GameState, seq: int, event: ActionDeclared) -> StoryEntry:
    """The story line of a typed action: the player's words, who typed them, for which hero."""
    hero = state.creatures.get(event.creature_id)
    return StoryEntry(
        kind="action",
        seq=seq,
        text=event.text,
        creature_id=event.creature_id,
        player_name=event.player_name,
        hero_name=hero.name if hero is not None else "",
    )


@dataclass
class PublicFeed:
    events: list[EventMsg] = field(default_factory=list[EventMsg])
    narrations: deque[StoryEntry] = field(
        default_factory=lambda: deque[StoryEntry](maxlen=MAX_NARRATIONS)
    )
    rolls: deque[RollEntry] = field(default_factory=lambda: deque[RollEntry](maxlen=MAX_ROLLS))
    actions: deque[StoryEntry] = field(
        default_factory=lambda: deque[StoryEntry](maxlen=MAX_ACTIONS)
    )

    def add_event(
        self, state: GameState, seq: int, event: AnyEvent
    ) -> EventMsg | PlayerActionMsg | None:
        """Project one applied event; returns the message to broadcast, or None (private)."""
        if isinstance(event, ActionDeclared):
            entry = action_entry(state, seq, event)
            self.actions.append(entry)
            return PlayerActionMsg(entry=entry)
        line = public_line(state, event)
        if line is None:
            return None
        msg = EventMsg(seq=seq, kind=event.type, line=line)
        self.events.append(msg)
        return msg

    def add_roll(self, seq: int, event: AnyEvent) -> DiceView | None:
        """Keep the dice of one applied event (every roll is public); returns its view."""
        dice = dice_view(event)
        if dice is not None:
            self.rolls.append(RollEntry(seq=seq, dice=dice))
        return dice

    def add_narration(self, nid: str, text: str, tone: NarrationTone | None, seq: int) -> None:
        clean = text.strip()
        if clean:
            entry = StoryEntry(kind="narration", seq=seq, text=clean, id=nid, tone=tone)
            self.narrations.append(entry)

    def since(self, seq: int, limit: int) -> list[EventMsg]:
        return [m for m in self.events if m.seq >= seq][-limit:]

    def history(self) -> StoryHistory:
        events = [
            StoryEntry(kind="event", seq=m.seq, text=m.line, event_kind=m.kind)
            for m in self.events[-HISTORY_EVENTS:]
        ]
        merged = sorted(
            [*self.narrations, *events, *self.actions], key=lambda e: (e.seq, e.kind != "narration")
        )
        return StoryHistory(entries=tuple(merged[-HISTORY_MAX:]), dice=tuple(self.rolls))

    @classmethod
    def rebuild(cls, initial: GameState, log: Sequence[LoggedEvent]) -> "PublicFeed":
        """Replay `log` from `initial` and project every event as it was when applied."""
        feed = cls()
        state = initial.model_copy(deep=True)
        for entry in log:
            reduce(state, entry.event)
            feed.add_roll(entry.seq, entry.event)
            if isinstance(entry.event, NarrationRecorded):
                feed.add_narration(f"h{entry.seq}", entry.event.text, None, entry.seq)
            else:
                feed.add_event(state, entry.seq, entry.event)
        return feed
