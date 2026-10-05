"""Public views carried by server messages (SPEC 10, 12): what a client may see of the game.

Built by `aidm.session.views` from `GameState`; nothing here holds NPC motives, unrevealed
secrets, raw attitude scores or hidden features (NPCs are `PublicNpcView`, built only by
`aidm.rules.social.public_npc_view`).

Public API:
- `TablePhase`: lobby / generating / play / ended.
- `PlayerInfo(id, name, is_host, connected, creature_id)`: one seat at the table.
- `PublicCreature`: a party member or combatant (hp, ac, conditions, death saves, level/class
  for PCs).
- `PublicExit`, `PublicFeature`, `PublicScene`: the current place, its exits, visible features,
  visible items and present NPCs.
- `MapNode`, `PublicMap`: the region graph with fog (visited nodes and their neighbours).
- `PublicQuest`; `PublicOffer` (a pending encounter offer: foes, boss, options).
- `CombatToken`, `PublicCombat`: zones, tokens, initiative, the active creature and its
  economy pips.
- `QueueEntry`, `VoteKind`, `VoteView`: the exploration queue and the open ready vote.
- `PublicState`: the full snapshot payload.
- `DiceView`: one visible roll for the dice tray (d20 tests, attacks, death saves, damage dice).
- `StoryEntry`: one narration or public event line of the story history (reconnect, reload).
- `StockLine`: one shop line (item id, name, price).
"""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from aidm.models.campaign_state import OfferChoice
from aidm.models.dice import AdvState
from aidm.models.encounter import Side, TurnEconomy
from aidm.models.narration import NarrationTone
from aidm.models.world import PublicNpcView
from aidm.models.zones import Zone, ZoneEdge


class _View(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class TablePhase(StrEnum):
    LOBBY = "lobby"
    GENERATING = "generating"
    PLAY = "play"
    ENDED = "ended"


class PlayerInfo(_View):
    id: str
    name: str
    is_host: bool = False
    connected: bool = True
    creature_id: str | None = None


class PublicCreature(_View):
    id: str
    name: str
    kind: str
    hp: int
    max_hp: int
    temp_hp: int = 0
    ac: int = 10
    conditions: tuple[str, ...] = ()
    dead: bool = False
    dying: bool = False
    stable: bool = False
    death_save_successes: int = Field(default=0, ge=0, le=3)
    death_save_failures: int = Field(default=0, ge=0, le=3)
    level: int | None = None
    race: str | None = None
    class_index: str | None = None
    portrait_id: str = ""
    gold: int | None = None
    xp: int | None = None


class PublicExit(_View):
    node_id: str
    name: str
    locked: bool = False
    visited: bool = False


class PublicFeature(_View):
    id: str
    kind: str
    name: str
    description: str = ""


class PublicScene(_View):
    node_id: str
    name: str
    description: str = ""
    exits: tuple[PublicExit, ...] = ()
    npcs: tuple[PublicNpcView, ...] = ()
    features: tuple[PublicFeature, ...] = ()
    items: tuple[str, ...] = ()
    shop_npc_id: str | None = None


class MapNode(_View):
    id: str
    name: str
    visited: bool = False
    locked: bool = False
    current: bool = False


class PublicMap(_View):
    nodes: tuple[MapNode, ...] = ()
    edges: tuple[tuple[str, str], ...] = ()


class PublicQuest(_View):
    id: str
    title: str
    state: str


class PublicOffer(_View):
    id: str
    node_id: str
    foes: tuple[str, ...] = ()
    boss_name: str | None = None
    difficulty: str = ""
    options: tuple[OfferChoice, ...] = ()


class CombatToken(_View):
    creature_id: str
    name: str
    side: Side
    zone_id: str
    hp: int
    max_hp: int
    conditions: tuple[str, ...] = ()
    dead: bool = False
    withdrawn: bool = False


class PublicCombat(_View):
    encounter_id: str
    round: int
    zones: tuple[Zone, ...] = ()
    edges: tuple[ZoneEdge, ...] = ()
    tokens: tuple[CombatToken, ...] = ()
    initiative: tuple[str, ...] = ()
    active_id: str | None = None
    economy: TurnEconomy | None = None


class QueueEntry(_View):
    player_id: str
    creature_id: str
    text: str


class VoteKind(StrEnum):
    TRAVEL = "travel"
    SHORT_REST = "short_rest"
    LONG_REST = "long_rest"
    SHOP = "shop"


class VoteView(_View):
    vote_id: str
    kind: VoteKind
    detail: str = ""
    proposer_id: str
    voters: tuple[str, ...] = ()
    ready: tuple[str, ...] = ()
    declined: tuple[str, ...] = ()
    seconds: float = 0.0


class PublicState(_View):
    campaign_id: str
    phase: TablePhase = TablePhase.LOBBY
    paused: bool = False
    players: tuple[PlayerInfo, ...] = ()
    party: tuple[PublicCreature, ...] = ()
    scene: PublicScene | None = None
    map: PublicMap | None = None
    quests: tuple[PublicQuest, ...] = ()
    facts: tuple[str, ...] = ()
    combat: PublicCombat | None = None
    offer: PublicOffer | None = None
    queue: tuple[QueueEntry, ...] = ()
    resolving: QueueEntry | None = None
    vote: VoteView | None = None
    campaign_title: str = ""
    region_tier: int = 1
    camp_supplies: int = 0
    complete: bool = False
    epilogue: str | None = None
    tts_enabled: bool = False
    monster_hp: float = 1.0
    monster_damage: float = 1.0


class DiceView(_View):
    roller_id: str | None = None
    label: str = ""
    expression: str = "1d20"
    rolls: tuple[int, ...] = ()
    adv: AdvState = AdvState.NORMAL
    modifier: int = 0
    total: int = 0
    target: int | None = Field(default=None, description="DC or AC when the roll is a test")
    success: bool | None = None
    crit: bool = False


class StoryEntry(_View):
    """One line of the story history: a told narration (id, tone) or a public event line."""

    kind: Literal["narration", "event"]
    seq: int = Field(ge=0, description="event-log position the entry follows")
    text: str
    id: str = ""
    tone: NarrationTone | None = None
    event_kind: str = ""


class StockLine(_View):
    item_id: str
    name: str
    price_gp: int = Field(ge=0)
