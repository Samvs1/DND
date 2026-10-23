"""The world entity registry: what exists outside combat (SPEC 2.2 closed world, 6.3, 9).

Things exist only once a creation tool (or the campaign generator) registered them. The narrator
sees the registry through the manifest (M4.3). M4.2 adds the minimal shape; M4.3/M5 extend it
(every new field needs a default, like all state models).

Public API:
- `FeatureKind`: door / lever / cache / trap / container / passage / object / hazard.
- `QuestState`: offered / active / completed / failed (completed and failed are final).
- `NpcSecret(id, text, min_score, reveal, revealed)`: private NPC knowledge (never sent to
  clients or narration context); `reveal_secret` succeeds only when the NPC's attitude score
  reaches `min_score` (None: no attitude condition) AND the structured campaign condition
  `reveal` (quest completed, item possessed, fact known...) holds (`aidm.rules.secrets`).
- `WorldNpc(id, name, role, archetype_id, demeanor, voice_tag, node_id, scene_index, base,
  social, deeds, hostile, motive, secrets)`: a registered NPC. `archetype_id` is an SRD
  monster/NPC stat block index. The attitude score is derived by `aidm.rules.social` from
  `base` plus the capped/floored `social` contribution plus uncapped `deeds`; `hostile` is set
  once violence against the NPC was confirmed.
- `PublicNpcView(id, name, role, demeanor, node_id, attitude, hostile, revealed_secrets)`: the
  client projection of an NPC (built by `aidm.rules.social.public_npc_view`; no motive, no
  unrevealed secret, no raw scores).
- `WorldFeature(id, kind, name, description, interactable, node_id, hidden, discover_dc,
  discovered, lock)`: a door, lever, cache or trap. Hidden features carry a `discover_dc` and are
  not in the manifest until discovered. `lock` (M27.4; None = unlocked, so old saves load unlocked)
  is a `LockInfo(dc_tier, opens)`: the engine's DC tier word and the feature kind a key must
  open (`aidm.rules.locks`).
- `Quest(id, title, state, giver_npc_id, against_npc_id, kind, objective, steps, steps_done,
  routes, log, closed_reason)` (M23 fields default, so old `QuestUpdated` events load as side
  quests): `steps` are a side quest's or favour's own steps (a main quest's routes live in the
  plan, `aidm.rules.quest_plan`); `steps_done` counts finished steps (sequential); `routes`
  are the KNOWN routes of a main quest with their progress (`RouteProgress(route_id,
  steps_done)`); `log` the last `MAX_QUEST_LOG` lines of what happened in it; `closed_reason`
  `left_behind` marks a failed quest that was left behind on crossing a gateway (no penalty).
- `QuestLead(quest_id, text)`: a journal line pointing at a side quest's giver (M23).
- `QuestAsk(quest_id, npc_id, node_id)`: the giver's open question (M23.4): the phones show the
  Accept / Not now card while it is set; answering, declining or leaving the node clears it.
- `Fact(id, text, entity_ids, tags)`: the fact ledger.
- `WorldItem(id, name, catalog_id, qty, node_id, hidden, discover_dc, quest_id)`: an item lying
  in a place (dropped, found); visible items are part of the manifest. A hidden item is found by
  a search check meeting `discover_dc` (M23.3); `quest_id` marks a quest item the engine placed
  (picked up, it becomes a `Keepsake` with that `quest_id`). M29.9b T13: `teaches`, the learn tag
  a clue item carries (it goes along to the keepsake, `rules.lore`).
- `World(current_node, neighbours, locked_nodes, visited, region_tier, scene_index, npcs,
  features, quests, facts, shop_npc_id, node_names, descriptions, items, lore_names,
  scene_turn)`: `neighbours` maps a node id to its legal travel neighbours (the region graph of
  M5.2 fills it); `scene_index` grows on every move and bounds per-scene creation caps.
  M4.3 scene fields: `node_names` (display names, M5.2), `descriptions` (the established
  description of a node, stored once and never regenerated), `items` (world items by id),
  `lore_names` (world-bible names the guard allows), `scene_turn` (narrated turns in the
  current scene; reset by a move). The derived scene view is `aidm.rules.scene.current_scene`.
  M29.9b: `arrived` (node id -> the seq of the party's last arrival there) and `learned` (learn
  tag -> the seq of the last `LoreLearned`); `Quest.active_since` is the seq at which a side
  quest or favour was accepted (None: a main quest, or a save from before), so a visit or a
  lesson counts only when made while the quest is active (`aidm.rules.quest_steps`).
  M23: `leads` (quest leads), `quest_ask` (the pending quest offer, at most one);
  `WorldNpc.keepsakes` holds keepsakes handed to that NPC. A closed quest's `closed_reason`:
  `left_behind` (its region was left) or `withdrawn` (a favour let go, M23.5).
  M27.12: `lights` (`CarriedLight(creature_id, item, reach)`, one per hero, set by `LightLit`,
  ended by `LightEnded`): the lit lights the heroes carry. A light travels with its bearer from
  place to place until the next long rest (`PartyMoved` keeps it). `reach` (`LightReach`):
  "touching" lights the bearer's zone and the touching zones in a fight (torch, lantern), "zone"
  only the bearer's zone (candle). Darkness itself is derived (`aidm.rules.light`), never
  stored. A snapshot from M27.2-M27.3 holds the place-bound `lit` key; it is dropped on load.
  M27.3 (gear): `boons` (`ActiveBoon`: advantage a hero's gear gives on listed skills or on
  saves against listed harms; scope "place" ends on `PartyMoved`, "until_long_rest" on the long
  rest), `alerted` (the place a noisy use alerted; cleared on `PartyMoved`; M27.5 `alerted_by`
  "noise" or "light", a light gave the party away), `foraged` (places
  whose once-per-place supplies use is spent), `charted` (places made known by a map use: their
  names and ways show on the map without a visit). Old saves default to empty.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aidm.models.campaign import RevealCondition
from aidm.models.character import Keepsake
from aidm.models.checks import DcTier
from aidm.models.dm_tiers import AttitudeBand
from aidm.models.quests import QuestKind, QuestStep

MAX_QUEST_LOG = 8

type LightReach = Literal["zone", "touching"]
type AlertCause = Literal["noise", "light"]  # M27.5: what alerted a place


class CarriedLight(BaseModel):
    """A lit light a hero carries (M27.12); `item` is the catalogue id (torch, lantern...)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    creature_id: str = Field(min_length=1)
    item: str = Field(min_length=1)
    reach: LightReach = "touching"


