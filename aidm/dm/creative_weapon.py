"""A creative action never deals a weapon's damage (M31.1a V3, round 4: "I cut down the spider with
my sword" became an Athletics check and a flat 2d6, and 13 from a longsword, above its maximum
of 11, with no roll against armour).

The rule, in ONE place (`run_creative_effect` asks it before any creative damage): creative
damage aimed at a creature of the fight, when the effect leans on a weapon the hero carries (the
creative_effect tool's `item` argument; M36.12: no text rules, the line is read by the menu), is
the engine's own attack instead: `AttackCommand` with the attack option whose name fits the
weapon (the main hand when no option fits).
`rules.commands.execute_command` rolls it against armour class with the weapon's own dice and
spends the action; when it is impossible (out of reach, no attack left) the tool is refused with
the rules' plain reason, and no creative damage is dealt.

Public API: `WEAPON_BLOW`, `weapon_outcome(state, args, gear, rng, regs)`.
"""

import re

from aidm.data.combat_data import combat_registries
from aidm.dm.entities import display_name
from aidm.dm.tool_context import ToolRefused, ToolRegistries, ToolResult
from aidm.dm.tools import CreativeEffectArgs
from aidm.models.combat_events import AttackRolled
from aidm.models.commands import AttackCommand
from aidm.models.dm_tiers import EffectKind
from aidm.models.encounter import EncounterStatus
from aidm.models.state import Creature, GameState
from aidm.rules.attack_profiles import UNARMED_KEY, attack_options
from aidm.rules.command_checks import CommandRefused
from aidm.rules.commands import execute_command
from aidm.rules.dice import Rng

WEAPON_BLOW = "a weapon blow is the engine's attack roll, never creative damage"


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z]+", text.lower()))


def _weapon(gear: str | None) -> str | None:
    entry = combat_registries().chars.equipment.find(gear) if gear else None
    return gear if entry is not None and entry.weapon_category is not None else None


def _option(actor: Creature, weapon: str | None) -> str:
    options = attack_options(actor, combat_registries().chars)
    wanted = _words(display_name(weapon)) if weapon else set()
    fits = [o.key for o in options if o.key != UNARMED_KEY and wanted & _words(o.name)]
    if fits:
        return fits[0]
    return "main_hand" if any(o.key == "main_hand" for o in options) else UNARMED_KEY


def _in_fight(state: GameState, actor_id: str, target_id: str) -> bool:
    enc = state.encounter
    if enc is None or enc.status is not EncounterStatus.ACTIVE:
        return False
    return target_id != actor_id and {actor_id, target_id} <= set(enc.combatants)


def _summary(state: GameState, events: list[object]) -> str:
    rolled = [e for e in events if isinstance(e, AttackRolled)]
    if not rolled:
        return f"{WEAPON_BLOW}: the attack was made"
    a = rolled[0]
    verdict = "hit" if a.hit else "miss"
    target = state.creatures[a.target_id].name
    return f"{a.attack} attack on {target}: {a.roll.total} vs AC {a.target_ac} -> {verdict}"


def weapon_outcome(
    state: GameState,
    args: CreativeEffectArgs,
    gear: str | None,
    rng: Rng,
    regs: ToolRegistries,
) -> ToolResult | None:
    target = args.target or ""
    actor = state.creatures.get(args.actor)
    if args.effect_kind is not EffectKind.MINOR_DAMAGE or actor is None or actor.pc is None:
        return None
    if not _in_fight(state, actor.id, target):
        return None
    weapon = _weapon(gear)
    if weapon is None:
        return None
    command = AttackCommand(actor_id=actor.id, target_id=target, option=_option(actor, weapon))
    try:
        events = execute_command(state, command, regs.combat, rng)
    except CommandRefused as refused:
        raise ToolRefused(f"{WEAPON_BLOW}: {refused.reason}") from refused
    return ToolResult(events=tuple(events), summary=_summary(state, list(events)))
