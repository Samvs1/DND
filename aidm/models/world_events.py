"""World events (part of the `aidm.models.events.Event` union; same design rules apply).

Emitted by the DM tool executors (`aidm.dm.tool_exec`) and applied by
`aidm.session.world_apply`. Payloads are resolved: ids, scores and scene indexes are computed
before the event exists, the reducer only assigns.

Public API:
- `NpcIntroduced(npc)`: register a new NPC (full snapshot; the id must be new).
- `FeatureIntroduced(feature)`: register a door, lever, cache, trap...
- `AttitudeChanged(npc_id, social, deeds, hostile, reason)`: the NPC's attitude inputs become
  exactly these values (`aidm.rules.social` computed them).
- `SecretRevealed(npc_id, secret_id)`: the secret is now known to the party.
- `PartyMoved(from_node, to_node, scene_index)`: the party travelled to a legal neighbour; a new
  scene starts.
- `QuestUpdated(quest)`: the quest becomes exactly `quest` (new or changed).
- `FactRecorded(fact)`: appended to the fact ledger.
- `ShopOpened(npc_id)`: the NPC's shop is open for the party.
- `HostileActPending(actor_id, npc_ids, tool, reason)`: pure log event (point of no return): a
  hostile act against non-hostile NPCs waits for the acting player's confirmation; nothing
  else changed.
- `ItemsTraded(npc_id, creature_id, item, qty, gold, sold)` (M5.6): pure log event of a shop
  sale or purchase (gold and inventory move through `GoldChanged` / `InventoryChanged`).
- `RewardGranted(source, kind, xp_each, gold_each, items)` (M5.6): log event of loot, a quest
  or a milestone paying out (the numbers move through their own events); a milestone's
  `source` joins `CampaignState.milestones` (M9.2), so it is paid once.
- `LevelUpReady(creature_id, level)` (M5.6): pure log event: the PC has enough XP for `level`.
- `FeatureDiscovered(feature_id, creature_id)` (M4.3): a hidden feature was found; it joins
  the manifest.
- `NodeDescribed(node_id, text)`: the established description of a place (stored once).
- `ItemPlaced(item)` / `ItemRemoved(item_id)`: a world item appears in / leaves a place.
- `NarrationRecorded(text, scene_turn)`: one narrated turn joins the rolling memory and the
  scene turn counter becomes `scene_turn`.
- `SceneSummarised(summary)` (M4.7): a scene summary joins the rolling memory and the count of
  unsummarised turns restarts at zero (its facts arrive as separate `FactRecorded` events).
- `EquipmentChanged(creature_id, equipped, ac)` (M6.2): the hero's worn/held gear becomes
  `equipped` and its armour class `ac` (computed by `aidm.rules.equipment`).
- `WorldEvents`: the union of these classes (joins `AnyEvent`).
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from aidm.models.character import Equipped
from aidm.models.memory import SceneSummary
from aidm.models.world import Fact, Quest, WorldFeature, WorldItem, WorldNpc


class _WorldEvent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class NpcIntroduced(_WorldEvent):
    type: Literal["npc_introduced"] = "npc_introduced"
    npc: WorldNpc


class FeatureIntroduced(_WorldEvent):
    type: Literal["feature_introduced"] = "feature_introduced"
    feature: WorldFeature


class AttitudeChanged(_WorldEvent):
    type: Literal["attitude_changed"] = "attitude_changed"
    npc_id: str
    social: int
    deeds: int
    hostile: bool = False
    reason: str = ""


class SecretRevealed(_WorldEvent):
    type: Literal["secret_revealed"] = "secret_revealed"
    npc_id: str
    secret_id: str


class PartyMoved(_WorldEvent):
    type: Literal["party_moved"] = "party_moved"
    from_node: str | None
    to_node: str
    scene_index: int = Field(ge=0)


class QuestUpdated(_WorldEvent):
    type: Literal["quest_updated"] = "quest_updated"
    quest: Quest


class FactRecorded(_WorldEvent):
    type: Literal["fact_recorded"] = "fact_recorded"
    fact: Fact


class ShopOpened(_WorldEvent):
    type: Literal["shop_opened"] = "shop_opened"
    npc_id: str


class HostileActPending(_WorldEvent):
    type: Literal["hostile_act_pending"] = "hostile_act_pending"
    actor_id: str | None
    npc_ids: tuple[str, ...]
    tool: str
    reason: str = ""


class ItemsTraded(_WorldEvent):
    type: Literal["items_traded"] = "items_traded"
    npc_id: str
    creature_id: str
    item: str = Field(min_length=1)
    qty: int = Field(ge=1)
    gold: int = Field(ge=0)
    sold: bool = False


class RewardGranted(_WorldEvent):
    type: Literal["reward_granted"] = "reward_granted"
    source: str = Field(min_length=1)
    kind: Literal["loot", "quest", "milestone"]
    xp_each: int = Field(default=0, ge=0)
    gold_each: int = Field(default=0, ge=0)
    items: tuple[str, ...] = ()


class LevelUpReady(_WorldEvent):
    type: Literal["level_up_ready"] = "level_up_ready"
    creature_id: str
    level: int = Field(ge=2, le=20)


class FeatureDiscovered(_WorldEvent):
    type: Literal["feature_discovered"] = "feature_discovered"
    feature_id: str
    creature_id: str | None = None


class NodeDescribed(_WorldEvent):
    type: Literal["node_described"] = "node_described"
    node_id: str = Field(min_length=1)
    text: str = Field(min_length=1)


class ItemPlaced(_WorldEvent):
    type: Literal["item_placed"] = "item_placed"
    item: WorldItem


class ItemRemoved(_WorldEvent):
    type: Literal["item_removed"] = "item_removed"
    item_id: str


class NarrationRecorded(_WorldEvent):
    type: Literal["narration_recorded"] = "narration_recorded"
    text: str = Field(min_length=1)
    scene_turn: int = Field(ge=0)


class SceneSummarised(_WorldEvent):
    type: Literal["scene_summarised"] = "scene_summarised"
    summary: SceneSummary


class EquipmentChanged(_WorldEvent):
    type: Literal["equipment_changed"] = "equipment_changed"
    creature_id: str
    equipped: Equipped
    ac: int = Field(ge=0)


WorldEvents = (
    NpcIntroduced
    | FeatureIntroduced
    | AttitudeChanged
    | SecretRevealed
    | PartyMoved
    | QuestUpdated
    | FactRecorded
    | ShopOpened
    | HostileActPending
    | ItemsTraded
    | RewardGranted
    | LevelUpReady
    | FeatureDiscovered
    | NodeDescribed
    | ItemPlaced
    | ItemRemoved
    | NarrationRecorded
    | SceneSummarised
    | EquipmentChanged
)
