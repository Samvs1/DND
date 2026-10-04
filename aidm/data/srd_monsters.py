"""Typed SRD monster entries (data/srd/monsters.json, 5e-bits 2014 format)."""

from __future__ import annotations

from aidm.data.srd_common import ApiRef, SrdModel
from aidm.data.srd_monster_actions import (
    LegendaryAction,
    MonsterAction,
    MonsterReaction,
    SpecialAbility,
    Spellcasting,
)


class MonsterArmorClass(SrdModel):
    """`type` is natural, armor, dex, spell, condition...; the matching ref
    field (`armor`, `spell`, `condition`) is set when relevant."""

    type: str
    value: int
    armor: list[ApiRef] = []
    spell: ApiRef | None = None
    condition: ApiRef | None = None
    desc: str | None = None


class MonsterSpeed(SrdModel):
    walk: str | None = None
    fly: str | None = None
    swim: str | None = None
    climb: str | None = None
    burrow: str | None = None
    hover: bool | None = None


class MonsterSenses(SrdModel):
    darkvision: str | None = None
    blindsight: str | None = None
    tremorsense: str | None = None
    truesight: str | None = None
    passive_perception: int


class MonsterProficiency(SrdModel):
    value: int
    proficiency: ApiRef


class SrdMonster(SrdModel):
    index: str
    name: str
    desc: str | None = None
    size: str
    type: str
    subtype: str | None = None
    alignment: str
    armor_class: list[MonsterArmorClass]
    hit_points: int
    hit_dice: str
    hit_points_roll: str
    speed: MonsterSpeed
    strength: int
    dexterity: int
    constitution: int
    intelligence: int
    wisdom: int
    charisma: int
    proficiencies: list[MonsterProficiency] = []
    damage_vulnerabilities: list[str] = []
    damage_resistances: list[str] = []
    damage_immunities: list[str] = []
    condition_immunities: list[ApiRef] = []
    senses: MonsterSenses
    languages: str
    challenge_rating: float
    proficiency_bonus: int
    xp: int
    special_abilities: list[SpecialAbility] = []
    actions: list[MonsterAction] = []
    reactions: list[MonsterReaction] = []
    legendary_actions: list[LegendaryAction] = []
    forms: list[ApiRef] = []
    image: str | None = None
    url: str | None = None

    @property
    def ac(self) -> int:
        """The first (primary) armor class value."""
        return self.armor_class[0].value

    @property
    def cr(self) -> float:
        return self.challenge_rating

    def ability_score(self, ability: str) -> int:
        scores = {
            "str": self.strength,
            "dex": self.dexterity,
            "con": self.constitution,
            "int": self.intelligence,
            "wis": self.wisdom,
            "cha": self.charisma,
        }
        return scores[ability.lower()]

    def save_bonus(self, ability: str) -> int:
        """Saving-throw bonus: the listed proficiency value, else the ability modifier."""
        wanted = f"saving-throw-{ability.lower()}"
        for p in self.proficiencies:
            if p.proficiency.index == wanted:
                return p.value
        return (self.ability_score(ability) - 10) // 2

    @property
    def breath_weapons(self) -> list[MonsterAction]:
        """Every breath weapon with its DC, including ones nested in `options`."""
        found: list[MonsterAction] = []
        for action in self.actions:
            if "Breath" in action.name and action.dc is not None:
                found.append(action)
            for opt in action.breath_options:
                found.append(
                    MonsterAction(
                        name=opt.name,
                        desc=action.desc,
                        dc=opt.dc,
                        damage=opt.damage,
                        usage=action.usage,
                    )
                )
        return found

    @property
    def spellcasting(self) -> Spellcasting | None:
        for ability in self.special_abilities:
            if ability.spellcasting is not None:
                return ability.spellcasting
        return None

    @property
    def is_spellcaster(self) -> bool:
        return self.spellcasting is not None
