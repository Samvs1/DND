"""The compact schema the campaign model fills, and its assembly into a `CampaignPlan` (M5.3).

The model writes names, flavour and choices only; code assigns every id (slugs of the names),
resolves cross-references written as names (an NPC's home place, a quest giver, a reveal
condition's quest) and builds the validated `CampaignPlan`. Anything that does not resolve or
validate becomes a `Problem`, which the generator feeds back on its retry.

Repair over reject (M16.1): every draft model trims over-long strings at a word boundary and
cuts over-long lists to the field's own `max_length` before validation (`fit_limits`); min
lengths, required fields and enums still reject. Names resolve leniently (`_Ids.resolve`):
the exact name first, then the one name that contains the written words (a quest against
"Skarn" finds "Skarn the Hollow"). A required reference (home place, quest giver) that still
does not resolve is a `Problem`; an optional one is dropped (a quest target or rival becomes
None, a secret whose quest or item is unknown reveals at a friendly attitude instead).

Public API:
- Draft models: `NodeDraft`, `BossDraft`, `RegionDraft`, `ActDraft`, `SecretDraft`, `NpcDraft`,
  `QuestDraft`, `CampaignDraft` (the `structured` schema).
- `assemble_plan(draft) -> CampaignPlan | list[Problem]`.
- `slug_id(name, taken) -> str`: a plan id for a display name, unique among `taken`.
- `trim_words(text, limit) -> str`; `fit_limits(data, limits) -> dict` (the repair step).
"""

from __future__ import annotations

import functools
import re
from collections.abc import Iterable, Mapping
from typing import Any

from pydantic import BaseModel, Field, ValidationError, model_validator

from aidm.models.campaign import CampaignPlan, RevealKind, RewardTier
from aidm.models.dm_tiers import AttitudeBand
from aidm.models.problem import Problem

MAX_VALIDATION_PROBLEMS = 12
TRIM_TAIL = " \t\n,;:-"
_LAST_SPACE = re.compile(r"\s\S*$")


def trim_words(text: str, limit: int) -> str:
    """`text` cut to at most `limit` characters at the last word boundary (hard cut if none)."""
    if len(text) <= limit:
        return text
    space = _LAST_SPACE.search(text[: limit + 1])
    head = text[: space.start()] if space is not None and space.start() > 0 else text[:limit]
    return head.rstrip(TRIM_TAIL) or text[:limit]


def fit_limits(data: Mapping[str, Any], limits: Mapping[str, int]) -> dict[str, Any]:
    """A copy of `data` whose strings and lists named in `limits` fit their maximum length."""
    out = dict(data)
    for name, limit in limits.items():
        value = out.get(name)
        if isinstance(value, str):
            out[name] = trim_words(value, limit)
        elif isinstance(value, list) and len(value) > limit:
            out[name] = value[:limit]
    return out


@functools.cache
def _max_lengths(model: type[BaseModel]) -> dict[str, int]:
    out: dict[str, int] = {}
    for name, info in model.model_fields.items():
        for meta in info.metadata:
            limit = getattr(meta, "max_length", None)
            if isinstance(limit, int):
                out[name] = limit
    return out


class _Draft(BaseModel):
    """Base of every draft model: over-long text and lists are repaired, not rejected."""

    @model_validator(mode="before")
    @classmethod
    def _fit(cls, data: Any) -> Any:
        if isinstance(data, Mapping):
            return fit_limits(data, _max_lengths(cls))
        return data


class NodeDraft(_Draft):
    """A place: arrival (safe, no encounter themes), spoke, or gateway (the boss's lair)."""

    name: str = Field(min_length=1, max_length=40)
    flavour: str = Field(min_length=1, max_length=200)
    terrain_tags: list[str] = Field(min_length=1, max_length=3)
    encounter_themes: list[str] = Field(default_factory=list[str], max_length=3)


class BossDraft(_Draft):
    monster_id: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=40)
    ally_path: str | None = Field(default=None, max_length=300)


class RegionDraft(_Draft):
    name: str = Field(min_length=1, max_length=40)
    flavour: str = Field(min_length=1, max_length=300)
    terrain_tags: list[str] = Field(min_length=1, max_length=4)
    arrival: NodeDraft
    spokes: list[NodeDraft] = Field(min_length=2, max_length=3)
    gateway: NodeDraft
    boss: BossDraft


class ActDraft(_Draft):
    title: str = Field(min_length=1, max_length=60)
    goal: str = Field(min_length=1, max_length=200)
    region: RegionDraft


