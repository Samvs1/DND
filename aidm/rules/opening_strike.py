"""The attack that starts a fight (M19.2, owner choice "rolled right away as the fight starts, BG3
style"; M20.5, playtest 3: a hero who cast Eldritch Blast at someone had a dagger rolled instead).

`opening_strike(state, attacker_id, target_id, regs, rng, attack=None)` is rolled before the first
turn and spends no action:
- `attack` a spell id the hero has ready with an attack roll (a cantrip, or a leveled spell, which
  pays its slot as usual): that spell is cast at the target (`rules.spells.cast_spell`);
- `attack` a weapon option ("main_hand", "ranged", "unarmed", ...): that attack, if it reaches;
- otherwise the first option the hotbar would offer that reaches (main hand first, never a
  bonus-action attack).
Empty when nothing the hero named or carries reaches (the fight still starts).

Public API: `opening_strike(state, attacker_id, target_id, regs, rng, attack=None)`.
"""

from aidm.data.combat_data import CombatRegistries
from aidm.models.combat import AttackEconomy, AttackProfile
from aidm.models.events import AnyEvent
from aidm.models.state import GameState
from aidm.rules.attack_profiles import attack_options
from aidm.rules.attacks import resolve_attack
from aidm.rules.command_checks import CommandRefused
from aidm.rules.dice import Rng
from aidm.rules.hit_chance import attack_situation
from aidm.rules.spell_chances import SPELL_OPTION_PREFIX, spell_attack_options
from aidm.rules.spells import cast_spell


def _spell(
    state: GameState, ids: tuple[str, str], spell_id: str, regs: CombatRegistries, rng: Rng
) -> list[AnyEvent] | None:
    attacker_id, target_id = ids
    creature = state.creatures[attacker_id]
    ready = {p.key for p in spell_attack_options(creature, regs.chars, regs.spells)}
    spell = regs.spells.find(spell_id)
    if spell is None or f"{SPELL_OPTION_PREFIX}{spell_id}" not in ready:
        return None
    slot = None if spell.level == 0 else spell.level
    try:
        return cast_spell(state, attacker_id, spell, slot, [target_id], None, rng, regs)
    except CommandRefused:
        return []


def _weapons(creature_options: list[AttackProfile], attack: str | None) -> list[AttackProfile]:
    usable = [p for p in creature_options if p.economy is not AttackEconomy.BONUS_ACTION]
    named = [p for p in usable if p.key == attack]
    return named or usable


def opening_strike(
    state: GameState,
    attacker_id: str,
    target_id: str,
    regs: CombatRegistries,
    rng: Rng,
    attack: str | None = None,
) -> list[AnyEvent]:
    if attack:
        cast = _spell(
            state, (attacker_id, target_id), attack.removeprefix(SPELL_OPTION_PREFIX), regs, rng
        )
        if cast is not None:
            return cast
    creature = state.creatures[attacker_id]
    feats = regs.chars.features
    for profile in _weapons(attack_options(creature, regs.chars), attack):
        sit = attack_situation(state, attacker_id, target_id, profile, feats)
        if sit.range_check.in_range:
            return list(resolve_attack(rng, state, attacker_id, target_id, profile, feats).events)
    return []
