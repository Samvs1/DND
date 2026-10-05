"""The world entity registry: what exists outside combat (SPEC 2.2 closed world, 6.3, 9).

Things exist only once a creation tool (or the campaign generator) registered them. The narrator
sees the registry through the manifest (M4.3). M4.2 adds the minimal shape; M4.3/M5 extend it
(every new field needs a default, like all state models).

Public API:
- `FeatureKind`: door / lever / cache / trap / container / passage / object / hazard.
- `QuestState`: offered / active / completed / failed (completed and failed are final).
- `NpcSecret(id, text, min_score, revealed)`: private NPC knowledge (never sent to clients or
  narration context); `reveal_secret` succeeds only when the NPC's attitude score reaches
  `min_score` (None: no attitude condition).
- `WorldNpc(id, name, role, archetype_id, demeanor, voice_tag, node_id, scene_index, base,
  social, deeds, hostile, motive, secrets)`: a registered NPC. `archetype_id` is an SRD
  monster/NPC stat block index. The attitude score is derived by `aidm.rules.social` from
  `base` plus the capped/floored `social` contribution plus uncapped `deeds`; `hostile` is set
  once violence against the NPC was confirmed.
- `WorldFeature(id, kind, name, description, interactable, node_id, hidden, discover_dc,
  discovered)`: a door, lever, cache or trap. Hidden features carry a `discover_dc` and are not
  in the manifest until discovered.
- `Quest(id, title, state, giver_npc_id)`; `Fact(id, text, entity_ids, tags)`: the fact ledger.
- `World(current_node, neighbours, locked_nodes, visited, region_tier, scene_index, npcs,
  features, quests, facts, shop_npc_id)`: `neighbours` maps a node id to its legal travel
  neighbours (the region graph of M5.2 fills it); `scene_index` grows on every move and bounds
  per-scene creation caps.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


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


class Quest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    state: QuestState = QuestState.ACTIVE
    giver_npc_id: str | None = None


class Fact(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    entity_ids: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()


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