class SecretDraft(_Draft):
    text: str = Field(min_length=1, max_length=300)
    reveal_kind: RevealKind
    band: AttitudeBand | None = None
    quest_title: str | None = Field(default=None, max_length=60)
    item: str | None = Field(default=None, max_length=60)
    fact_tag: str | None = Field(default=None, max_length=24)


class NpcDraft(_Draft):
    name: str = Field(min_length=1, max_length=40)
    role: str = Field(min_length=1, max_length=40)
    archetype_id: str = Field(min_length=1)
    demeanor: str = Field(min_length=1, max_length=80)
    motive: str = Field(min_length=1, max_length=200)
    home_place: str = Field(min_length=1, max_length=40, description="the name of a place")
    voice_tag: str = Field(default="", max_length=30)
    secrets: list[SecretDraft] = Field(default_factory=list[SecretDraft], max_length=2)


class QuestDraft(_Draft):
    title: str = Field(min_length=1, max_length=60)
    giver: str = Field(min_length=1, max_length=40, description="the NPC who gives it")
    objective: str = Field(min_length=1, max_length=200)
    reward_tier: RewardTier
    act: int = Field(ge=1, le=3)
    reward_item: str | None = Field(default=None, max_length=60)
    against: str | None = Field(
        default=None, max_length=40, description="an NPC the quest works against"
    )


class CampaignDraft(_Draft):
    """Submit the whole campaign plan."""

    title: str = Field(min_length=1, max_length=80)
    premise: str = Field(min_length=1, max_length=600)
    tone: str = Field(min_length=1, max_length=80)
    theme: str = Field(min_length=1, max_length=120)
    acts: list[ActDraft] = Field(min_length=3, max_length=3)
    npcs: list[NpcDraft] = Field(min_length=3, max_length=10)
    quests: list[QuestDraft] = Field(default_factory=list[QuestDraft], max_length=8)
    rival_name: str | None = Field(default=None, max_length=40)
    rival_hook: str | None = Field(default=None, max_length=200)


