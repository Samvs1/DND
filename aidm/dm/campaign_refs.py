"""Repair of a campaign draft's catalogue and name references before assembly (M35.4, Y20).

Round 6 threw a whole campaign away for one leftover problem ("'lizardfolk' is tier 1, the
region is tier 2") and played the sample instead. The engine owns the catalogue, so a reference
it can check it can also fix deterministically. Each fix appends a `plan_repair` note to
`repairs` (the generator logs them on the session "campaign" line):
- an encounter theme that is unknown or of another tier -> the best catalogue monster of the
  region tier (same role, then the same creature type, then the most terrains shared with the
  place, then id order), never one the place already fights;
- a spoke left without a theme gets one; the arrival's themes are cleared (it is the safe place);
- a boss that is unknown, of another tier's CR or too dangerous (`master_too_dangerous`) -> the
  best master of the tier by the same order (never a minion);
- an unknown terrain tag is dropped (a place left without one takes the region's, a region its
  places', last the first catalogue terrain);
- an unknown NPC archetype -> its slug when that is a stat block, else `commoner`;
- an NPC home place that names no place -> the arrival of the act they give a quest in (act 1);
- a quest whose giver names no NPC is dropped (side quests are optional).
Structure (act count, spokes, the draft schema) is not repaired here: the schema rejects it.

Public API: `repair_draft_refs(draft, repairs) -> CampaignDraft` (a copy; `draft` is untouched).
"""

from __future__ import annotations

import functools
import re

from aidm.data.encounter_monsters import EncounterMonster, encounter_monsters
from aidm.data.srd import srd
from aidm.data.zone_templates import zone_templates
from aidm.dm.campaign_draft import (
    ActDraft,
    CampaignDraft,
    NodeDraft,
    NpcDraft,
    QuestDraft,
    RegionDraft,
)
from aidm.dm.campaign_draft_base import name_key, resolve_name
from aidm.models.problem import Problem
from aidm.rules.campaign_check import master_too_dangerous

DEFAULT_ARCHETYPE = "commoner"
MAX_NODE_TERRAINS = 3
MAX_REGION_TERRAINS = 4


def _note(owner: str, message: str) -> Problem:
    return Problem(code="plan_repair", message=f"{owner}: {message}", subject=owner)


def _kind(monster_id: str) -> str | None:
    monster = srd().monsters.find(monster_id)
    return monster.type if monster is not None else None


@functools.cache
def _unfit_masters(tier: int) -> frozenset[str]:
    entries = encounter_monsters().filter(lambda m: m.tier == tier)
    return frozenset(m.index for m in entries if master_too_dangerous(m.index, tier))


def _pick(tier: int, wanted: str, terrains: list[str], avoid: set[str], *, boss: bool) -> str:
    """The catalogue monster of `tier` closest to `wanted` for a place of `terrains`."""
    found = encounter_monsters().find(wanted)
    role = found.role if found is not None else None
    kind = _kind(wanted)
    tags = set(terrains)

    def fits(m: EncounterMonster) -> bool:
        if m.tier != tier or m.index in avoid:
            return False
        return not boss or (m.role != "minion" and m.index not in _unfit_masters(tier))

    def rank(m: EncounterMonster) -> tuple[bool, bool, int, str]:
        return (m.role != role, _kind(m.index) != kind, -len(tags & set(m.tags)), m.index)

    pool = encounter_monsters().filter(fits) or encounter_monsters().filter(
        lambda m: m.tier == tier
    )
    return min(pool, key=rank).index


def _theme_ok(monster_id: str, tier: int) -> bool:
    entry = encounter_monsters().find(monster_id)
    return entry is not None and entry.tier == tier


def _themes(node: NodeDraft, tier: int, *, spoke: bool, notes: list[Problem]) -> list[str]:
    kept: list[str] = []
    for monster_id in node.encounter_themes:
        if _theme_ok(monster_id, tier):
            kept.append(monster_id)
            continue
        swap = _pick(tier, monster_id, node.terrain_tags, set(kept), boss=False)
        notes.append(
            _note(node.name, f"{monster_id!r} is no tier {tier} monster: {swap!r} instead")
        )
        kept.append(swap)
    if spoke and not kept:
        kept.append(_pick(tier, "", node.terrain_tags, set(), boss=False))
        notes.append(_note(node.name, f"a spoke needs a fight: {kept[0]!r}"))
    return kept


def _known(tags: list[str]) -> list[str]:
    known = zone_templates()
    return [t for t in tags if t in known]


