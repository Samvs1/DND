"""Typed SRD spell entries (data/srd/spells.json, 5e-bits 2014 format)."""

from __future__ import annotations

from aidm.data.srd_common import ApiRef, SrdModel


class SpellDamage(SrdModel):
    """One damage block; the SRD stores `damage` as a list of these."""

    damage_type: ApiRef | None = None
    damage_at_slot_level: dict[str, str] = {}
    damage_at_character_level: dict[str, str] = {}


class SpellDc(SrdModel):
    dc_type: ApiRef
    dc_success: str
    desc: str | None = None


class AreaOfEffect(SrdModel):
    type: str
    size: int


class SrdSpell(SrdModel):
    index: str
    name: str
    level: int
    school: ApiRef
    casting_time: str
    range: str
    duration: str
    concentration: bool
    ritual: bool
    components: list[str]
    material: str | None = None
    desc: list[str]
    higher_level: list[str] = []
    classes: list[ApiRef]
    subclasses: list[ApiRef] = []
    damage: list[SpellDamage] = []
    dc: SpellDc | None = None
    attack_type: str | None = None
    area_of_effect: AreaOfEffect | None = None
    heal_at_slot_level: dict[str, str] | None = None
