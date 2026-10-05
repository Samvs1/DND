// Wizard model: the draft, what it implies (final scores, pick counts, limits) and the payload for
// create_character. Pure functions over (draft, data); the server's validate_creation stays authoritative.

export const ABILITIES = ['str', 'dex', 'con', 'int', 'wis', 'cha'];
export const POINT_BUDGET = 27;
export const POINT_MIN = 8;
export const POINT_MAX = 15;
export const POINT_COSTS = { 8: 0, 9: 1, 10: 2, 11: 3, 12: 4, 13: 5, 14: 7, 15: 9 };
export const STANDARD_ARRAY = [15, 14, 13, 12, 10, 8];
export const BACKSTORY_MAX = 400;
export const NAME_MAX = 40;
export const PRONOUNS_MAX = 30;

export function newDraft() {
  return {
    race: '',
    subrace: null,
    cls: '',
    background: '',
    method: 'point_buy',
    points: Object.fromEntries(ABILITIES.map((a) => [a, POINT_MIN])),
    assign: {},
    rolls: [],
    abilityPicks: [],
    tools: [],
    languages: [],
    classSkills: [],
    raceSkills: [],
    classChoices: {},
    featureChoices: {},
    equipment: {},
    cantrips: [],
    raceCantrips: [],
    spells: [],
    prepared: [],
    portrait: '',
    name: '',
    pronouns: '',
    backstory: '',
  };
}

export function modifier(score) {
  return Math.floor((score - 10) / 2);
}

export function signed(n) {
  return n >= 0 ? `+${n}` : `${n}`;
}

export function context(draft, data) {
  const race = data.races.find((r) => r.index === draft.race) ?? null;
  const sub = race?.subraces.find((s) => s.index === draft.subrace) ?? null;
  const effective = race ? (race.subraces.length ? (sub?.effective ?? null) : race.effective) : null;
  const cls = data.classes.find((c) => c.index === draft.cls) ?? null;
  const bg = data.backgrounds.find((b) => b.index === draft.background) ?? null;
  return { race, sub, effective, cls, bg };
}

export function pointCost(points) {
  return ABILITIES.reduce((sum, a) => sum + (POINT_COSTS[points[a]] ?? 0), 0);
}

export function assignableValues(draft) {
  return draft.method === 'standard_array' ? STANDARD_ARRAY : draft.rolls.map((r) => r.total);
}

/** The six base scores before racial bonuses, or null while the assignment is incomplete. */
export function baseScores(draft) {
  if (draft.method === 'point_buy') return { ...draft.points };
  const values = assignableValues(draft);
  const out = {};
  const used = new Set();
  for (const a of ABILITIES) {
    const at = draft.assign[a];
    if (at === undefined || at === null || used.has(at) || values[at] === undefined) return null;
    used.add(at);
    out[a] = values[at];
  }
  return out;
}

export function bonuses(draft, ctx) {
  const out = Object.fromEntries(ABILITIES.map((a) => [a, 0]));
  if (!ctx.effective) return out;
  for (const [a, n] of Object.entries(ctx.effective.ability_bonuses)) out[a] += n;
  const bonus = ctx.effective.ability_choice?.bonus ?? 0;
  for (const a of draft.abilityPicks) out[a] += bonus;
  return out;
}

export function finalScores(draft, ctx) {
  const base = baseScores(draft);
  if (!base) return null;
  const extra = bonuses(draft, ctx);
  return Object.fromEntries(ABILITIES.map((a) => [a, base[a] + extra[a]]));
}

export function grantedSkills(ctx) {
  return [...new Set([...(ctx.bg?.skills ?? []), ...(ctx.effective?.skills ?? [])])];
}

export function grantedTools(ctx) {
  return [...new Set([...(ctx.cls?.tools ?? []), ...(ctx.effective?.tools ?? []), ...(ctx.bg?.tools ?? [])])];
}

export function classSkillOptions(ctx) {
  const taken = grantedSkills(ctx);
  return (ctx.cls?.skill_choice.options ?? []).filter((s) => !taken.includes(s));
}

export function raceSkillOptions(draft, ctx) {
  const taken = [...grantedSkills(ctx), ...draft.classSkills];
  return (ctx.effective?.skill_choice?.options ?? []).filter((s) => !taken.includes(s));
}

export function proficientSkills(draft, ctx) {
  const all = [...grantedSkills(ctx), ...draft.classSkills, ...draft.raceSkills, ...(ctx.cls?.feature_skills ?? [])];
  return [...new Set(all)];
}

export function toolOptions(ctx) {
  const taken = grantedTools(ctx);
  return (ctx.effective?.tool_choice?.options ?? []).filter((x) => !taken.includes(x));
}

export function languageOptions(data, ctx) {
  const known = ctx.effective?.languages ?? [];
  return data.languages.map((l) => l.index).filter((l) => !known.includes(l));
}

export function racePicks(ctx) {
  const e = ctx.effective;
  if (!e) return { abilities: 0, tools: 0, languages: 0, traits: [] };
  return {
    abilities: e.ability_choice?.choose ?? 0,
    tools: Math.min(e.tool_choice?.choose ?? 0, toolOptions(ctx).length),
    languages: e.language_choices,
    traits: e.trait_picks,
  };
}

/**
 * Spell counts and pools for the chosen class and race, or null when the hero casts nothing.
 * A non-caster class can still pick a heritage cantrip (high elf), so that case has `ability: null`.
 */
