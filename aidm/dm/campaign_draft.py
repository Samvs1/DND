"""The compact schema the campaign model fills, and its assembly into a `CampaignPlan` (M5.3).

The model writes names, flavour and choices only; code assigns every id (slugs of the names),
resolves cross-references written as names (an NPC's home place, a quest giver, a reveal
condition's quest) and builds the validated `CampaignPlan`. Anything that does not resolve or
validate becomes a `Problem`, which the generator feeds back on its retry.

Public API:
- Draft models: `NodeDraft`, `BossDraft`, `RegionDraft`, `ActDraft`, `SecretDraft`, `NpcDraft`,
  `QuestDraft`, `CampaignDraft` (the `structured` schema).
- `assemble_plan(draft) -> CampaignPlan | list[Problem]`.
- `slug_id(name, taken) -> str`: a plan id for a display name, unique among `taken`.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from aidm.models.campaign import CampaignPlan, RevealKind, RewardTier
from aidm.models.dm_tiers import AttitudeBand
from aidm.models.problem import Problem

MAX_VALIDATION_PROBLEMS = 12


class NodeDraft(BaseModel):
    """A place: arrival (safe, no encounter themes), spoke, or gateway (the boss's lair)."""

    name: str = Field(min_length=1, max_length=40)
    flavour: str = Field(min_length=1, max_length=200)
    terrain_tags: list[str] = Field(min_length=1, max_length=3)
    encounter_themes: list[str] = Field(default_factory=list[str], max_length=3)


class BossDraft(BaseModel):
    monster_id: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=40)
    ally_path: str | None = Field(default=None, max_length=300)


class RegionDraft(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    flavour: str = Field(min_length=1, max_length=300)
    terrain_tags: list[str] = Field(min_length=1, max_length=4)
    arrival: NodeDraft
    spokes: list[NodeDraft] = Field(min_length=2, max_length=3)
    gateway: NodeDraft
    boss: BossDraft


class ActDraft(BaseModel):
    title: str = Field(min_length=1, max_length=60)
    goal: str = Field(min_length=1, max_length=200)
    region: RegionDraft


class SecretDraft(BaseModel):
    text: str = Field(min_length=1, max_length=300)
    reveal_kind: RevealKind
    band: AttitudeBand | None = None
    quest_title: str | None = None
    item: str | None = None


class NpcDraft(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    role: str = Field(min_length=1, max_length=40)
    archetype_id: str = Field(min_length=1)
    demeanor: str = Field(min_length=1, max_length=80)
    motive: str = Field(min_length=1, max_length=200)
    home_place: str = Field(min_length=1, description="the name of one of the places")
    voice_tag: str = Field(default="", max_length=30)
    secrets: list[SecretDraft] = Field(default_factory=list[SecretDraft], max_length=2)


class QuestDraft(BaseModel):
    title: str = Field(min_length=1, max_length=60)
    giver: str = Field(min_length=1, description="the name of the NPC who gives it")
    objective: str = Field(min_length=1, max_length=200)
    reward_tier: RewardTier
    act: int = Field(ge=1, le=3)
    reward_item: str | None = Field(default=None, max_length=60)


class CampaignDraft(BaseModel):
    """Submit the whole campaign plan."""

    title: str = Field(min_length=1, max_length=80)
    premise: str = Field(min_length=1, max_length=600)
    tone: str = Field(min_length=1, max_length=80)
    theme: str = Field(min_length=1, max_length=120)
    acts: list[ActDraft] = Field(min_length=3, max_length=3)
    npcs: list[NpcDraft] = Field(min_length=3, max_length=10)
    quests: list[QuestDraft] = Field(default_factory=list[QuestDraft], max_length=8)
    rival_name: str | None = None
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


class _Ids:
    """Id assignment and name -> id lookups shared by the assembly steps."""

    def __init__(self) -> None:
        self.taken: set[str] = set()
        self.nodes: dict[str, str] = {}
        self.npcs: dict[str, str] = {}
        self.quests: dict[str, str] = {}
        self.problems: list[Problem] = []

    def new(self, name: str, index: dict[str, str] | None = None) -> str:
        new_id = slug_id(name, self.taken)
        self.taken.add(new_id)
        if index is not None:
            index.setdefault(_key(name), new_id)
        return new_id

    def find(self, index: dict[str, str], name: str, what: str, owner: str) -> str:
        found = index.get(_key(name))
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


def _secret(ids: _Ids, npc_id: str, n: int, secret: SecretDraft) -> dict[str, Any]:
    reveal: dict[str, Any] = {"kind": secret.reveal_kind.value}
    if secret.reveal_kind is RevealKind.ATTITUDE:
        reveal["band"] = (secret.band or AttitudeBand.FRIENDLY).value
    elif secret.reveal_kind is RevealKind.QUEST_COMPLETED:
        title = secret.quest_title or ""
        reveal["quest_id"] = ids.find(ids.quests, title, "quest", npc_id)
    else:
        reveal["item"] = secret.item or ""
    return {"id": f"{npc_id}-secret-{n}", "text": secret.text, "reveal": reveal}


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
    npc_id = ids.find(ids.npcs, draft.rival_name, "rival", "rival")
    return {"npc_id": npc_id, "hook": draft.rival_hook or "A rival of the party."}


def assemble_plan(draft: CampaignDraft) -> CampaignPlan | list[Problem]:
    ids = _Ids()
    acts = [_act(ids, i + 1, a) for i, a in enumerate(draft.acts)]
    npc_ids = [ids.new(n.name, ids.npcs) for n in draft.npcs]
    quest_ids = [ids.new(q.title, ids.quests) for q in draft.quests]
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
