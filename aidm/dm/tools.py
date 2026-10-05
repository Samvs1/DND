"""The DM tool schemas (SPEC 6.3): one pydantic arg model per tool, plus their OpenAI export.

The LLM only proposes; `aidm.dm.tool_exec.execute_tool` validates against state and owns every
number. These models bound the shape (enums, lengths, counts); the executors bound the meaning
(known ids, caps, budgets). Strings that name things are short and plain so a prompt injection
cannot smuggle numbers through them.

Public API:
- One `<Tool>Args` model per tool: `RequestCheckArgs`, `RequestSaveArgs`, `CreativeEffectArgs`,
  `UpdateAttitudeArgs`, `RevealSecretArgs`, `MovePartyArgs`, `IntroduceNpcArgs`,
  `IntroduceFeatureArgs`, `GrantItemArgs`, `GrantXpArgs`, `StartEncounterArgs`, `OpenShopArgs`,
  `UpdateQuestArgs`, `RecordFactArgs`, `NoMechanicsArgs`.
- `DM_TOOLS`: every `ToolDef` in SPEC order; `dm_tool(name) -> ToolDef`;
  `dm_tools_param(names=None) -> list[dict]` (the OpenAI `tools` parameter).
"""

from collections.abc import Sequence
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aidm.dm.llm_types import ToolDef, tool_param
from aidm.models.abilities import Ability, Skill
from aidm.models.checks import DcTier
from aidm.models.damage import DamageType
from aidm.models.dice import AdvState
from aidm.models.dm_tiers import DeltaTier, EffectKind, Severity, XpTier
from aidm.models.encounter import SurpriseKind
from aidm.models.world import FeatureKind, QuestState


def _id() -> Any:
    return Field(min_length=1, max_length=64)


def _reason() -> Any:
    return Field(default="", max_length=200)


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RequestCheckArgs(_Args):
    """Ask one character for an ability or skill check; the engine sets the DC from the tier."""

    actor: str = _id()
    ability_or_skill: Skill | Ability
    dc_tier: DcTier
    reason: str = _reason()
    advantage: AdvState = AdvState.NORMAL


class RequestSaveArgs(_Args):
    """Ask one or more creatures for a saving throw against a tiered DC."""

    actors: list[str] = Field(min_length=1, max_length=8)
    ability: Ability
    dc_tier: DcTier
    reason: str = _reason()


class CreativeEffectArgs(_Args):
    """An improvised effect; the engine maps the severity to dice, DCs and durations."""

    actor: str = _id()
    target: str | None = Field(default=None, max_length=64)
    effect_kind: EffectKind
    severity: Severity = Severity.MINOR
    duration_rounds: int = Field(default=1, ge=0, le=10)
    condition: str | None = Field(default=None, max_length=32)
    damage_type: DamageType = DamageType.BLUDGEONING


class UpdateAttitudeArgs(_Args):
    """Shift an NPC's attitude after social play (bounded; only deeds make allies)."""

    npc: str = _id()
    delta_tier: DeltaTier
    reason: str = _reason()


class RevealSecretArgs(_Args):
    """An NPC reveals one of their secrets (only if its reveal condition is met)."""

    npc: str = _id()
    secret_id: str = _id()


class MovePartyArgs(_Args):
    """Travel to a listed neighbouring location."""

    node_id: str = _id()


class IntroduceNpcArgs(_Args):
    """Register a new minor NPC; only registered NPCs exist."""

    name: str = Field(min_length=1, max_length=40)
    role: str = Field(min_length=1, max_length=40)
    archetype_id: str = _id()
    demeanor: str = Field(default="", max_length=60)
    voice_tag: str = Field(default="", max_length=30)


class IntroduceFeatureArgs(_Args):
    """Register a door, lever, cache, trap...; hidden ones need a discover DC tier."""

    kind: FeatureKind
    name: str = Field(min_length=1, max_length=40)
    description: str = Field(default="", max_length=200)
    interactable: bool = True
    hidden: bool = False
    discover_dc_tier: DcTier | None = None

    @model_validator(mode="after")
    def _hidden_needs_dc(self) -> Self:
        if self.hidden and self.discover_dc_tier is None:
            raise ValueError("a hidden feature needs discover_dc_tier")
        return self


class GrantItemArgs(_Args):
    """Give the acting character an item from the catalogue (value capped by region)."""

    catalog_id: str = _id()
    qty: int = Field(default=1, ge=1, le=100)
    reason: str = _reason()


class GrantXpArgs(_Args):
    """Award experience to the party; the engine maps the tier to XP."""

    tier: XpTier
    reason: str = _reason()


class StartEncounterArgs(_Args):
    """Start a fight with catalogue monsters (CR budget enforced) and/or present NPCs."""

    monster_ids: list[str] = Field(default_factory=list[str], max_length=8)
    terrain_tags: list[str] = Field(default_factory=list[str], max_length=3)
    surprise: SurpriseKind = SurpriseKind.NONE
    against_npcs: list[str] = Field(default_factory=list[str], max_length=4)

    @model_validator(mode="after")
    def _someone(self) -> Self:
        if not self.monster_ids and not self.against_npcs:
            raise ValueError("name at least one monster id or NPC")
        return self


class OpenShopArgs(_Args):
    """Open a present NPC's shop."""

    npc: str = _id()


class UpdateQuestArgs(_Args):
    """Create or move a quest; a new quest needs a title. Completed and failed are final."""

    quest_id: str = _id()
    state: QuestState
    title: str | None = Field(default=None, max_length=80)
    giver_npc: str | None = Field(default=None, max_length=64)


class RecordFactArgs(_Args):
    """Write one fact to the ledger, tagged with the ids of known entities."""

    text: str = Field(min_length=1, max_length=300)
    entity_ids: list[str] = Field(default_factory=list[str], max_length=8)
    tags: list[str] = Field(default_factory=list[str], max_length=8)


class NoMechanicsArgs(_Args):
    """Pure narration: nothing changes."""


def _def(name: str, model: type[BaseModel]) -> ToolDef:
    return ToolDef(name, (model.__doc__ or name).strip(), model)


DM_TOOLS: tuple[ToolDef, ...] = (
    _def("request_check", RequestCheckArgs),
    _def("request_save", RequestSaveArgs),
    _def("creative_effect", CreativeEffectArgs),
    _def("update_attitude", UpdateAttitudeArgs),
    _def("reveal_secret", RevealSecretArgs),
    _def("move_party", MovePartyArgs),
    _def("introduce_npc", IntroduceNpcArgs),
    _def("introduce_feature", IntroduceFeatureArgs),
    _def("grant_item", GrantItemArgs),
    _def("grant_xp", GrantXpArgs),
    _def("start_encounter", StartEncounterArgs),
    _def("open_shop", OpenShopArgs),
    _def("update_quest", UpdateQuestArgs),
    _def("record_fact", RecordFactArgs),
    _def("no_mechanics", NoMechanicsArgs),
)
_BY_NAME = {d.name: d for d in DM_TOOLS}


def dm_tool(name: str) -> ToolDef:
    return _BY_NAME[name]


def dm_tools_param(names: Sequence[str] | None = None) -> list[dict[str, Any]]:
    chosen = DM_TOOLS if names is None else tuple(_BY_NAME[n] for n in names)
    return [tool_param(d) for d in chosen]