def _node(
    node: NodeDraft, tier: int, region_tags: list[str], role: str, notes: list[Problem]
) -> NodeDraft:
    tags = _known(node.terrain_tags) or region_tags[:MAX_NODE_TERRAINS]
    if tags != node.terrain_tags:
        notes.append(_note(node.name, f"terrain {node.terrain_tags} -> {tags}"))
    placed = node.model_copy(update={"terrain_tags": tags})
    if role == "arrival":
        if node.encounter_themes:
            notes.append(_note(node.name, "the arrival is safe: its fights were removed"))
        return placed.model_copy(update={"encounter_themes": []})
    themes = _themes(placed, tier, spoke=role == "spoke", notes=notes)
    return placed.model_copy(update={"encounter_themes": themes})


def _region_tags(region: RegionDraft) -> list[str]:
    own = _known(region.terrain_tags)
    if own:
        return own
    places = [t for n in (region.arrival, *region.spokes, region.gateway) for t in n.terrain_tags]
    from_places = list(dict.fromkeys(_known(places)))[:MAX_REGION_TERRAINS]
    return from_places or [sorted(t.index for t in zone_templates().all())[0]]


def _boss_ok(monster_id: str, tier: int) -> bool:
    entry = encounter_monsters().find(monster_id)
    return entry is not None and entry.tier == tier and monster_id not in _unfit_masters(tier)


def _region(region: RegionDraft, tier: int, notes: list[Problem]) -> RegionDraft:
    tags = _region_tags(region)
    if tags != region.terrain_tags:
        notes.append(_note(region.name, f"terrain {region.terrain_tags} -> {tags}"))
    arrival = _node(region.arrival, tier, tags, "arrival", notes)
    spokes = [_node(s, tier, tags, "spoke", notes) for s in region.spokes]
    gateway = _node(region.gateway, tier, tags, "gateway", notes)
    boss = region.boss
    if not _boss_ok(boss.monster_id, tier):
        swap = _pick(tier, boss.monster_id, gateway.terrain_tags, set(), boss=True)
        notes.append(
            _note(boss.name, f"{boss.monster_id!r} cannot be a tier {tier} master: {swap!r}")
        )
        boss = boss.model_copy(update={"monster_id": swap})
    return region.model_copy(
        update={
            "terrain_tags": tags,
            "arrival": arrival,
            "spokes": spokes,
            "gateway": gateway,
            "boss": boss,
        }
    )


def _archetype(npc: NpcDraft, notes: list[Problem]) -> str:
    monsters = srd().monsters
    if npc.archetype_id in monsters:
        return npc.archetype_id
    slug = re.sub(r"[^a-z0-9]+", "-", npc.archetype_id.lower()).strip("-")
    chosen = slug if slug in monsters else DEFAULT_ARCHETYPE
    notes.append(_note(npc.name, f"archetype {npc.archetype_id!r} -> {chosen!r}"))
    return chosen


def _home(npc: NpcDraft, draft: CampaignDraft, places: dict[str, str], notes: list[Problem]) -> str:
    if resolve_name(places, npc.home_place) is not None:
        return npc.home_place
    acts = [q.act for q in draft.quests if name_key(q.giver) == name_key(npc.name)]
    home = draft.acts[(acts[0] if acts else 1) - 1].region.arrival.name
    notes.append(_note(npc.name, f"home {npc.home_place!r} is no place: lives at {home}"))
    return home


def _index(names: list[str]) -> dict[str, str]:
    index: dict[str, str] = {}
    for name in names:
        index.setdefault(name_key(name), name)
    return index


def _cast(draft: CampaignDraft, notes: list[Problem]) -> CampaignDraft:
    regions = [a.region for a in draft.acts]
    places = _index([n.name for r in regions for n in (r.arrival, *r.spokes, r.gateway)])
    npcs = [
        n.model_copy(
            update={
                "archetype_id": _archetype(n, notes),
                "home_place": _home(n, draft, places, notes),
            }
        )
        for n in draft.npcs
    ]
    people = _index([n.name for n in draft.npcs])
    quests: list[QuestDraft] = []
    for quest in draft.quests:
        if resolve_name(people, quest.giver) is None:
            notes.append(_note(quest.title, f"giver {quest.giver!r} is no NPC: quest dropped"))
            continue
        quests.append(quest)
    return draft.model_copy(update={"npcs": npcs, "quests": quests})


def repair_draft_refs(draft: CampaignDraft, repairs: list[Problem]) -> CampaignDraft:
    """A copy of `draft` whose catalogue and name references all resolve (notes in `repairs`)."""
    acts: list[ActDraft] = [
        a.model_copy(update={"region": _region(a.region, i + 1, repairs)})
        for i, a in enumerate(draft.acts)
    ]
    return _cast(draft.model_copy(update={"acts": acts}), repairs)