export function casting(draft, data, ctx) {
  const c = ctx.cls?.casting ?? null;
  const raceClass = ctx.effective?.cantrip_class;
  const pool = raceClass ? (data.race_cantrips[raceClass] ?? []) : [];
  const racePool = pool.filter((s) => !draft.cantrips.includes(s));
  const raceCount = Math.min(ctx.effective?.cantrip_choices ?? 0, racePool.length);
  if (!c && !raceCount) return null;
  const base = c ?? {
    ability: null,
    kind: null,
    cantrip_count: 0,
    spell_count: 0,
    spellbook: false,
    prepares: false,
    cantrips: [],
    spells: [],
  };
  const finals = finalScores(draft, ctx);
  const score = finals && base.ability ? finals[base.ability] : 10;
  const limit = base.prepares ? Math.max(1, modifier(score) + 1) : 0;
  const preparedPool = base.spellbook ? draft.spells : base.spells;
  return { ...base, racePool, raceCount, limit, preparedPool };
}

function keepIn(list, allowed, max) {
  return (list ?? []).filter((x, i) => allowed.includes(x) && list.indexOf(x) === i).slice(0, max);
}

function pruneIdentity(draft) {
  return (ctx) => {
    if (!ctx.race) draft.race = '';
    if (!ctx.race?.subraces.length || !ctx.sub) draft.subrace = null;
    if (!ctx.cls) draft.cls = '';
    if (!ctx.bg) draft.background = '';
  };
}

function pruneRace(draft, data, ctx) {
  const picks = racePicks(ctx);
  const abil = ctx.effective?.ability_choice?.options ?? [];
  draft.abilityPicks = keepIn(draft.abilityPicks, abil, picks.abilities);
  draft.tools = keepIn(draft.tools, toolOptions(ctx), picks.tools);
  draft.languages = keepIn(draft.languages, languageOptions(data, ctx), picks.languages);
  const next = {};
  for (const ex of ctx.cls?.expertise ?? []) next[ex.id] = draft.featureChoices[ex.id] ?? [];
  for (const pick of [...picks.traits, ...(ctx.cls?.feature_picks ?? [])]) {
    const ids = pick.options.map((o) => o.id);
    next[pick.id] = keepIn(draft.featureChoices[pick.id], ids, pick.choose);
  }
  draft.featureChoices = next;
}

function pruneClass(draft, ctx) {
  const cls = ctx.cls;
  draft.classSkills = keepIn(draft.classSkills, classSkillOptions(ctx), cls?.skill_choice.choose ?? 0);
  draft.raceSkills = keepIn(draft.raceSkills, raceSkillOptions(draft, ctx), ctx.effective?.skill_choice?.choose ?? 0);
  const proficient = proficientSkills(draft, ctx);
  for (const ex of cls?.expertise ?? []) {
    draft.featureChoices[ex.id] = keepIn(draft.featureChoices[ex.id], proficient, ex.choose);
  }
  const choices = {};
  for (const c of cls?.class_choices ?? []) {
    choices[c.id] = keepIn(draft.classChoices[c.id], c.options.map((o) => o.id), c.choose);
  }
  draft.classChoices = choices;
  const equipment = {};
  for (const c of cls?.equipment.choices ?? []) {
    const at = draft.equipment[c.id];
    if (Number.isInteger(at) && at >= 0 && at < c.options.length) equipment[c.id] = at;
  }
  draft.equipment = equipment;
}

function pruneSpells(draft, data, ctx) {
  const cast = casting({ ...draft, cantrips: [] }, data, ctx);
  if (!cast) {
    Object.assign(draft, { cantrips: [], raceCantrips: [], spells: [], prepared: [] });
    return;
  }
  draft.cantrips = keepIn(draft.cantrips, cast.cantrips, cast.cantrip_count);
  const after = casting(draft, data, ctx);
  draft.raceCantrips = keepIn(draft.raceCantrips, after.racePool, after.raceCount);
  draft.spells = keepIn(draft.spells, after.spells, after.spell_count);
  const final = casting(draft, data, ctx);
  draft.prepared = keepIn(draft.prepared, final.preparedPool, final.limit);
}

/** Drop every pick the current race/class/background no longer allows (mutates the draft). */
export function prune(draft, data) {
  pruneIdentity(draft)(context(draft, data));
  const ctx = context(draft, data);
  pruneRace(draft, data, ctx);
  pruneClass(draft, ctx);
  pruneSpells(draft, data, ctx);
  return draft;
}

export function buildChoices(draft, data) {
  const ctx = context(draft, data);
  const base = baseScores(draft);
  if (!base || !ctx.race || !ctx.cls || !ctx.bg) return null;
  const featureChoices = {};
  for (const [id, picks] of Object.entries(draft.featureChoices)) if (picks.length) featureChoices[id] = picks;
  return {
    name: draft.name.trim(),
    pronouns: draft.pronouns.trim(),
    backstory: draft.backstory,
    portrait_id: draft.portrait,
    race: ctx.race.index,
    subrace: draft.subrace,
    class_index: ctx.cls.index,
    background: ctx.bg.index,
    ability_method: draft.method,
    base_scores: base,
    rolls: draft.method === 'roll_4d6' ? draft.rolls : [],
    ability_choice_picks: draft.abilityPicks,
    class_skills: draft.classSkills,
    race_skills: draft.raceSkills,
    tool_picks: draft.tools,
    language_picks: draft.languages,
    equipment_picks: draft.equipment,
    class_choices: draft.classChoices,
    feature_choices: featureChoices,
    cantrips: draft.cantrips,
    race_cantrips: draft.raceCantrips,
    spells: draft.spells,
    prepared: draft.prepared,
  };
}
