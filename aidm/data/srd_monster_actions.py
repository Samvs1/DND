"""Typed pieces of an SRD monster's action economy (5e-bits 2014 format).

Everything the v1 library dropped is kept here: breath-weapon DCs, recharge
usage, multiattack parts, nested damage choices, legendary actions, reactions
and per-spell usage on spell kits.
"""

from __future__ import annotations

from typing import Any

from pydantic import JsonValue, model_validator

from aidm.data.srd_common import ApiRef, SrdModel


class ActionDc(SrdModel):
    dc_type: ApiRef
    dc_value: int
    success_type: str


class ActionUsage(SrdModel):
    """`type` is "recharge on roll" (dice, min_value), "per day" (times),
    "recharge after rest" (rest_types) or "at will"."""

    type: str
    times: int | None = None
    dice: str | None = None
    min_value: int | None = None
    rest_types: list[str] = []


class ActionDamage(SrdModel):
    """One damage block, or a `choose` block whose options are flattened.

    The SRD stores a choice as {choose, type, from: {options: [...]}}. Here
    `choose` is the count to pick and `options` holds the alternatives; plain
    blocks have a `damage_type`/`damage_dice` and an optional rider `dc`.
    """

    damage_type: ApiRef | None = None
    damage_dice: str | None = None
    dc: ActionDc | None = None
    choose: int | None = None
    options: list[ActionDamage] = []

    @model_validator(mode="before")
    @classmethod
    def _flatten_choice(cls, data: Any) -> Any:
        if isinstance(data, dict) and "from" in data:
            body: dict[str, Any] = {k: v for k, v in data.items() if k not in ("from", "type")}
            body["options"] = data["from"].get("options", [])
            return body
        return data


class MultiattackPart(SrdModel):
    action_name: str
    count: int | str
    type: str


class ActionAttack(SrdModel):
    """A named sub-attack (e.g. a sphinx's First/Second/Third Roar)."""

    name: str
    dc: ActionDc | None = None
    damage: list[ActionDamage] = []


class BreathOption(SrdModel):
    """One breath weapon from a "Breath Weapons" choice action."""

    name: str
    dc: ActionDc | None = None
    damage: list[ActionDamage] = []


class MonsterAction(SrdModel):
    name: str
    desc: str
    attack_bonus: int | None = None
    dc: ActionDc | None = None
    damage: list[ActionDamage] = []
    usage: ActionUsage | None = None
    multiattack_type: str | None = None
    actions: list[MultiattackPart] = []
    attacks: list[ActionAttack] = []
    options: JsonValue | None = None
    action_options: JsonValue | None = None

    @property
    def breath_options(self) -> list[BreathOption]:
        """Breath weapons nested in the `options` blob (dual-breath dragons)."""
        opts = self.options
        if not isinstance(opts, dict):
            return []
        source = opts.get("from")
        items = source.get("options") if isinstance(source, dict) else None
        if not isinstance(items, list):
            return []
        return [
            BreathOption.model_validate(o)
            for o in items
            if isinstance(o, dict) and o.get("option_type") == "breath"
        ]


class LegendaryAction(SrdModel):
    name: str
    desc: str
    attack_bonus: int | None = None
    dc: ActionDc | None = None
    damage: list[ActionDamage] = []


class MonsterReaction(SrdModel):
    name: str
    desc: str
    dc: ActionDc | None = None


class MonsterSpell(SrdModel):
    name: str
    level: int
    url: str
    usage: ActionUsage | None = None
    notes: str | None = None


class Spellcasting(SrdModel):
    ability: ApiRef
    dc: int | None = None
    modifier: int | None = None
    level: int | None = None
    school: str | None = None
    slots: dict[str, int] = {}
    spells: list[MonsterSpell] = []
    components_required: list[str] = []


class SpecialAbility(SrdModel):
    name: str
    desc: str
    dc: ActionDc | None = None
    damage: list[ActionDamage] = []
    usage: ActionUsage | None = None
    spellcasting: Spellcasting | None = None
