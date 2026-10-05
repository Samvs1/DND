"""Build-time feature effects, read by character creation and level-up (SPEC 7.4, 7.5, 8).

The same hooks as `aidm.rules.features`, but the ones that change the character sheet itself:
resource pools, resistances, maximum HP per level, speed, darkvision, proficiencies, expertise
and option picks, spell grants, scroll-copy costs and slot recovery. Functions take feature id
lists (the character may not exist yet) plus the feature registry as an argument.

Public API:
- `FeatureEffects(resistances, hp_per_level, speed, darkvision, armor, weapons, tools, skills)`;
  `feature_effects(ids, level, feats) -> FeatureEffects`.
- `feature_resources(ids, level, feats) -> dict[str, Resource]`: full pools (creation).
- `feature_resource_events(creature, ids, level, feats) -> list[AnyEvent]`: level-up: new pools
  full, grown pools keep their spent uses (same rule as spell slots).
- `with_picks(ids, picks, feats) -> list[str]`: `ids` plus the options picked for features
  that offer a `pick` (draconic ancestry colour).
- `feature_choice_errors(ids, picks, feats, proficient, *, expert=(), field) -> errors`:
  each pick feature needs exactly `choose` of its options; each `expertise` hook needs
  `choose` skills from `proficient` that are not already in `expert`; picks for features not in
  `ids` are refused.
- `expertise_picks(ids, picks, feats) -> list[Skill]`.
- `granted_spells(ids, level, subclass, feats) -> list[GrantedSpell]`: grants active at `level`
  for this subclass (or for any subclass), shipped spells only (an unshipped domain, patron or
  racial spell is simply not granted; docs/RULES_DECISIONS.md M3.6b);
  `expanded_spell_indexes(...) -> set[str]`: the `expanded` ones (warlock patron lists, added
  to what the class may learn).
- `innate_casting_ability(ids, level, feats) -> Ability | None`: the casting ability of spells
  granted by features and of picked race cantrips (the hook covering race cantrips first).
- `scroll_copy_cost(ids, level, feats, spell_level, school) -> int | None`: gold to copy a
  scroll of this level and school (None = no scroll-copy feature).
- `SlotRecoveryError(ValueError)`; `recover_spell_slots(creature, feats, slot_levels)`:
  spend the slot-recovery resource and regain one slot per listed level (budget, cap, spent
  slots and the resource are checked; nothing changes on an error).
"""

from collections import Counter
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass

from aidm.data.feature_defs import FeatureDef
from aidm.data.feature_hooks import (
    DarkvisionHook,
    ExpertiseHook,
    GrantedSpell,
    ProficiencyHook,
    ResistanceHook,
    ResourceHook,
    ScrollCopyHook,
    SlotRecoveryHook,
    SpellGrantHook,
    StatBonusHook,
)
from aidm.data.registry import Registry
from aidm.data.spell_defs import shipped_spell_ids
from aidm.models.abilities import Ability, Skill
from aidm.models.creation import CreationError, CreationErrorCode
from aidm.models.damage import DamageType
from aidm.models.events import AnyEvent, ResourceSet
from aidm.models.state import Creature, RechargeKind, Resource
from aidm.rules.creation_checks import pick_errors
from aidm.rules.features import character_level, creature_feature_ids, feature_hooks
from aidm.rules.resources import ResourceError, spend_resource
from aidm.rules.spellcasting import SlotKind, slot_key

FEATURE_CHOICES_FIELD = "feature_choices"


@dataclass(frozen=True)
class FeatureEffects:
    resistances: tuple[DamageType, ...] = ()
    hp_per_level: int = 0
    speed: int = 0
    darkvision: int = 0
    armor: tuple[str, ...] = ()
    weapons: tuple[str, ...] = ()
    tools: tuple[str, ...] = ()
    skills: tuple[str, ...] = ()


def _unique[T](items: Sequence[T]) -> tuple[T, ...]:
    return tuple(dict.fromkeys(items))


def feature_effects(ids: Sequence[str], level: int, feats: Registry[FeatureDef]) -> FeatureEffects:
    hooks = [h for _, h in feature_hooks(ids, level, feats)]
    profs = [h for h in hooks if isinstance(h, ProficiencyHook)]
    stats = [h for h in hooks if isinstance(h, StatBonusHook)]
    resist = [DamageType(t) for h in hooks if isinstance(h, ResistanceHook) for t in h.damage_types]
    return FeatureEffects(
        resistances=_unique(resist),
        hp_per_level=sum(h.hp_per_level for h in stats),
        speed=sum(h.speed for h in stats),
        darkvision=max((h.range for h in hooks if isinstance(h, DarkvisionHook)), default=0),
        armor=_unique([a for h in profs for a in h.armor]),
        weapons=_unique([w for h in profs for w in h.weapons]),
        tools=_unique([t for h in profs for t in h.tools]),
        skills=_unique([s for h in profs for s in h.skills]),
    )


def _resource_hooks(
    ids: Sequence[str], level: int, feats: Registry[FeatureDef]
) -> list[ResourceHook]:
    return [h for _, h in feature_hooks(ids, level, feats) if isinstance(h, ResourceHook)]


def feature_resources(
    ids: Sequence[str], level: int, feats: Registry[FeatureDef]
) -> dict[str, Resource]:
    return {
        h.key: Resource(current=h.uses, maximum=h.uses, recharge=RechargeKind(h.recharge))
        for h in _resource_hooks(ids, level, feats)
    }


