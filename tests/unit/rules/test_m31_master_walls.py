"""M31.1f master walls: a master's area damage spells count in the `boss_area` plan check.

The M31.1d grid wiped four-hero parties on the act-3 mage's Fireball (a party in one zone). A
breath weapon already kept a master out of a plan (M29.6b); a spell of the same strength did not.
SRD 5.1 Fireball: 3rd level, 8d6 fire in an area, Dexterity save for half: average 28. The mage
(CR 6, SRD 5.1) has slots 4/3/3/3/1 and Fireball on its list. Reference hit points per tier
(data/bg3/encounter_budget.json `area_reference_hp`): 17 / 23 / 29; the boss cap is medium (a
share below `area_damage_rating.hard` 0.6).
"""

from __future__ import annotations

from aidm.data.encounter_tables import encounter_tables
from aidm.data.spell_defs import spell_defs
from aidm.data.srd import srd
from aidm.data.srd_monsters import SrdMonster
from aidm.dm.campaign_gen import campaign_messages
from aidm.dm.campaign_sample import load_sample_campaign
from aidm.models.campaign import CampaignPlan
from aidm.models.encounter import Difficulty
from aidm.rules.campaign_check import check_plan_refs, master_too_dangerous
from aidm.rules.encounter_danger import area_damage, spell_area_damage, too_dangerous
from tests.session.playtest_saves import events_of, replay_until

MEDIUM = Difficulty.MEDIUM


def _mage() -> SrdMonster:
    return srd().monsters.get("mage")


def _without_slots_above(monster: SrdMonster, top: int) -> SrdMonster:
    abilities = []
    for ability in monster.special_abilities:
        kit = ability.spellcasting
        if kit is not None:
            slots = {k: v for k, v in kit.slots.items() if int(k) <= top}
            ability = ability.model_copy(
                update={"spellcasting": kit.model_copy(update={"slots": slots})}
            )
        abilities.append(ability)
    return monster.model_copy(update={"special_abilities": abilities})


def test_golden_m31_mage_fireball_area_damage() -> None:
    # SRD 5.1 Fireball 8d6 = (8 + 48) / 2 = 28; the mage has no breath or save action.
    assert spell_area_damage(_mage(), spell_defs()) == 28.0
    assert area_damage(_mage()) == 0.0  # without the spell registry: breath weapons only
    assert area_damage(_mage(), spell_defs()) == 28.0


def test_v1_m31_master_fireball_counts_as_area() -> None:
    # 28 / 29 = 0.97 of a tier-3 hero's hit points: deadly, above the medium boss cap.
    assert master_too_dangerous("mage", 3)
    raw = load_sample_campaign().model_dump(mode="json")
    raw["acts"][2]["region"]["boss"]["monster_id"] = "mage"
    codes = [p.code for p in check_plan_refs(CampaignPlan.model_validate(raw))]
    assert codes == ["boss_area"]


def test_m31_fireball_rated_by_the_heroes_hit_points() -> None:
    tables, spells = encounter_tables(), spell_defs()
    # Low-level heroes (17 hit points): 28 / 17 = 1.65 -> deadly, too dangerous for a master.
    assert too_dangerous(_mage(), 17, MEDIUM, tables, spells)
    # The same stat block against heroes of 80 hit points: 28 / 80 = 0.35 -> below medium.
    assert not too_dangerous(_mage(), 80, MEDIUM, tables, spells)


def test_m31_area_spell_needs_a_slot_of_its_level() -> None:
    # Without a 3rd-level slot or higher the mage cannot cast Fireball: no area damage.
    low = _without_slots_above(_mage(), 2)
    assert spell_area_damage(low, spell_defs()) == 0.0
    assert not too_dangerous(low, 17, MEDIUM, encounter_tables(), spell_defs())


def test_m31_area_spell_without_damage_is_not_a_blast() -> None:
    # The priest's Spirit Guardians is an area spell that lays a surface, not a damage roll.
    assert spell_area_damage(srd().monsters.get("priest"), spell_defs()) == 0.0
    assert not master_too_dangerous("priest", 2)


def test_m31_sample_campaign_still_validates_and_is_offered_without_the_mage() -> None:
    plan = load_sample_campaign()
    assert check_plan_refs(plan) == []
    assert plan.acts[2].region.boss.monster_id == "gladiator"
    prompt = campaign_messages(None, "four heroes")[1]["content"]
    assert "tier 3, never a boss (area attack or spell too strong):" in prompt
    tier3 = next(line for line in prompt.splitlines() if line.startswith("tier 3, never"))
    assert "mage" in tier3.split(": ", 1)[1].split(", ")


def test_m31_saved_plan_with_a_fireball_master_still_loads() -> None:
    # Round 4's quests save met the mage as its act-3 master: the check runs at plan creation,
    # never on load, so the save replays and keeps its master.
    last = max(e.seq for e in events_of("m31-r4-quests"))
    state = replay_until("m31-r4-quests", last + 1)
    assert state.campaign is not None
    bosses = [r.boss.monster_id for r in state.campaign.plan.all_regions()]
    assert "mage" in bosses
    assert "boss_area" in [p.code for p in check_plan_refs(state.campaign.plan)]
