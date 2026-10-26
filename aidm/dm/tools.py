"""The DM tool schemas (SPEC 6.3): one pydantic arg model per tool, plus their OpenAI export.

The LLM only proposes; `aidm.dm.tool_exec.execute_tool` validates against state and owns every
number. These models bound the shape (enums, lengths, counts); the executors bound the meaning
(known ids, caps, budgets). Strings that name things are short and plain so a prompt injection
cannot smuggle numbers through them.

Public API:
- One `<Tool>Args` model per tool: `RequestCheckArgs`, `RequestSaveArgs`, `CreativeEffectArgs`,
  `UpdateAttitudeArgs`, `RevealSecretArgs`, `MovePartyArgs`, `IntroduceNpcArgs`,
  `IntroduceFeatureArgs`, `GrantItemArgs`, `GrantXpArgs`, `StartEncounterArgs`, `OpenShopArgs`,
  `UpdateQuestArgs` (M23.5: a free step only), `OfferFavourArgs` + `FavourKind` (M23.5),
  `RecordFactArgs`, `TakeItemArgs`, `GiveKeepsakeArgs` (M19.3), `UseItemArgs` (M27.5),
  `NoMechanicsArgs`.
- `DM_TOOLS`: every `ToolDef` in SPEC order; `dm_tool(name) -> ToolDef`;
  `dm_tools_param(names=None) -> list[dict]` (the OpenAI `tools` parameter).
"""

from collections.abc import Sequence
from enum import StrEnum
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aidm.dm.llm_types import ToolDef, tool_param
from aidm.models.abilities import Ability, Skill
from aidm.models.character import MAX_KEEPSAKE_NAME
from aidm.models.checks import DcTier
from aidm.models.damage import DamageType
from aidm.models.dice import AdvState
from aidm.models.dm_tiers import AttitudeBand, DeltaTier, EffectKind, Severity, XpTier
from aidm.models.encounter import SurpriseKind
from aidm.models.impossible import MAX_IMPOSSIBLE_REASON
from aidm.models.quests import MAX_STEP_GOLD, MAX_STEP_TEXT, MAX_TAG
from aidm.models.world import FeatureKind


def _id() -> Any:
    return Field(min_length=1, max_length=64)


def _reason() -> Any:
    return Field(default="", max_length=200)


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RequestCheckArgs(_Args):
    """Ask one character for an ability or skill check; the engine sets the DC from the tier.
    Or declare the attempt physically impossible (`impossible`): the engine then rolls nothing."""

    actor: str = _id()
    ability_or_skill: Skill | Ability
    dc_tier: DcTier
    reason: str = _reason()
    advantage: AdvState = AdvState.NORMAL
    feature: str | None = Field(
        default=None,
        max_length=60,
        description=(
            "a LOCKED feature id the check is made on: Athletics forces it (loud), Sleight of"
            " Hand picks it with thieves' tools, a fitting key opens it; the engine sets the DC"
        ),
    )
    impossible: str | None = Field(
        default=None,
        min_length=1,
        max_length=MAX_IMPOSSIBLE_REASON,
        description=(
            "ONLY when no one could do this with what is at hand (no spell, item or feature of"
            " the hero allows it): why, in a few words. Then no dice roll and dc_tier is"
            " ignored. Hard but possible is a high dc_tier, never this."
        ),
    )


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
    item: str | None = Field(
        default=None,
        max_length=64,
        description="the hero's own gear the effect uses, if any (it must be carried)",
    )
    reason: str = _reason()  # M20.1: the model sends one; it was refused as an extra input


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
    lock_tier: DcTier | None = Field(
        default=None, description="a lock on a cache, container or side door (never the main path)"
    )

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
    """Start a fight with catalogue monsters (CR budget enforced) and/or present NPCs. When the
    acting hero starts it by attacking a present NPC, also name that NPC in opening_strike_on and
    the attack they used in opening_attack: the engine rolls that attack before the first turn."""

    monster_ids: list[str] = Field(default_factory=list[str], max_length=8)
    terrain_tags: list[str] = Field(default_factory=list[str], max_length=3)
    surprise: SurpriseKind = SurpriseKind.NONE
    against_npcs: list[str] = Field(default_factory=list[str], max_length=4)
    opening_strike_on: str | None = Field(
        default=None,
        max_length=64,
        description="the NPC (one of against_npcs) the acting hero's attack opens on",
    )
    opening_attack: str | None = Field(
        default=None,
        max_length=64,
        description=(
            "the attack the hero named: a harmful spell id (fire-bolt, burning-hands),"
            " a carried scroll id (scroll-of-sleep: the engine reads it) or a"
            " weapon slot (main_hand, ranged, unarmed); empty = main weapon"
        ),
    )

    @model_validator(mode="after")
    def _someone(self) -> Self:
        if not self.monster_ids and not self.against_npcs:
            raise ValueError("name at least one monster id or NPC")
        if self.opening_strike_on is not None and self.opening_strike_on not in self.against_npcs:
            raise ValueError("opening_strike_on must be one of against_npcs")
        return self


