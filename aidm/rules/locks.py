"""Locks on world features (M27.4, GOAL_ITEMS "Locks" and "Risk"). PURE: returns events.

Placement (the feature generator is `introduce_feature`; it REPAIRS, never rejects):
- only caches, containers and side doors take a lock (`LOCKABLE`); never a feature at a region's
  gateway (the main path to the boss) and never one named like a quest item of the plan
  (`aidm.rules.quest_items.same_item`). Travel between places never passes a feature, so any
  other door is a side door. `lock_problem` says why a lock may not stay, `placed_lock` strips it
  (and caps its tier at `MAX_LOCK_TIER`, so forcing can always succeed).
- `LockInfo.opens` is the feature kind a key must open (`aidm.rules.item_grants.key_fits`).

Opening (every way emits `FeatureUnlocked`; contents stay out of reach until then):
- a fitting key the party carries opens it automatically, no check, whatever the hero tries
  (`key_open`, through `aidm.rules.item_grants.party_key_for`);
- pick: the lock's DC with the hero's thieves' tools (`gear_check` with the tool: proficiency once
  for tool OR skill, both = advantage); without a pick tool a lock cannot be picked;
- force: Athletics (or STR) at the lock's DC; gear with a force use that grants advantage (the
  crowbar) names it (*Crowbar*); forcing is noisy, success or failure (`PlaceAlerted`), and can
  always be retried, as can picking.
A lock check's DC and advantage are the engine's (lock tier, gear, tool and skill, darkness):
the AI's tier and advantage flag never apply, and place boons (a climbing rope) do not either.
Which gear does a method is data: the hero's carried items with an `unlock` use of that method
(data/bg3/item_uses.json); no per-item branch.

Public API: `LOCKABLE`, `MAX_LOCK_TIER`, `lock_problem(state, feature) -> str | None`,
`placed_lock(state, feature) -> WorldFeature`, `locked_here(state, feature_id) -> WorldFeature |
str`, `key_open(state, actor_id, feature) -> list[AnyEvent]`, `lock_method(what) -> Method |
None`, `lock_gear(actor, method) -> LockGear | None`, `noise_events(state) -> list[AnyEvent]`,
`attempt_lock(rng, state, actor, feature, method, what, gear, reason) -> list[AnyEvent]`,
`lock_check(rng, state, actor, feature, what, reason) -> list[AnyEvent] | str`.
"""

from dataclasses import dataclass
from typing import Literal

from aidm.data.item_catalogue import item_catalogue
from aidm.data.item_uses import Unlock, uses_for_item
from aidm.models.abilities import Ability, Skill
from aidm.models.checks import DcTier
from aidm.models.events import AnyEvent, CheckResolved
from aidm.models.item_events import FeatureUnlocked, PlaceAlerted
from aidm.models.state import Creature, GameState
from aidm.models.world import FeatureKind, WorldFeature
from aidm.rules.checks import dc_for_tier
from aidm.rules.dice import Rng
from aidm.rules.gear_checks import gear_check
from aidm.rules.item_grants import party_key_for
from aidm.rules.quest_items import act_quest_items, same_item

type Method = Literal["pick", "force"]

LOCKABLE = frozenset({FeatureKind.CACHE, FeatureKind.CONTAINER, FeatureKind.DOOR})
MAX_LOCK_TIER = DcTier.HARD
_TIER_ORDER = tuple(DcTier)
_FORCE = frozenset({Skill.ATHLETICS, Ability.STR})
_PICK = frozenset({Skill.SLEIGHT_OF_HAND, Ability.DEX})


@dataclass(frozen=True)
class LockGear:
    """The carried item doing a lock method, its tool id (proficiency) and its advantage name."""

    item: str
    tool: str | None
    aid: str | None


def _gateways(state: GameState) -> set[str]:
    campaign = state.campaign
    if campaign is None:
        return set()
    return {region.gateway.id for region in campaign.plan.all_regions()}


def _quest_item_names(state: GameState) -> list[str]:
    campaign = state.campaign
    if campaign is None:
        return []
    plan = campaign.plan
    return [item.name for act in plan.acts for item in act_quest_items(plan, act.index)]


def lock_problem(state: GameState, feature: WorldFeature) -> str | None:
    if feature.lock is None:
        return None
    if feature.kind not in LOCKABLE:
        return "only caches, containers and side doors take a lock"
    if feature.node_id is not None and feature.node_id in _gateways(state):
        return "the gateway is the main path and is never locked"
    if any(same_item(feature.name, name) for name in _quest_item_names(state)):
        return "a quest item is never locked away"
    return None