type BoonScope = Literal["place", "until_long_rest"]  # mirrors aidm.data.item_uses.BoonScope


class ActiveBoon(BaseModel):
    """Gear advantage (M27.3): `name` is the reason shown with the dice; `tool` is the catalogue
    id of an SRD tool when the boon came from one (a check it covers is made with that tool)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    creature_id: str = Field(min_length=1)
    use_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    skills: tuple[str, ...] = ()
    saves_against: tuple[str, ...] = ()
    scope: BoonScope = "place"
    node: str | None = None
    tool: str | None = None


class FeatureKind(StrEnum):
    DOOR = "door"
    LEVER = "lever"
    CACHE = "cache"
    TRAP = "trap"
    CONTAINER = "container"
    PASSAGE = "passage"
    OBJECT = "object"
    HAZARD = "hazard"


class QuestState(StrEnum):
    OFFERED = "offered"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"


class NpcSecret(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    min_score: int | None = None
    reveal: RevealCondition | None = None
    revealed: bool = False


class WorldNpc(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    role: str = ""
    archetype_id: str = Field(min_length=1)
    demeanor: str = ""
    voice_tag: str = ""
    node_id: str | None = None
    scene_index: int = Field(default=0, ge=0)
    base: int = 0
    social: int = 0
    deeds: int = 0
    hostile: bool = False
    motive: str = ""
    secrets: list[NpcSecret] = Field(default_factory=list[NpcSecret])
    dead: bool = False  # M20.5: their fight creature died; never present, never fought again
    keepsakes: list[Keepsake] = Field(default_factory=list[Keepsake])  # M23: handed to them
    gifts: list[str] = Field(default_factory=list[str])  # M29.6b: item keys that earned a deed
    paid: int = Field(default=0, ge=0)  # M29.9a T17: gold the party paid them (pay steps)


class PublicNpcView(BaseModel):
    """What a client may see of an NPC: never the motive or an unrevealed secret (SPEC 9)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    name: str
    role: str = ""
    demeanor: str = ""
    node_id: str | None = None
    attitude: AttitudeBand
    hostile: bool = False
    revealed_secrets: tuple[str, ...] = ()


