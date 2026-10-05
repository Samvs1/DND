"""A monster's action catalog, derived purely from its SRD stat block (M3.8, SPEC 7.4 Monsters).

`monster_catalog(monster, overlay, shipped)` turns the stat block (plus the prose mechanics of
`aidm.data.monster_overlay`) into the options a monster can use, each an existing engine shape:
- "attack": a weapon or natural attack (`melee` and/or `ranged` `AttackProfile`, extra typed
  damage parts, optional `on_hit` riders: a pseudo spell run with `dc`, skipped against
  `exempt` creature types or races). Executed through THE attack path.
- "save": a save action (breath weapon, wing beat): `save` is a pseudo spell (area or creature
  targeting, DC `dc`) run by THE spell interpreter; dual breath weapons ("Breath Weapons" with
  options) become one option per breath sharing the parent's recharge resource.
- "multiattack": `routines` (one per SRD choice; "actions" multiattacks have one), each a
  sequence of `MultiattackStep(action, mode)` naming attack options; a step of type "ability"
  that is not an attack (Frightful Presence) is skipped, a routine with any other unknown step
  is dropped. A multiattack costs the action once.
- "spell": "spell:<index>" for every spell of the spell kits that is shipped in the DSL
  (`MonsterSpell` numbers: the kit's DC and attack bonus, slots or innate uses).
`resource` names the pool an option spends (`rules.monster_keys`), `cost` the legendary points.
Legendary actions (`legendary`): an own attack, a reference to an attack option ("makes a tail
attack", "makes one attack with its hooves"), or a save action; their keys drop the cost suffix.
Anything not expressible is listed by name in `unsupported` (the M3.9 readiness checklist reads
it). Unshipped spells appear as "spell <index>".

Public API: `MultiattackStep`, `MonsterOption`, `MonsterSpell`, `MonsterCatalog` (`option(key)`,
`legendary_option(key)`, `spell(index)`), `monster_catalog(monster, overlay, shipped)`,
`monster_spells(monster) -> tuple[MonsterSpell, ...]`, `SPELL_PREFIX` ("spell:").
"""

from collections.abc import Container, Sequence
from dataclasses import dataclass, replace
from typing import Any, Literal, cast

from aidm.data.monster_overlay import MonsterOverlay
from aidm.data.spell_defs import SpellDef
from aidm.data.srd_monster_actions import ActionDamage, ActionDc, MonsterAction, MultiattackPart
from aidm.data.srd_monsters import SrdMonster
from aidm.models.combat import AttackProfile
from aidm.rules.abilities import ability_modifier
from aidm.rules.monster_keys import (
    AT_WILL,
    ability_slug,
    legendary_cost,
    spell_index,
    usage_resource,
)
from aidm.rules.monster_parse import attack_profiles, flat_parts, on_hit_spell, save_spell

SPELL_PREFIX = "spell:"
type OptionShape = Literal["attack", "save", "multiattack", "spell"]
type StepMode = Literal["melee", "ranged", "any"]


@dataclass(frozen=True)
class MultiattackStep:
    action: str
    mode: StepMode = "any"


@dataclass(frozen=True)
class MonsterOption:
    key: str
    name: str
    shape: OptionShape
    melee: AttackProfile | None = None
    ranged: AttackProfile | None = None
    on_hit: SpellDef | None = None
    save: SpellDef | None = None
    dc: int = 0
    exempt: tuple[str, ...] = ()
    routines: tuple[tuple[MultiattackStep, ...], ...] = ()
    resource: str | None = None
    cost: int = 1


@dataclass(frozen=True)
class MonsterSpell:
    index: str
    name: str
    level: int
    resource: str | None
    save_dc: int
    attack_bonus: int
    modifier: int
    caster_level: int


@dataclass(frozen=True)
class MonsterCatalog:
    monster: str
    options: tuple[MonsterOption, ...]
    legendary: tuple[MonsterOption, ...]
    spells: tuple[MonsterSpell, ...]
    unsupported: tuple[str, ...]

    def option(self, key: str) -> MonsterOption | None:
        return next((o for o in self.options if o.key == key), None)

    def legendary_option(self, key: str) -> MonsterOption | None:
        return next((o for o in self.legendary if o.key == key), None)

    def spell(self, index: str) -> MonsterSpell | None:
        return next((s for s in self.spells if s.index == index), None)


@dataclass(frozen=True)
class _Block:
    """The fields shared by actions, breath options and legendary actions."""

    name: str
    desc: str
    attack_bonus: int | None
    dc: ActionDc | None
    damage: Sequence[ActionDamage]


def _option(
    monster: SrdMonster, block: _Block, overlay: MonsterOverlay, resource: str | None
) -> MonsterOption | None:
    key = ability_slug(block.name)
    extra = overlay.for_action(monster.index, key)
    parts = flat_parts(block.damage)
    if block.attack_bonus is not None:
        melee, ranged = attack_profiles(key, block.name, block.desc, block.attack_bonus, parts)
        if melee is None and ranged is None:
            return None
        rider, dc = on_hit_spell(key, parts, extra)
        exempt = extra.exempt_types if extra is not None else ()
        return MonsterOption(
            key=key,
            name=block.name,
            shape="attack",
            melee=melee,
            ranged=ranged,
            on_hit=rider,
            dc=dc,
            exempt=exempt,
            resource=resource,
        )
    if block.dc is None:
        return None
    save = save_spell(key, block.desc, block.dc, parts, extra)
    if save is None:
        return None
    return MonsterOption(
        key, block.name, "save", save=save, dc=block.dc.dc_value, resource=resource
    )