def placed_lock(state: GameState, feature: WorldFeature) -> WorldFeature:
    lock = feature.lock
    if lock is None:
        return feature
    if lock_problem(state, feature) is not None:
        return feature.model_copy(update={"lock": None})
    if _TIER_ORDER.index(lock.dc_tier) > _TIER_ORDER.index(MAX_LOCK_TIER):
        capped = lock.model_copy(update={"dc_tier": MAX_LOCK_TIER})
        return feature.model_copy(update={"lock": capped})
    return feature


def locked_here(state: GameState, feature_id: str | None) -> WorldFeature | str:
    world = state.world
    feature = world.features.get(feature_id or "")
    if feature is None or feature.node_id != world.current_node:
        return "There is nothing locked here to open."
    if feature.hidden and not feature.discovered:
        return "There is nothing locked here to open."
    if feature.lock is None:
        return f"The {feature.name} is not locked."
    return feature


def key_open(state: GameState, actor_id: str, feature: WorldFeature) -> list[AnyEvent]:
    if feature.lock is None:
        return []
    key = party_key_for(state, feature, item_catalogue())
    if key is None:
        return []
    return [FeatureUnlocked(feature_id=feature.id, creature_id=actor_id, method="key", item=key)]


def lock_method(what: Skill | Ability) -> Method | None:
    if what in _FORCE:
        return "force"
    if what in _PICK:
        return "pick"
    return None


def _gear_name(item_id: str) -> str:
    found = item_catalogue().find(item_id)
    name = found.name if found is not None else item_id
    return name.split(" (")[0].split(",")[0].strip()


def lock_gear(actor: Creature, method: Method) -> LockGear | None:
    """The first carried item with an `unlock` use of `method`, preferring one that aids."""
    pc = actor.pc
    if pc is None:
        return None
    found: list[LockGear] = []
    for entry in pc.inventory:
        for use in uses_for_item(entry.item):
            effect = use.effect
            if isinstance(effect, Unlock) and effect.method == method:
                aid = _gear_name(use.item) if effect.advantage else None
                found.append(LockGear(entry.item, use.item if use.tool else None, aid))
    found.sort(key=lambda g: (g.aid is None, g.tool is None))
    return found[0] if found else None


def noise_events(state: GameState) -> list[AnyEvent]:
    node = state.world.current_node
    if node is None or state.world.alerted == node:
        return []
    return [PlaceAlerted(node=node)]


def attempt_lock(
    rng: Rng,
    state: GameState,
    actor: Creature,
    feature: WorldFeature,
    method: Method,
    what: Skill | Ability,
    gear: LockGear | None,
    reason: str,
) -> list[AnyEvent]:
    """One pick or force roll at the lock's DC: `CheckResolved` (+ `FeatureUnlocked` on success).

    Noise is the caller's (`noise_events`, or the item use's `noise` flag)."""
    lock = feature.lock
    assert lock is not None
    result = gear_check(
        rng,
        state,
        actor,
        what,
        dc_for_tier(lock.dc_tier),
        tool=gear.tool if gear is not None else None,
        adv_names=(gear.aid,) if gear is not None and gear.aid else (),
        use_boons=False,
    )
    result = result.model_copy(update={"tier": lock.dc_tier})
    events: list[AnyEvent] = [CheckResolved(creature_id=actor.id, result=result, reason=reason)]
    if result.success:
        item = gear.item if gear is not None else None
        events.append(
            FeatureUnlocked(feature_id=feature.id, creature_id=actor.id, method=method, item=item)
        )
    return events


def lock_check(
    rng: Rng,
    state: GameState,
    actor: Creature,
    feature: WorldFeature,
    what: Skill | Ability,
    reason: str,
) -> list[AnyEvent] | str:
    """A check the DM asked for ON a locked feature (`request_check` naming it), or a refusal.

    A fitting key opens it with no roll; Athletics/STR forces (noisy), Sleight of Hand/DEX picks
    (needs a pick tool); any other check cannot reach what the lock keeps."""
    opened = key_open(state, actor.id, feature)
    if opened:
        return opened
    method = lock_method(what)
    if method is None:
        return (
            f"The {feature.name} is locked: open it first (a fitting key, thieves' tools with"
            " Sleight of Hand, or force it with Athletics)."
        )
    gear = lock_gear(actor, method)
    if method == "pick" and gear is None:
        return (
            f"Picking the lock of the {feature.name} needs thieves' tools, and {actor.name}"
            " carries none; forcing it with Athletics is the other way."
        )
    events = attempt_lock(rng, state, actor, feature, method, what, gear, reason)
    return [*events, *noise_events(state)] if method == "force" else events