class LockInfo(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    dc_tier: DcTier = DcTier.MEDIUM
    opens: FeatureKind


class WorldFeature(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    kind: FeatureKind
    name: str = Field(min_length=1)
    description: str = ""
    interactable: bool = True
    node_id: str | None = None
    scene_index: int = Field(default=0, ge=0)
    hidden: bool = False
    discover_dc: int | None = Field(default=None, ge=0)
    discovered: bool = False
    lock: LockInfo | None = None


class ClosedReason(StrEnum):
    LEFT_BEHIND = "left_behind"
    WITHDRAWN = "withdrawn"  # M23.5: a favour the party let go (Not now, or its card withdrawn)


class RouteProgress(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    route_id: str = Field(min_length=1)
    steps_done: int = Field(default=0, ge=0)


class Quest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    state: QuestState = QuestState.ACTIVE
    giver_npc_id: str | None = None
    against_npc_id: str | None = None
    kind: QuestKind = QuestKind.SIDE
    objective: str = ""
    steps: tuple[QuestStep, ...] = ()
    steps_done: int = Field(default=0, ge=0)
    routes: tuple[RouteProgress, ...] = ()
    log: tuple[str, ...] = Field(default=(), max_length=MAX_QUEST_LOG)
    closed_reason: ClosedReason | None = None
    active_since: int | None = Field(default=None, ge=0)  # M29.9b: seq of the acceptance

    def route(self, route_id: str) -> RouteProgress | None:
        return next((r for r in self.routes if r.route_id == route_id), None)

    @model_validator(mode="after")
    def _consistent(self) -> Quest:
        if self.steps_done > len(self.steps):
            raise ValueError(f"quest {self.id!r}: more steps done than it has")
        if len({r.route_id for r in self.routes}) != len(self.routes):
            raise ValueError(f"quest {self.id!r}: a route is known twice")
        if self.closed_reason is not None and self.state is not QuestState.FAILED:
            raise ValueError(f"quest {self.id!r}: only a failed quest has a closed reason")
        return self


class QuestLead(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    quest_id: str = Field(min_length=1)
    text: str = Field(min_length=1, max_length=160)


class QuestAsk(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    quest_id: str = Field(min_length=1)
    npc_id: str = Field(min_length=1)
    node_id: str = Field(min_length=1)


class Fact(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    entity_ids: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()


class WorldItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    catalog_id: str | None = None
    qty: int = Field(default=1, ge=1)
    node_id: str | None = None
    hidden: bool = False
    discover_dc: int | None = Field(default=None, ge=0)
    quest_id: str | None = None
    teaches: str | None = None  # M29.9b T13: the learn tag a clue item carries


class World(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_node: str | None = None
    neighbours: dict[str, list[str]] = Field(default_factory=dict[str, list[str]])
    locked_nodes: list[str] = Field(default_factory=list[str])
    visited: list[str] = Field(default_factory=list[str])
    region_tier: int = Field(default=1, ge=1, le=3)
    scene_index: int = Field(default=0, ge=0)
    npcs: dict[str, WorldNpc] = Field(default_factory=dict[str, WorldNpc])
    features: dict[str, WorldFeature] = Field(default_factory=dict[str, WorldFeature])
    quests: dict[str, Quest] = Field(default_factory=dict[str, Quest])
    facts: list[Fact] = Field(default_factory=list[Fact])
    shop_npc_id: str | None = None
    node_names: dict[str, str] = Field(default_factory=dict[str, str])
    descriptions: dict[str, str] = Field(default_factory=dict[str, str])
    items: dict[str, WorldItem] = Field(default_factory=dict[str, WorldItem])
    lore_names: list[str] = Field(default_factory=list[str])
    scene_turn: int = Field(default=0, ge=0)
    leads: list[QuestLead] = Field(default_factory=list[QuestLead])
    quest_ask: QuestAsk | None = None
    lights: list[CarriedLight] = Field(default_factory=list[CarriedLight])  # M27.12
    boons: list[ActiveBoon] = Field(default_factory=list[ActiveBoon])  # M27.3
    alerted: str | None = None  # M27.3: cleared on PartyMoved
    alerted_by: AlertCause | None = None  # M27.5: why `alerted` (old saves: None = noise)
    foraged: list[str] = Field(default_factory=list[str])  # M27.3
    charted: list[str] = Field(default_factory=list[str])  # M27.3
    arrived: dict[str, int] = Field(default_factory=dict[str, int])  # M29.9b: node -> last seq
    learned: dict[str, int] = Field(default_factory=dict[str, int])  # M29.9b: tag -> last seq

    @model_validator(mode="before")
    @classmethod
    def _drop_place_light(cls, data: object) -> object:
        """M27.2-M27.3 snapshots hold the place-bound `lit` (always null in play): drop it."""
        if not isinstance(data, dict):
            return data
        raw = cast(dict[str, object], data)
        return {k: v for k, v in raw.items() if k != "lit"} if "lit" in raw else raw
