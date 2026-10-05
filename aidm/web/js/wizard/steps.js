// The wizard step list: id, whether it applies, its client-side problem check (a strings key under
// `wzProblem`, or null) and its renderer. The server's creation_result stays authoritative.
import { renderAbilities } from './step_abilities.js';
import { renderBackground } from './step_background.js';
import { renderClass } from './step_class.js';
import { renderEquipment } from './step_equipment.js';
import { renderIdentity } from './step_identity.js';
import { renderPortrait } from './step_portrait.js';
import { renderRace } from './step_race.js';
import { renderReview } from './step_review.js';
import { renderSkills } from './step_skills.js';
import { renderSpells } from './step_spells.js';
import {
  BACKSTORY_MAX,
  NAME_MAX,
  POINT_BUDGET,
  PRONOUNS_MAX,
  baseScores,
  casting,
  classSkillOptions,
  pointCost,
  racePicks,
} from './model.js';

const needsBasics = (ctx) => !ctx.race || !ctx.effective || !ctx.cls || !ctx.bg;

function raceProblem(draft, data, ctx) {
  if (!ctx.race) return 'pickRace';
  if (!ctx.effective) return 'pickSubrace';
  const picks = racePicks(ctx);
  const traitsDone = picks.traits.every((p) => (draft.featureChoices[p.id] ?? []).length === p.choose);
  const done =
    draft.abilityPicks.length === picks.abilities &&
    draft.tools.length === picks.tools &&
    draft.languages.length === picks.languages &&
    traitsDone;
  return done ? null : 'finishHeritage';
}

function classProblem(draft, data, ctx) {
  if (!ctx.cls) return 'pickClass';
  const chosen = ctx.cls.class_choices.every((c) => (draft.classChoices[c.id] ?? []).length === c.choose);
  const picked = ctx.cls.feature_picks.every((p) => (draft.featureChoices[p.id] ?? []).length === p.choose);
  return chosen && picked ? null : 'finishClassChoice';
}

function abilitiesProblem(draft) {
  if (draft.method === 'roll_4d6' && !draft.rolls.length) return 'rollFirst';
  if (draft.method === 'point_buy' && pointCost(draft.points) > POINT_BUDGET) return 'overBudget';
  return baseScores(draft) ? null : 'assignScores';
}

function skillsProblem(draft, data, ctx) {
  if (needsBasics(ctx)) return 'needEarlier';
  const wantClass = Math.min(ctx.cls.skill_choice.choose, classSkillOptions(ctx).length);
  const raceWant = ctx.effective.skill_choice?.choose ?? 0;
  const expertiseDone = ctx.cls.expertise.every((e) => (draft.featureChoices[e.id] ?? []).length === e.choose);
  const ok = draft.classSkills.length === wantClass && draft.raceSkills.length === raceWant && expertiseDone;
  return ok ? null : 'pickSkills';
}

function equipmentProblem(draft, data, ctx) {
  if (needsBasics(ctx)) return 'needEarlier';
  return ctx.cls.equipment.choices.every((c) => Number.isInteger(draft.equipment[c.id])) ? null : 'pickEquipment';
}

function spellsProblem(draft, data, ctx) {
  const cast = casting(draft, data, ctx);
  if (!cast) return null;
  const preparedOk = !cast.prepares || (draft.prepared.length >= 1 && draft.prepared.length <= cast.limit);
  const ok =
    draft.cantrips.length === cast.cantrip_count &&
    draft.raceCantrips.length === cast.raceCount &&
    draft.spells.length === cast.spell_count &&
    preparedOk;
  return ok ? null : 'pickSpells';
}

function identityProblem(draft) {
  const name = draft.name.trim();
  if (!name || name.length > NAME_MAX) return 'nameNeeded';
  if (draft.pronouns.length > PRONOUNS_MAX) return 'pronounsLong';
  return draft.backstory.length > BACKSTORY_MAX ? 'backstoryLong' : null;
}

export const STEPS = [
  { id: 'race', problem: raceProblem, render: renderRace },
  { id: 'class', problem: classProblem, render: renderClass },
  { id: 'background', problem: (d, x, ctx) => (ctx.bg ? null : 'pickBackground'), render: renderBackground },
  { id: 'abilities', problem: abilitiesProblem, render: renderAbilities, needsBasics: true },
  { id: 'skills', problem: skillsProblem, render: renderSkills, needsBasics: true },
  { id: 'equipment', problem: equipmentProblem, render: renderEquipment, needsBasics: true },
  { id: 'spells', problem: spellsProblem, render: renderSpells, needsBasics: true, casters: true },
  { id: 'portrait', problem: (d) => (d.portrait ? null : 'pickPortrait'), render: renderPortrait },
  { id: 'identity', problem: identityProblem, render: renderIdentity },
  { id: 'review', problem: () => null, render: renderReview },
];

/** Steps that apply to the current draft (spells only for casters). */
export function activeSteps(draft, data, ctx) {
  return STEPS.filter((s) => !s.casters || casting(draft, data, ctx));
}

export function stepProblem(step, draft, data, ctx) {
  if (step.needsBasics && needsBasics(ctx)) return 'needEarlier';
  return step.problem(draft, data, ctx);
}