def feature_resource_events(
    creature: Creature, ids: Sequence[str], level: int, feats: Registry[FeatureDef]
) -> list[AnyEvent]:
    events: list[AnyEvent] = []
    for key, fresh in feature_resources(ids, level, feats).items():
        old = creature.resources.get(key)
        spent = old.maximum - old.current if old is not None else 0
        updated = fresh.model_copy(update={"current": max(0, fresh.maximum - spent)})
        if updated != old:
            events.append(ResourceSet(creature_id=creature.id, key=key, resource=updated))
    return events


def with_picks(
    ids: Sequence[str], picks: Mapping[str, Sequence[str]], feats: Registry[FeatureDef]
) -> list[str]:
    result = list(ids)
    for feature_id in ids:
        if feats.get(feature_id).pick is not None:
            result.extend(picks.get(feature_id, []))
    return list(dict.fromkeys(result))


def _expertise_counts(ids: Sequence[str], feats: Registry[FeatureDef]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for feature_id in ids:
        for hook in feats.get(feature_id).hooks:
            if isinstance(hook, ExpertiseHook):
                counts[feature_id] = counts.get(feature_id, 0) + hook.choose
    return counts


def feature_choice_errors(
    ids: Sequence[str],
    picks: Mapping[str, Sequence[str]],
    feats: Registry[FeatureDef],
    proficient: Collection[str],
    *,
    expert: Collection[str] = (),
    field: str = FEATURE_CHOICES_FIELD,
) -> list[CreationError]:
    errors: list[CreationError] = []
    expected: set[str] = set()
    for feature_id in dict.fromkeys(ids):
        pick = feats.get(feature_id).pick
        if pick is not None:
            expected.add(feature_id)
            got = list(picks.get(feature_id, []))
            errors += pick_errors(
                f"{field}.{feature_id}", got, count=pick.choose, allowed=pick.options
            )
    for feature_id, count in _expertise_counts(ids, feats).items():
        expected.add(feature_id)
        got = list(picks.get(feature_id, []))
        errors += pick_errors(
            f"{field}.{feature_id}", got, count=count, allowed=proficient, taken=expert
        )
    for feature_id in sorted(set(picks) - expected):
        detail = f"{feature_id!r} offers no choice here"
        errors.append(
            CreationError(
                code=CreationErrorCode.PICK_NOT_ALLOWED,
                field=f"{field}.{feature_id}",
                detail=detail,
            )
        )
    return errors


def expertise_picks(
    ids: Sequence[str], picks: Mapping[str, Sequence[str]], feats: Registry[FeatureDef]
) -> list[Skill]:
    return [Skill(s) for feature_id in _expertise_counts(ids, feats) for s in picks[feature_id]]


def _grants(ids: Sequence[str], level: int, feats: Registry[FeatureDef]) -> list[SpellGrantHook]:
    return [h for _, h in feature_hooks(ids, level, feats) if isinstance(h, SpellGrantHook)]


def granted_spells(
    ids: Sequence[str], level: int, subclass: str | None, feats: Registry[FeatureDef]
) -> list[GrantedSpell]:
    shipped = shipped_spell_ids()
    return [
        spell
        for hook in _grants(ids, level, feats)
        for spell in hook.spells
        if spell.min_level <= level
        and spell.subclass in (None, subclass)
        and spell.spell in shipped
    ]


def expanded_spell_indexes(
    ids: Sequence[str], level: int, subclass: str | None, feats: Registry[FeatureDef]
) -> set[str]:
    granted = granted_spells(ids, level, subclass, feats)
    return {g.spell for g in granted if g.mode == "expanded"}


def innate_casting_ability(
    ids: Sequence[str], level: int, feats: Registry[FeatureDef]
) -> Ability | None:
    grants = sorted(_grants(ids, level, feats), key=lambda h: not h.covers_race_cantrips)
    return next((Ability(h.ability) for h in grants if h.ability is not None), None)


def scroll_copy_cost(
    ids: Sequence[str], level: int, feats: Registry[FeatureDef], spell_level: int, school: str
) -> int | None:
    hooks = [h for _, h in feature_hooks(ids, level, feats) if isinstance(h, ScrollCopyHook)]
    base = [h.gold_per_level for h in hooks if h.school is None]
    if not base:
        return None
    percent = min([100, *(h.cost_percent for h in hooks if h.school == school)])
    return max(base) * spell_level * percent // 100


class SlotRecoveryError(ValueError):
    """Slot recovery refused: no feature, resource spent, over budget or nothing to regain."""


def recover_spell_slots(
    creature: Creature, feats: Registry[FeatureDef], slot_levels: Sequence[int]
) -> list[AnyEvent]:
    level = character_level(creature)
    pairs = feature_hooks(creature_feature_ids(creature), level, feats)
    hook = next((h for _, h in pairs if isinstance(h, SlotRecoveryHook)), None)
    if hook is None:
        raise SlotRecoveryError(f"{creature.id!r} cannot recover spell slots")
    budget = -(-level // hook.level_divisor)
    if not slot_levels or sum(slot_levels) > budget or max(slot_levels) > hook.max_slot_level:
        raise SlotRecoveryError(f"slot levels {list(slot_levels)} exceed the budget {budget}")
    try:
        events = spend_resource(creature, hook.resource)
    except ResourceError as exc:
        raise SlotRecoveryError(str(exc)) from None
    for slot_level, count in sorted(Counter(slot_levels).items()):
        key = slot_key(SlotKind.STANDARD, slot_level)
        pool = creature.resources.get(key)
        if pool is None or pool.maximum - pool.current < count:
            raise SlotRecoveryError(f"no {count} spent level-{slot_level} slot(s) to regain")
        restored = pool.model_copy(update={"current": pool.current + count})
        events.append(ResourceSet(creature_id=creature.id, key=key, resource=restored))
    return events
