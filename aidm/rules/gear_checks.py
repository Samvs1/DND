"""THE check the engine rolls for a hero out of a fight (M27.3): darkness, gear boons and tools.

Used by the DM `request_check` (`aidm.dm.tool_exec_checks`) and by gear uses that roll (fishing,
`aidm.rules.item_effects`). Whatever the AI asked, the engine adds:
- *Darkness* (`aidm.rules.light.sight_darkness`, M27.2) as a disadvantage source;
- each gear boon of the hero that covers the skill (`aidm.rules.boons.skill_boons`) as a named
  advantage source; advantage never stacks (`aidm.rules.d20`);
- the SRD tool the check is made with (an explicit `tool`, else the tool of a covering boon):
  PROF once for tool OR skill proficiency (`aidm.rules.checks.tool_extra`), and advantage
  (*Tool and skill*) when proficient in both (house rule, docs/RULES_DECISIONS.md).

A lock check (M27.4, `aidm.rules.locks`) passes `use_boons=False` (a climbing rope's Athletics
boon does not force a lock) and names its own gear advantage in `adv_names` (*Crowbar*).

Public API: `TOOL_AND_SKILL`, `gear_check(rng, state, creature, what, dc, *, adv_sources=0,
dis_sources=0, tool=None, adv_names=(), use_boons=True) -> CheckResult`.
"""

from collections.abc import Sequence

from aidm.models.abilities import Ability, Skill
from aidm.models.checks import CheckResult
from aidm.models.state import Creature, GameState
from aidm.rules.boons import skill_boons
from aidm.rules.checks import tool_and_skill
from aidm.rules.conditions import ability_check_with_conditions, skill_check_with_conditions
from aidm.rules.dice import Rng
from aidm.rules.light import sight_darkness

TOOL_AND_SKILL = "Tool and skill"


def gear_check(
    rng: Rng,
    state: GameState,
    creature: Creature,
    what: Skill | Ability,
    dc: int,
    *,
    adv_sources: int = 0,
    dis_sources: int = 0,
    tool: str | None = None,
    adv_names: Sequence[str] = (),
    use_boons: bool = True,
) -> CheckResult:
    skill = what if isinstance(what, Skill) else None
    boons = skill_boons(state, creature.id, skill) if use_boons else []
    used_tool = tool or next((b.tool for b in boons if b.tool is not None), None)
    names = [*adv_names, *(b.name for b in boons)]
    if tool_and_skill(creature, skill, used_tool):
        names.append(TOOL_AND_SKILL)
    dark = sight_darkness(state, what)
    if isinstance(what, Skill):
        return skill_check_with_conditions(
            rng,
            creature,
            what,
            dc,
            adv_sources=adv_sources,
            dis_sources=dis_sources,
            adv_names=names,
            dis_names=dark,
            tool=used_tool,
        )
    return ability_check_with_conditions(
        rng,
        creature,
        what,
        dc,
        adv_sources=adv_sources,
        dis_sources=dis_sources,
        adv_names=names,
        dis_names=dark,
        tool=used_tool,
    )
