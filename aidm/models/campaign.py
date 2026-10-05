"""The campaign plan: premise, 3 acts, one region per act, the NPC cast, bosses and quests (SPEC 9).

The plan is DATA: the LLM campaign generator (M5.3) or the built-in sample campaign
(`data/campaigns/sample_campaign.json`, loaded by `aidm.dm.campaign_sample`) produce it, code
validates it, and the region graph (`aidm.rules.world_graph`) is built from it by code. Structural
validation (unique ids, internal references, the region shape) lives here; checks against the data
registries (monster ids, archetypes, terrain tags, boss CR vs tier) are in
`aidm.rules.campaign_check` because `aidm.models` may not import `aidm.data`.

Public API:
- `RevealKind` / `RevealCondition(kind, band, quest_id, item, fact_tag)`: when an NPC secret may
  be revealed: attitude band reached, a quest completed, an item shown (the party carries it) or a
  fact known (a ledger fact carries the tag, M5.5). Exactly the field its kind needs.
- `SecretPlan(id, text, reveal)`; `NpcPlan(id, name, role, archetype_id, demeanor, motive,
  secrets, voice_tag, home_node)`.
- `NodePlan(id, name, flavour, terrain_tags, encounter_themes, shop)`: one place. `encounter_themes`
  are monster ids (encounter catalogue ids of the region tier).
- `BossPlan(monster_id, name, lair_node, ally_path, defeat_always)`: the boss lives at the gateway;
  `defeat_always` is always true (an ally path never replaces defeat).
- `RegionPlan(id, name, flavour, tier, terrain_tags, arrival, spokes, gateway, boss)`:
  one safe arrival (no encounters), 2 to 3 spokes (each with encounter themes), one gateway;
  `nodes()` lists them in that order.
- `RivalPlan(npc_id, hook)`; `QuestPlan(id, title, giver_npc_id, objective, reward_tier, act,
  reward_item, against_npc_id)` (completing it is a deed for the giver and against the
  target); `Act(index, title, goal, region)`.
- `CampaignPlan(title, premise, tone, theme, acts, npcs, quests, rival)`: exactly 3 acts, act
  `i` has region tier `i`; `all_nodes()`, `all_regions()`.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aidm.models.dm_tiers import AttitudeBand

ID_PATTERN = r"^[a-z0-9][a-z0-9-]*$"
ACT_COUNT = 3

type RewardTier = Literal["minor", "moderate", "major"]


def _id() -> str:
    return Field(pattern=ID_PATTERN, max_length=60)


class _Plan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class RevealKind(StrEnum):
    ATTITUDE = "attitude"
    QUEST_COMPLETED = "quest_completed"
    ITEM_SHOWN = "item_shown"
    FACT_KNOWN = "fact_known"


class RevealCondition(_Plan):
    kind: RevealKind
    band: AttitudeBand | None = None
    quest_id: str | None = None
    item: str | None = None
    fact_tag: str | None = Field(default=None, min_length=1, max_length=24)

    @model_validator(mode="after")
    def _one_field_for_kind(self) -> RevealCondition:
        given = {
            "band": self.band,
            "quest_id": self.quest_id,
            "item": self.item,
            "fact_tag": self.fact_tag,
        }
        needed = {
            RevealKind.ATTITUDE: "band",
            RevealKind.QUEST_COMPLETED: "quest_id",
            RevealKind.ITEM_SHOWN: "item",
            RevealKind.FACT_KNOWN: "fact_tag",
        }[self.kind]
        extra = [name for name, value in given.items() if value is not None and name != needed]
        if given[needed] is None or extra:
            raise ValueError(f"reveal kind {self.kind.value!r} needs exactly {needed!r}")
        if self.band is AttitudeBand.HOSTILE:
            raise ValueError("a secret cannot require a hostile attitude")
        return self


class SecretPlan(_Plan):
    id: str = _id()
    text: str = Field(min_length=1, max_length=300)
    reveal: RevealCondition


class NpcPlan(_Plan):
    id: str = _id()
    name: str = Field(min_length=1, max_length=40)
    role: str = Field(min_length=1, max_length=40)
    archetype_id: str = _id()
    demeanor: str = Field(min_length=1, max_length=80)
    motive: str = Field(min_length=1, max_length=200)
    secrets: tuple[SecretPlan, ...] = ()
    voice_tag: str = Field(default="", max_length=30)
    home_node: str = _id()

    @model_validator(mode="after")
    def _secret_ids_unique(self) -> NpcPlan:
        ids = [s.id for s in self.secrets]
        if len(ids) != len(set(ids)):
            raise ValueError(f"npc {self.id!r} has duplicate secret ids")
        return self


class NodePlan(_Plan):
    id: str = _id()
    name: str = Field(min_length=1, max_length=40)
    flavour: str = Field(min_length=1, max_length=200)
    terrain_tags: tuple[str, ...] = Field(min_length=1, max_length=3)
    encounter_themes: tuple[str, ...] = ()
    shop: bool = False


class BossPlan(_Plan):
    monster_id: str = _id()
    name: str = Field(min_length=1, max_length=40)
    lair_node: str = _id()
    ally_path: str | None = Field(default=None, max_length=300)
    defeat_always: Literal[True] = True


class RegionPlan(_Plan):
    id: str = _id()
    name: str = Field(min_length=1, max_length=40)
    flavour: str = Field(min_length=1, max_length=300)
    tier: int = Field(ge=1, le=3)
    terrain_tags: tuple[str, ...] = Field(min_length=1, max_length=4)
    arrival: NodePlan
    spokes: tuple[NodePlan, ...] = Field(min_length=2, max_length=3)
    gateway: NodePlan
    boss: BossPlan

    def nodes(self) -> tuple[NodePlan, ...]:
        return (self.arrival, *self.spokes, self.gateway)

    @model_validator(mode="after")
    def _shape(self) -> RegionPlan:
        ids = [n.id for n in self.nodes()]
        if len(ids) != len(set(ids)):
            raise ValueError(f"region {self.id!r} has duplicate node ids")
        if self.arrival.encounter_themes:
            raise ValueError(f"region {self.id!r}: the arrival node must be safe (no encounters)")
        if any(not s.encounter_themes for s in self.spokes):
            raise ValueError(f"region {self.id!r}: every spoke needs encounter themes")
        if self.boss.lair_node != self.gateway.id:
            raise ValueError(f"region {self.id!r}: the boss lair must be the gateway node")
        return self


class RivalPlan(_Plan):
    npc_id: str = _id()
    hook: str = Field(min_length=1, max_length=200)


class QuestPlan(_Plan):
    id: str = _id()
    title: str = Field(min_length=1, max_length=60)
    giver_npc_id: str = _id()
    objective: str = Field(min_length=1, max_length=200)
    reward_tier: RewardTier
    act: int = Field(ge=1, le=ACT_COUNT)
    reward_item: str | None = Field(default=None, max_length=60)
    against_npc_id: str | None = None


class Act(_Plan):
    index: int = Field(ge=1, le=ACT_COUNT)
    title: str = Field(min_length=1, max_length=60)
    goal: str = Field(min_length=1, max_length=200)
    region: RegionPlan


def _unique(kind: str, ids: list[str]) -> None:
    seen: set[str] = set()
    for value in ids:
        if value in seen:
            raise ValueError(f"duplicate {kind} id {value!r}")
        seen.add(value)


class CampaignPlan(_Plan):
    title: str = Field(min_length=1, max_length=80)
    premise: str = Field(min_length=1, max_length=600)
    tone: str = Field(min_length=1, max_length=80)
    theme: str = Field(min_length=1, max_length=120)
    acts: tuple[Act, ...] = Field(min_length=ACT_COUNT, max_length=ACT_COUNT)
    npcs: tuple[NpcPlan, ...] = Field(min_length=1)
    quests: tuple[QuestPlan, ...] = ()
    rival: RivalPlan | None = None

    def all_regions(self) -> tuple[RegionPlan, ...]:
        return tuple(a.region for a in self.acts)

    def all_nodes(self) -> tuple[NodePlan, ...]:
        return tuple(n for r in self.all_regions() for n in r.nodes())

    @model_validator(mode="after")
    def _structure(self) -> CampaignPlan:
        if [a.index for a in self.acts] != list(range(1, ACT_COUNT + 1)):
            raise ValueError("acts must be numbered 1, 2, 3 in order")
        if [a.region.tier for a in self.acts] != list(range(1, ACT_COUNT + 1)):
            raise ValueError("act i must have a region of tier i")
        _unique("region", [r.id for r in self.all_regions()])
        _unique("node", [n.id for n in self.all_nodes()])
        _unique("npc", [n.id for n in self.npcs])
        _unique("quest", [q.id for q in self.quests])
        return self

    @model_validator(mode="after")
    def _references(self) -> CampaignPlan:
        npc_ids = {n.id for n in self.npcs}
        node_ids = {n.id for n in self.all_nodes()}
        quest_ids = {q.id for q in self.quests}
        items = {q.reward_item for q in self.quests if q.reward_item}
        for npc in self.npcs:
            if npc.home_node not in node_ids:
                raise ValueError(f"npc {npc.id!r}: unknown home node {npc.home_node!r}")
            for secret in npc.secrets:
                _check_reveal(npc.id, secret, quest_ids, items)
        for quest in self.quests:
            if quest.giver_npc_id not in npc_ids:
                raise ValueError(f"quest {quest.id!r}: unknown giver {quest.giver_npc_id!r}")
            if quest.against_npc_id is not None and quest.against_npc_id not in npc_ids:
                raise ValueError(f"quest {quest.id!r}: unknown target {quest.against_npc_id!r}")
        if self.rival is not None and self.rival.npc_id not in npc_ids:
            raise ValueError(f"rival {self.rival.npc_id!r} is not in the cast")
        return self


def _check_reveal(npc_id: str, secret: SecretPlan, quests: set[str], items: set[str]) -> None:
    cond = secret.reveal
    if cond.kind is RevealKind.QUEST_COMPLETED and cond.quest_id not in quests:
        raise ValueError(f"npc {npc_id!r} secret {secret.id!r}: unknown quest {cond.quest_id!r}")
    if cond.kind is RevealKind.ITEM_SHOWN and cond.item not in items:
        raise ValueError(f"npc {npc_id!r} secret {secret.id!r}: no quest rewards {cond.item!r}")