class OpenShopArgs(_Args):
    """Open a present NPC's shop."""

    npc: str = _id()


class UpdateQuestArgs(_Args):
    """Mark the CURRENT step of an active quest done when it is a free step (listed in QUESTS as
    'judged by you') and the party really did it. Every other step is checked by the engine, and
    this never creates a quest (a present NPC who asks for help: offer_favour)."""

    quest_id: str = _id()
    route_id: str | None = Field(
        default=None, max_length=40, description="for a main quest: the known way followed"
    )
    reason: str = _reason()


class FavourKind(StrEnum):
    VISIT = "visit"
    CLEAR = "clear"
    DEFEAT = "defeat"
    DELIVER = "deliver"
    MEET = "meet"
    WIN_OVER = "win_over"
    LEARN = "learn"
    PAY = "pay"


class OfferFavourArgs(_Args):
    """A present NPC asks the party a small favour (only when they really ask for help). One
    step the engine can check: visit or clear a place (place), defeat, meet or win over an NPC
    (target_npc; win_over also band), deliver a keepsake a hero carries to an NPC (item,
    target_npc), learn something (tag), or pay an NPC, the asker too (target_npc, gold).
    Ids from this region only. The players accept or not; the engine adds the report back to
    the asker. It earns that NPC's goodwill, never gold or XP: the asker promises no reward.
    Any errand, job or task an NPC sets is this tool, never prose alone (a parcel to carry:
    give_keepsake it, then a deliver favour)."""

    npc: str = _id()
    title: str = Field(min_length=1, max_length=60)
    kind: FavourKind
    text: str = Field(min_length=1, max_length=MAX_STEP_TEXT, description="the step, in words")
    place: str | None = Field(default=None, max_length=64)
    target_npc: str | None = Field(default=None, max_length=64)
    item: str | None = Field(default=None, max_length=MAX_KEEPSAKE_NAME)
    band: AttitudeBand | None = None
    tag: str | None = Field(default=None, max_length=MAX_TAG)
    gold: int | None = Field(default=None, ge=1, le=MAX_STEP_GOLD, description="pay: the price")


class RecordFactArgs(_Args):
    """Write one fact to the ledger, tagged with the ids of known entities."""

    text: str = Field(min_length=1, max_length=300)
    entity_ids: list[str] = Field(default_factory=list[str], max_length=8)
    tags: list[str] = Field(default_factory=list[str], max_length=8)


class TakeItemArgs(_Args):
    """The acting hero picks up a visible item lying here (an id from the manifest's items)."""

    item_id: str = _id()


class GiveKeepsakeArgs(_Args):
    """Hand the acting hero a story object they found or were given (a note, a key, a trinket,
    a map scrap): it has no gold value and cannot be sold. Use it whenever the hero takes such a
    thing, so it is really carried."""

    name: str = Field(min_length=1, max_length=40)
    description: str = Field(default="", max_length=200)
    teaches: str | None = Field(
        default=None,
        max_length=24,
        description="only when the object tells what an open 'Learn about <tag>' step asks: "
        "that tag (a note, a letter, a carving); otherwise leave it out",
    )


class UseItemArgs(_Args):
    """A hero uses gear they carry (torch, lantern, rope, crowbar, thieves' tools, a kit, a
    flask, a scroll): the engine checks the gear, the place and the cost, rolls what needs a
    roll and applies the effect. Gear advantage comes ONLY from this tool, never from the
    advantage flag of request_check. put_out=true puts out the hero's carried light (free)."""

    actor: str = _id()
    item: str = Field(min_length=1, max_length=64, description="catalogue id or gear name")
    target: str | None = Field(
        default=None,
        max_length=64,
        description="the feature id (a lock), creature id or fight zone id it is used on",
    )
    put_out: bool = False


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
    _def("offer_favour", OfferFavourArgs),
    _def("record_fact", RecordFactArgs),
    _def("take_item", TakeItemArgs),
    _def("give_keepsake", GiveKeepsakeArgs),
    _def("use_item", UseItemArgs),
    _def("no_mechanics", NoMechanicsArgs),
)
_BY_NAME = {d.name: d for d in DM_TOOLS}


def dm_tool(name: str) -> ToolDef:
    return _BY_NAME[name]


def dm_tools_param(names: Sequence[str] | None = None) -> list[dict[str, Any]]:
    chosen = DM_TOOLS if names is None else tuple(_BY_NAME[n] for n in names)
    return [tool_param(d) for d in chosen]