def slug_id(name: str, taken: Iterable[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:48] or "x"
    used = set(taken)
    candidate, n = base, 2
    while candidate in used:
        candidate, n = f"{base}-{n}", n + 1
    return candidate


def _key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()


def _contains(key: str, written: str) -> bool:
    """True when the name `key` holds every word of `written` in order, as whole words."""
    return bool(written) and f" {written} " in f" {key} "


def _short(written: str) -> str:
    return written.removeprefix("the ") if written != "the" else written


class _Ids:
    """Id assignment and name -> id lookups shared by the assembly steps."""

    def __init__(self) -> None:
        self.taken: set[str] = set()
        self.nodes: dict[str, str] = {}
        self.npcs: dict[str, str] = {}
        self.quests: dict[str, str] = {}
        self.items: dict[str, str] = {}
        self.bosses: set[str] = set()
        self.problems: list[Problem] = []

    def new(self, name: str, index: dict[str, str] | None = None) -> str:
        new_id = slug_id(name, self.taken)
        self.taken.add(new_id)
        if index is not None:
            index.setdefault(_key(name), new_id)
        return new_id

    def resolve(
        self, index: Mapping[str, str], name: str, rivals: Iterable[str] = ()
    ) -> str | None:
        """The exact name, else the one name (of `index` or `rivals`) holding the written words."""
        key = _key(name)
        if key in index:
            return index[key]
        written = _short(key)
        hits = {v for k, v in index.items() if _contains(k, written)}
        if len(hits) != 1 or any(_contains(r, written) for r in rivals):
            return None
        return hits.pop()

    def find(self, index: dict[str, str], name: str, what: str, owner: str) -> str:
        """A required reference: unresolved names become a `Problem`."""
        found = self.resolve(index, name)
        if found is None:
            msg = f"{owner}: {what} {name!r} is not one of the names you defined"
            self.problems.append(Problem(code="unknown_reference", message=msg, subject=owner))
            return "missing"
        return found


def _node(ids: _Ids, node: NodeDraft) -> dict[str, Any]:
    return {
        "id": ids.new(node.name, ids.nodes),
        "name": node.name,
        "flavour": node.flavour,
        "terrain_tags": node.terrain_tags,
        "encounter_themes": node.encounter_themes,
    }


def _act(ids: _Ids, index: int, act: ActDraft) -> dict[str, Any]:
    reg = act.region
    nodes = [_node(ids, n) for n in (reg.arrival, *reg.spokes, reg.gateway)]
    boss = {"monster_id": reg.boss.monster_id, "name": reg.boss.name, "lair_node": nodes[-1]["id"]}
    ids.bosses.add(_key(reg.boss.name))
    if reg.boss.ally_path:
        boss["ally_path"] = reg.boss.ally_path
    region = {
        "id": ids.new(reg.name),
        "name": reg.name,
        "flavour": reg.flavour,
        "tier": index,
        "terrain_tags": reg.terrain_tags,
        "arrival": nodes[0],
        "spokes": nodes[1:-1],
        "gateway": nodes[-1],
        "boss": boss,
    }
    return {"index": index, "title": act.title, "goal": act.goal, "region": region}


FRIENDLY_REVEAL = {"kind": RevealKind.ATTITUDE.value, "band": AttitudeBand.FRIENDLY.value}


def _reveal(ids: _Ids, secret: SecretDraft) -> dict[str, Any]:
    """The reveal condition; an unknown quest or item (or an empty fact) reveals when friendly."""
    kind = secret.reveal_kind
    if kind is RevealKind.ATTITUDE:
        band = secret.band if secret.band not in (None, AttitudeBand.HOSTILE) else None
        return {"kind": kind.value, "band": (band or AttitudeBand.FRIENDLY).value}
    if kind is RevealKind.QUEST_COMPLETED:
        field, ref = "quest_id", ids.resolve(ids.quests, secret.quest_title or "")
    elif kind is RevealKind.ITEM_SHOWN:
        field, ref = "item", ids.resolve(ids.items, secret.item or "")
    else:
        field, ref = "fact_tag", (secret.fact_tag or "").strip().lower() or None
    return {"kind": kind.value, field: ref} if ref is not None else dict(FRIENDLY_REVEAL)


def _secret(ids: _Ids, npc_id: str, n: int, secret: SecretDraft) -> dict[str, Any]:
    return {"id": f"{npc_id}-secret-{n}", "text": secret.text, "reveal": _reveal(ids, secret)}


def _npc(ids: _Ids, npc_id: str, npc: NpcDraft) -> dict[str, Any]:
    return {
        "id": npc_id,
        "name": npc.name,
        "role": npc.role,
        "archetype_id": npc.archetype_id,
        "demeanor": npc.demeanor,
        "motive": npc.motive,
        "voice_tag": npc.voice_tag,
        "home_node": ids.find(ids.nodes, npc.home_place, "place", npc_id),
        "secrets": [_secret(ids, npc_id, i + 1, s) for i, s in enumerate(npc.secrets)],
    }


def _quest(ids: _Ids, quest_id: str, quest: QuestDraft) -> dict[str, Any]:
    return {
        "id": quest_id,
        "title": quest.title,
        "giver_npc_id": ids.find(ids.npcs, quest.giver, "quest giver", quest_id),
        "objective": quest.objective,
        "reward_tier": quest.reward_tier,
        "act": quest.act,
        "reward_item": quest.reward_item,
        "against_npc_id": ids.resolve(ids.npcs, quest.against or "", ids.bosses),
    }


def _validation_problems(exc: ValidationError) -> list[Problem]:
    out: list[Problem] = []
    for err in exc.errors()[:MAX_VALIDATION_PROBLEMS]:
        where = ".".join(str(p) for p in err["loc"])
        out.append(Problem(code="invalid_plan", message=f"{where}: {err['msg']}", subject=where))
    return out


def _rival(ids: _Ids, draft: CampaignDraft) -> dict[str, Any] | None:
    if not draft.rival_name:
        return None
    npc_id = ids.resolve(ids.npcs, draft.rival_name, ids.bosses)
    if npc_id is None:
        return None
    return {"npc_id": npc_id, "hook": draft.rival_hook or "A rival of the party."}


def assemble_plan(draft: CampaignDraft) -> CampaignPlan | list[Problem]:
    ids = _Ids()
    acts = [_act(ids, i + 1, a) for i, a in enumerate(draft.acts)]
    npc_ids = [ids.new(n.name, ids.npcs) for n in draft.npcs]
    quest_ids = [ids.new(q.title, ids.quests) for q in draft.quests]
    ids.items = {_key(q.reward_item): q.reward_item for q in draft.quests if q.reward_item}
    raw = {
        "title": draft.title,
        "premise": draft.premise,
        "tone": draft.tone,
        "theme": draft.theme,
        "acts": acts,
        "npcs": [_npc(ids, i, n) for i, n in zip(npc_ids, draft.npcs, strict=True)],
        "quests": [_quest(ids, i, q) for i, q in zip(quest_ids, draft.quests, strict=True)],
        "rival": _rival(ids, draft),
    }
    if ids.problems:
        return ids.problems
    try:
        return CampaignPlan.model_validate(raw)
    except ValidationError as exc:
        return _validation_problems(exc)