def _action_options(
    monster: SrdMonster, action: MonsterAction, overlay: MonsterOverlay, unsupported: list[str]
) -> list[MonsterOption]:
    usage = usage_resource(ability_slug(action.name), action.usage)
    resource = usage[0] if usage else None
    blocks = [_Block(b.name, action.desc, None, b.dc, b.damage) for b in action.breath_options] or [
        _Block(action.name, action.desc, action.attack_bonus, action.dc, action.damage)
    ]
    found: list[MonsterOption] = []
    for block in blocks:
        option = _option(monster, block, overlay, resource)
        if option is None:
            unsupported.append(block.name)
        else:
            found.append(option)
    return found


def _dicts(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    items = cast(list[object], value)
    return [cast(dict[str, Any], item) for item in items if isinstance(item, dict)]


def _choices(action: MonsterAction) -> list[list[MultiattackPart]]:
    if action.multiattack_type != "action_options":
        return [list(action.actions)] if action.actions else []
    source = action.action_options
    picks = source.get("from") if isinstance(source, dict) else None
    routines: list[list[MultiattackPart]] = []
    for choice in _dicts(picks.get("options") if isinstance(picks, dict) else None):
        items = _dicts(choice.get("items")) if choice.get("option_type") == "multiple" else [choice]
        routines.append([MultiattackPart.model_validate(i) for i in items])
    return routines


def _count(text: str) -> int:
    return int(text) if text.isdigit() else 1


def _routine(
    parts: Sequence[MultiattackPart], attacks: dict[str, MonsterOption]
) -> tuple[MultiattackStep, ...] | None:
    steps: list[MultiattackStep] = []
    for part in parts:
        option = attacks.get(part.action_name.lower())
        if option is None:
            if part.type == "ability":
                continue
            return None
        count = part.count if isinstance(part.count, int) else _count(part.count)
        mode: StepMode = "ranged" if part.type == "ranged" else "melee"
        steps.extend([MultiattackStep(option.key, mode)] * max(1, count))
    return tuple(steps) or None


def _multiattack(action: MonsterAction, options: Sequence[MonsterOption]) -> MonsterOption | None:
    attacks = {o.name.lower(): o for o in options if o.shape == "attack"}
    routines = [_routine(parts, attacks) for parts in _choices(action)]
    valid = tuple(r for r in routines if r is not None)
    if not valid:
        return None
    return MonsterOption(ability_slug(action.name), action.name, "multiattack", routines=valid)


def _legendary(
    monster: SrdMonster, options: Sequence[MonsterOption], overlay: MonsterOverlay
) -> tuple[list[MonsterOption], list[str]]:
    found: list[MonsterOption] = []
    missing: list[str] = []
    for action in monster.legendary_actions:
        key, cost, text = (
            ability_slug(action.name),
            legendary_cost(action.name),
            action.desc.lower(),
        )
        ref = next(
            (
                o
                for o in options
                if o.shape == "attack"
                and (
                    f"{o.name.lower()} attack" in text
                    or f"attack with its {o.name.lower()}" in text
                )
            ),
            None,
        )
        block = _Block(action.name, action.desc, action.attack_bonus, action.dc, action.damage)
        option = ref if ref is not None and action.attack_bonus is None else None
        option = option or _option(monster, block, overlay, None)
        if option is None:
            missing.append(f"legendary {action.name}")
            continue
        found.append(replace(option, key=key, name=action.name, cost=cost, resource=None))
    return found, missing


def monster_spells(monster: SrdMonster) -> tuple[MonsterSpell, ...]:
    found: list[MonsterSpell] = []
    for ability in monster.special_abilities:
        kit = ability.spellcasting
        if kit is None:
            continue
        mod = ability_modifier(monster.ability_score(kit.ability.index))
        pb = monster.proficiency_bonus
        for spell in kit.spells:
            index, usage = spell_index(spell.url), spell.usage
            resource = None
            if usage is not None and usage.type == "per day":
                resource = f"innate-{index}"
            elif usage is not None and usage.type == "at will":
                resource = AT_WILL
            found.append(
                MonsterSpell(
                    index=index,
                    name=spell.name,
                    level=spell.level,
                    resource=resource,
                    save_dc=kit.dc or 8 + pb + mod,
                    attack_bonus=kit.modifier or pb + mod,
                    modifier=mod,
                    caster_level=kit.level or 1,
                )
            )
    return tuple(found)


def monster_catalog(
    monster: SrdMonster, overlay: MonsterOverlay, shipped: Container[str]
) -> MonsterCatalog:
    unsupported: list[str] = []
    options: list[MonsterOption] = []
    multi = [a for a in monster.actions if a.multiattack_type is not None]
    for action in monster.actions:
        if action.multiattack_type is None:
            options.extend(_action_options(monster, action, overlay, unsupported))
    for action in multi:
        option = _multiattack(action, options)
        if option is None:
            unsupported.append(action.name)
        else:
            options.append(option)
    spells = tuple(s for s in monster_spells(monster) if s.index in shipped)
    unsupported.extend(
        f"spell {s.index}" for s in monster_spells(monster) if s.index not in shipped
    )
    for spell in spells:
        options.append(MonsterOption(f"{SPELL_PREFIX}{spell.index}", spell.name, "spell"))
    legendary, missing = _legendary(monster, options, overlay)
    return MonsterCatalog(
        monster=monster.index,
        options=tuple(options),
        legendary=tuple(legendary),
        spells=spells,
        unsupported=(*unsupported, *missing),
    )
