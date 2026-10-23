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
- `PublicQuest` (title, state, giver and objective once taken on); `PublicSummary` (scene
  summaries); `PublicOffer` (a pending encounter offer: foes, boss, options, the sure ones);
  `PublicQuestOffer` (M23.4: the giver's open question, the phones' Accept / Not now card).
- `PublicZone`, `CombatToken`, `PublicCombat`: zones (with terrain), tokens (monster index for
  art), initiative, the active creature and its economy pips.
- `QueueEntry`, `VoteKind`, `VoteView`: the exploration queue and the open ready vote.
- `PublicState`: the full snapshot payload (M13.1: `scribe`, `aidm.models.scribe.ScribeView`).
- `DiceView`: one visible roll for the dice tray (d20 tests, attacks, death saves, damage dice).
  M26.2 (all optional): `kind`, `target_id` (an attack's target, the creature damage or healing
  lands on), `source_id` (who forced a save), `parts` (named bonuses summing to `modifier`),
  `adv_why` (advantage/disadvantage reasons), `difficulty` (the DC tier word, else None).
- `StoryEntry`: one narration or public event line of the story history (reconnect, reload).
- `StockLine`: one shop line (item id, name, price, category, camp supplies it adds).
- `AudioSettings` (M11.2): the shared screen's narration/music volume and mutes (audio remote).
- `FloorSeat`, `FloorView` (M11.2): who holds the floor, the waiting queue in order and who is
  typing, by player and hero name (the screen's "Sam is typing..." line).
"""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from aidm.models.campaign_state import OfferChoice
from aidm.models.dice import AdvState, RollKind, RollPart
from aidm.models.encounter import Side, TurnEconomy
from aidm.models.narration import NarrationTone
from aidm.models.scribe import ScribeView
from aidm.models.world import PublicNpcView
from aidm.models.zones import CoverLevel, ZoneEdge, ZoneSurface


class _View(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class TablePhase(StrEnum):
    LOBBY = "lobby"
    GENERATING = "generating"
    PLAY = "play"
    ENDED = "ended"
    DEFEATED = "defeated"  # M11.1: the party was wiped; only the defeat choices remain


class PlayerInfo(_View):
    id: str
    name: str
    is_host: bool = False
    connected: bool = True
    creature_id: str | None = None


class PublicBoon(_View):
    """A gear boon on a hero (M27.8): the item's name and what it helps (skills, saves)."""

    name: str
    helps: tuple[str, ...] = ()


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
    darkvision: int = 0  # M27.8: feet, 0 = none (the eye icon)
    light: str = ""  # M27.8: short name of the lit light carried ("Torch"), else ""
    boons: tuple[PublicBoon, ...] = ()  # M27.8: the active gear boons


class PublicExit(_View):
    node_id: str
    name: str
    locked: bool = False
    visited: bool = False
    locked_reason: str = ""  # M23.8: why a locked way is shut (`rules.gateway_lock`)


class PublicFeature(_View):
    id: str
    kind: str
    name: str
    description: str = ""
    locked: str = ""  # M27.8: the lock's tier (easy, medium, hard...) while shut, else ""


class PublicScene(_View):
    """The party's place. `terrain` is its first terrain tag (art key `region_banner.<terrain>`,
    the phone's Play picture and the screen header, M24), "" when unknown."""

    node_id: str
    name: str
    description: str = ""
    terrain: str = ""
    exits: tuple[PublicExit, ...] = ()
    npcs: tuple[PublicNpcView, ...] = ()
    features: tuple[PublicFeature, ...] = ()
    items: tuple[str, ...] = ()
    shop_npc_id: str | None = None
    shopkeepers: tuple[str, ...] = ()
    dark: bool = False  # M27.8: the place is dark by terrain (`rules.light.node_dark`)
    lit: str = ""  # M27.11: short name of the light a hero carries here (dark place only)


class MapNode(_View):
    id: str
    name: str
    visited: bool = False
    locked: bool = False
    current: bool = False


class PublicMap(_View):
    nodes: tuple[MapNode, ...] = ()
    edges: tuple[tuple[str, str], ...] = ()


class PublicRoute(_View):
    """A known way through a main quest (M23.7): only the steps already done are named."""

    id: str
    title: str
    kind: str = ""
    steps_done: tuple[str, ...] = ()
    done: bool = False


class PublicQuest(_View):
    """A quest line (M23.7). Only the texts of DONE steps are sent, never the next one (that is
    the answer to "What now?"). `closed_reason` is "", "left_behind" or "withdrawn"; `routes` are
    the known routes of a main quest."""

    id: str
    title: str
    state: str
    kind: str = "side"
    giver: str = ""
    objective: str = ""
    steps_done: tuple[str, ...] = ()
    routes: tuple[PublicRoute, ...] = ()
    log: tuple[str, ...] = ()
    closed_reason: str = ""


class PublicSummary(_View):
    title: str = ""
    text: str


class PublicOffer(_View):
    id: str
    node_id: str
    foes: tuple[str, ...] = ()
    boss_name: str | None = None
    difficulty: str = ""
    options: tuple[OfferChoice, ...] = ()
    sure: tuple[OfferChoice, ...] = ()  # M29.7c R14: answers that surely hold (a done Peace route)


class PublicQuestOffer(_View):
    quest_id: str
    giver: str
    title: str
    objective: str = ""


class PublicFinaleOption(_View):
    id: str
    title: str


class PublicFinale(_View):
    """M23.9: the plan's finale question. `chosen` is None while the party must still choose
    (the card shows); afterwards it is the chosen ending's id and `ending` its text."""

    question: str
    options: tuple[PublicFinaleOption, ...] = ()
    chosen: str | None = None
    ending: str = ""


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
    monster_index: str | None = None


class PublicZone(_View):
    """A battlefield zone for the zone card; `terrain` is the terrain template (art key
    `zone_card.<terrain>`) the zone came from, "" when unknown.
    `difficult` is the base terrain flag; `rough` is the effective one (terrain or a difficult
    surface) that doubles the cost of entering the zone. `q`, `r` are its axial hex on the battle
    map (M21: touching hexes are linked zones; `aidm.rules.hex_layout`)."""

    id: str
    name: str
    terrain: str = ""
    tags: tuple[str, ...] = ()
    distance_label: str = ""
    cover: CoverLevel = CoverLevel.NONE
    high_ground: bool = False
    difficult: bool = False
    rough: bool = False
    surfaces: tuple[ZoneSurface, ...] = ()
    q: int = 0
    r: int = 0
    dark: bool = False  # M27.8: the place is dark (a zone is dimmed unless `lit`)
    lit: bool = True  # M27.8: light reaches the zone (`rules.light.lit_zones`)
    lit_by: tuple[str, ...] = ()  # M27.8: bearers whose light covers the zone


class PublicCombat(_View):
    encounter_id: str
    round: int
    zones: tuple[PublicZone, ...] = ()
    edges: tuple[ZoneEdge, ...] = ()
    tokens: tuple[CombatToken, ...] = ()
    initiative: tuple[str, ...] = ()
    active_id: str | None = None
    economy: TurnEconomy | None = None
    turn_of: str | None = None  # M20.3: whose turn it is, or was until the next one begins


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


class AudioSettings(_View):
    """The shared screen's audio (M11.2): set by any seated player, last write wins."""

    narration_volume: int = Field(default=80, ge=0, le=100)
    music_volume: int = Field(default=50, ge=0, le=100)
    narration_muted: bool = False
    music_muted: bool = False
    effects_volume: int = Field(default=80, ge=0, le=100)  # M26.8: the dice sounds
    effects_muted: bool = False


class FloorSeat(_View):
    """One player on the floor line: `position` is 1-based in the waiting queue (0 otherwise)."""

    player_id: str
    name: str
    hero_name: str = ""
    position: int = Field(default=0, ge=0)


class FloorView(_View):
    """Out of combat: `holder` is the player whose action is resolving (in combat: the owner of
    the active hero); `queue` waits in order (`queue[0]` is next); `typing` are composing now."""

    holder: FloorSeat | None = None
    queue: tuple[FloorSeat, ...] = ()
    typing: tuple[FloorSeat, ...] = ()
    seconds_left: float | None = Field(
        default=None, description="seconds left on the running turn timer (M15.1)"
    )


class PublicState(_View):
    campaign_id: str
    phase: TablePhase = TablePhase.LOBBY
    paused: bool = False
    players: tuple[PlayerInfo, ...] = ()
    party: tuple[PublicCreature, ...] = ()
    scene: PublicScene | None = None
    map: PublicMap | None = None
    quests: tuple[PublicQuest, ...] = ()
    leads: tuple[str, ...] = ()
    facts: tuple[str, ...] = ()
    summaries: tuple[PublicSummary, ...] = ()
    combat: PublicCombat | None = None
    offer: PublicOffer | None = None
    quest_offer: PublicQuestOffer | None = None
    finale: PublicFinale | None = None
    queue: tuple[QueueEntry, ...] = ()
    resolving: QueueEntry | None = None
    vote: VoteView | None = None
    campaign_title: str = ""
    region_tier: int = 1
    camp_supplies: int = 0
    complete: bool = False
    epilogue: str | None = None
    tts_enabled: bool = False
    screens: int = 0  # connected /screen clients (the default audio device); M8.3 fills it
    monster_hp: float = 1.0
    monster_damage: float = 1.0
    defeat: str | None = Field(default=None, description="the defeat epilogue (phase defeated)")
    checkpoint: str | None = Field(default=None, description="label of the retry checkpoint")
    audio: AudioSettings = AudioSettings()
    turn_timer: int = Field(default=0, description="the host's turn timer in seconds, 0 = off")
    floor: FloorView = FloorView()
    scribe: ScribeView = ScribeView()


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
    kind: RollKind = RollKind.OTHER
    target_id: str | None = None
    source_id: str | None = Field(default=None, description="who forced the save")
    parts: tuple[RollPart, ...] = ()
    adv_why: tuple[str, ...] = ()
    difficulty: str | None = Field(default=None, description="the DC tier word")


class RollEntry(_View):
    """One recent dice roll of the story history (restores the dice panel on reconnect)."""

    seq: int = Field(ge=0, description="event-log position of the roll")
    dice: DiceView


class StoryEntry(_View):
    """One line of the story history: a told narration (id, tone), a public event line, or a
    player's typed action (M22.1: `text` is their words; who typed it and for which hero)."""

    kind: Literal["narration", "event", "action"]
    seq: int = Field(ge=0, description="event-log position the entry follows")
    text: str
    id: str = ""
    tone: NarrationTone | None = None
    event_kind: str = ""
    creature_id: str = ""
    player_name: str = ""
    hero_name: str = ""


class StockLine(_View):
    item_id: str
    name: str
    price_gp: int = Field(ge=0)
    unit_gp: float = Field(default=0.0, ge=0, description="exact price of one before rounding")
    bulk: str = Field(default="", description="e.g. '2 for 1 gp' for an item under 1 gp")
    category: str = ""
    supply: int = Field(default=0, ge=0, description="camp supplies one purchase adds")
