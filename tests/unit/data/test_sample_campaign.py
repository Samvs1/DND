"""M5.1: the campaign plan schema and the built-in sample campaign."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from aidm.data.campaign_data import load_sample_campaign_json
from aidm.data.encounter_monsters import encounter_monsters, tier_for_cr
from aidm.data.srd import srd
from aidm.dm.campaign_sample import load_sample_campaign
from aidm.models.campaign import CampaignPlan, RevealKind
from aidm.rules.campaign_check import check_plan_refs

PLAN = load_sample_campaign()


def _raw() -> dict[str, Any]:
    return dict(load_sample_campaign_json())


def test_sample_campaign_validates() -> None:
    assert len(PLAN.acts) == 3
    assert [a.region.tier for a in PLAN.acts] == [1, 2, 3]
    assert PLAN.title and PLAN.premise and PLAN.tone and PLAN.theme


def test_sample_references_resolve_against_registries() -> None:
    assert check_plan_refs(PLAN) == []
    for npc in PLAN.npcs:
        assert npc.archetype_id in srd().monsters
    for region in PLAN.all_regions():
        assert region.boss.monster_id in encounter_monsters()
        for node in region.nodes():
            assert all(t in encounter_monsters() for t in node.encounter_themes)


def test_sample_boss_cr_fits_tier() -> None:
    for region in PLAN.all_regions():
        entry = encounter_monsters().get(region.boss.monster_id)
        assert tier_for_cr(entry.cr) == region.tier
        assert region.boss.defeat_always is True
        assert region.boss.lair_node == region.gateway.id


def test_sample_region_shape() -> None:
    for region in PLAN.all_regions():
        assert region.arrival.encounter_themes == ()
        assert 2 <= len(region.spokes) <= 3
        assert all(s.encounter_themes for s in region.spokes)
        assert len(region.nodes()) == len({n.id for n in region.nodes()}) == len(region.spokes) + 2


def test_sample_cast_secrets_and_quests() -> None:
    kinds = {s.reveal.kind for n in PLAN.npcs for s in n.secrets}
    assert kinds == set(RevealKind)
    assert sum(1 for r in PLAN.all_regions() if r.boss.ally_path) == 1
    assert PLAN.rival is not None
    assert {q.act for q in PLAN.quests} == {1, 2, 3}


def test_sample_names_are_original() -> None:
    text = str(load_sample_campaign_json()).lower()
    for banned in ("baldur", "faerun", "waterdeep", "neverwinter", "gale", "astarion"):
        assert banned not in text


def test_bad_reference_is_rejected() -> None:
    raw = _raw()
    raw["quests"] = [{**raw["quests"][0], "giver_npc_id": "nobody"}]
    with pytest.raises(ValidationError):
        CampaignPlan.model_validate(raw)


def test_duplicate_node_id_is_rejected() -> None:
    raw = _raw()
    raw["acts"][1]["region"]["arrival"]["id"] = raw["acts"][0]["region"]["arrival"]["id"]
    with pytest.raises(ValidationError):
        CampaignPlan.model_validate(raw)


def test_region_needs_two_spokes_and_a_safe_arrival() -> None:
    raw = _raw()
    raw["acts"][0]["region"]["spokes"] = raw["acts"][0]["region"]["spokes"][:1]
    with pytest.raises(ValidationError):
        CampaignPlan.model_validate(raw)
    raw = _raw()
    raw["acts"][0]["region"]["arrival"]["encounter_themes"] = ["goblin"]
    with pytest.raises(ValidationError):
        CampaignPlan.model_validate(raw)


def test_wrong_tier_boss_and_unknown_monster_are_reported() -> None:
    raw = _raw()
    raw["acts"][0]["region"]["boss"]["monster_id"] = "mage"
    raw["acts"][1]["region"]["spokes"][0]["encounter_themes"] = ["not-a-monster"]
    raw["npcs"][0]["archetype_id"] = "not-an-archetype"
    codes = {p.code for p in check_plan_refs(CampaignPlan.model_validate(raw))}
    assert codes == {"boss_tier", "unknown_monster", "unknown_archetype"}


def test_defeat_cannot_be_disabled() -> None:
    raw = _raw()
    raw["acts"][0]["region"]["boss"]["defeat_always"] = False
    with pytest.raises(ValidationError):
        CampaignPlan.model_validate(raw)
