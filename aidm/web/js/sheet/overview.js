// Sheet "Overview" tab (M25: one place for each fact): speed, initiative, proficiency and passive Perception
// (AC and HP live on the hero strip), abilities and saves, skills, attacks, features with their action and
// uses (feature actions and resources folded in), conditions only when there are any, death saves, training.
// Pure rendering of the derived `CharacterSheet` the server sent.
import { t } from '../strings.js';
import { h } from '../ui/dom.js';
import { titleCase } from '../ui/format.js';
import { tipButton } from '../ui/tip.js';
import { itemArt } from './item_art.js';

const signed = (n) => (n >= 0 ? `+${n}` : String(n));

/** The same corner on every fact tile, so the '?' never wraps with the label. */
function cornerTip(key, label) {
  const tip = tipButton(key, label);
  tip.classList.add('tip-corner');
  return tip;
}

function stat(label, value, testid, tip, note) {
  return h('div', { class: 'sh-stat', 'data-testid': testid }, h('span', { class: 'sh-stat-label' }, label), h('strong', { class: 'sh-stat-value' }, value), note ? h('span', { class: 'sh-stat-note' }, note) : null, cornerTip(tip, label));
}

function vitals(s) {
  return h(
    'div',
    { class: 'sh-vitals' },
    stat(t('sheet.speed'), t('sheet.speedFeet', { n: s.speed }), 'sh-speed', 'sheet:speed'),
    stat(t('sheet.initiative'), signed(s.initiative_bonus), 'sh-init', 'sheet:initiative'),
    stat(t('sheet.proficiency'), signed(s.proficiency_bonus), 'sh-prof', 'sheet:proficiency'),
    stat(t('sheet.perceptionShort'), String(s.passive_perception), 'sh-passive', 'sheet:passive-perception'),
  );
}

function abilities(s) {
  return h(
    'div',
    { class: 'sh-abilities', 'data-testid': 'sh-abilities' },
    ...s.abilities.map((a) =>
      h(
        'div',
        { class: 'sh-ability', 'data-ability': a.ability },
        h('span', { class: 'sh-stat-label' }, t(`abil.${a.ability}`)),
        h('strong', { class: 'sh-score' }, String(a.score)),
        h('span', { class: 'sh-mod' }, signed(a.modifier)),
        h('span', { class: a.save_proficient ? 'sh-save prof' : 'sh-save' }, t('sheet.saveShort', { n: signed(a.save_bonus) }), a.save_proficient ? h('span', { class: 'sr-only' }, ` (${t('sheet.saveProf')})`) : null),
      ),
    ),
  );
}

function skills(s) {
  return h(
    'ul',
    { class: 'sh-skills', 'data-testid': 'sh-skills' },
    ...s.skills.map((k) => {
      const mark = k.expertise ? 'expert' : k.proficient ? 'prof' : '';
      const note = k.expertise ? t('sheet.skillExpert') : k.proficient ? t('sheet.skillProf') : '';
      return h('li', { class: `sh-skill ${mark}`, 'data-skill': k.skill }, h('span', { class: 'sh-dot', 'aria-hidden': 'true' }), h('span', { class: 'sh-skill-name' }, titleCase(k.skill)), h('span', { class: 'sh-skill-bonus' }, signed(k.bonus)), note ? h('span', { class: 'sr-only' }, ` (${note})`) : null);
    }),
  );
}

function attackRow(a) {
  const art = a.item ? itemArt(a.item, { ranged: a.range_band === 'ranged' }) : '';
  return h(
    'li',
    { class: 'sh-row', 'data-attack': a.hand },
    h('span', { class: 'sh-slot', 'aria-hidden': 'true' }, art ? h('img', { src: art, alt: '', width: 26, height: 26 }) : null),
    h('span', { class: 'sh-row-main' }, h('strong', {}, a.name), h('span', { class: 'sh-row-sub' }, t(`hotbar.hand_${a.hand}`))),
    h('span', { class: 'sh-row-val' }, t('sheet.toHit', { bonus: signed(a.attack_bonus) }), h('small', {}, t('sheet.damageLine', { damage: a.damage, type: a.damage_type }))),
  );
}

function attacks(s) {
  return h(
    'ul',
    { class: 'sh-list sh-rows', 'data-testid': 'sh-attacks' },
    ...s.attacks.map(attackRow),
    h('li', { class: 'hint sh-note' }, t('sheet.attacksPer', { n: s.attacks_per_action }), ' ', t('sheet.hitNote')),
  );
}

function deathSaves(s) {
  const d = s.death_saves;
  if (s.hp > 0 && d.successes === 0 && d.failures === 0) return null;
  const row = (n, cls) => h('span', { class: 'dsave-row', 'aria-hidden': 'true' }, ...Array.from({ length: 3 }, (_, i) => h('span', { class: i < n ? `pip ${cls}` : 'pip' })));
  return block(t('sheet.deathSaves'), 'sh-deathsaves', row(d.successes, 'ok'), row(d.failures, 'fail'), h('span', { class: 'sr-only' }, `${t('sheet.deathOk', { n: d.successes })}. ${t('sheet.deathFail', { n: d.failures })}`), d.stable ? h('span', { class: 'badge stable' }, t('sheet.stable')) : null);
}

// Dense grids (abilities, saves, skills, training) get ONE corner '?' on the block heading, not one per cell.
const BLOCK_TIPS = { 'sh-ab': [['sheet:abilities']], 'sh-sk': [['sheet:skills']], 'sh-train': [['sheet:training']] };

function block(title, testid, ...children) {
  const tips = (BLOCK_TIPS[testid] ?? []).map(([key, label]) => tipButton(key, label ? t(label) : title));
  return h('section', { class: 'sh-block', 'data-testid': testid }, h('h4', {}, title, ...tips), ...children);
}

/** Features without the bare choice a named one refines ("Fighting Style" beside "Fighting Style: Archery"). */
function distinctFeatures(list) {
  return list.filter((f) => !list.some((o) => o !== f && o.name.startsWith(`${f.name}:`)));
}

function usesTag(action, resource) {
  const uses = action?.uses_max != null ? [action.uses_left, action.uses_max] : resource ? [resource.current, resource.maximum] : null;
  if (!uses) return null;
  const count = t('sheet.usesShort', { n: uses[0], max: uses[1] });
  const text = resource ? t('sheet.usesRecharge', { uses: count, recharge: t(`sheet.recharge_${resource.recharge}`) }) : count;
  return h('span', { class: 'tag sh-uses' }, text);
}

function featureRow(f, action, resource) {
  const tags = [action ? h('span', { class: 'tag' }, t(`hotbar.econ_${action.economy}`)) : null, usesTag(action, resource)];
  return h(
    'li',
    { class: 'sh-feature', 'data-testid': action ? 'sh-fa-line' : 'sh-feature', 'data-feature': f.index },
    h('div', { class: 'sh-feature-head' }, h('strong', {}, f.name), ...tags, tipButton(`${f.source === 'race' ? 'trait' : 'feature'}:${f.index}`, f.name)),
    h('p', {}, f.summary), // the summary already says what it heals or does
  );
}

function features(s) {
  const actions = s.feature_actions ?? [];
  const used = new Set();
  const rows = distinctFeatures(s.features).map((f) => {
    const action = actions.find((a) => a.feature === f.index);
    const resource = s.resources.find((r) => r.key === (action?.resource ?? f.index));
    if (resource) used.add(resource.key);
    return featureRow(f, action, resource);
  });
  // A resource no feature names (rare) still shows, so nothing the server sends is lost.
  const loose = s.resources.filter((r) => !used.has(r.key)).map((r) => h('li', { class: 'sh-feature' }, h('div', { class: 'sh-feature-head' }, h('strong', {}, titleCase(r.key)), usesTag(null, r))));
  return block(t('sheet.features'), 'sh-ft', h('ul', { class: 'sh-features' }, ...rows, ...loose));
}

function conditions(s) {
  if (!s.conditions.length) return null; // the hero strip shows conditions too
  return block(t('sheet.conditions'), 'sh-cond', h('ul', { class: 'sh-list' }, ...s.conditions.map((c) => h('li', {}, titleCase(c.name), c.rounds_left ? ` (${t('sheet.rounds', { n: c.rounds_left })})` : '', tipButton(`condition:${c.name}`, titleCase(c.name))))));
}

function training(s) {
  const join = (items) => items.map(titleCase).join(', ');
  const gear = [...s.armor_proficiencies, ...s.weapon_proficiencies];
  const line = (label, items, testid) => (items.length ? h('li', { 'data-testid': testid }, h('span', { class: 'sh-train-k' }, label), h('span', {}, join(items))) : null);
  return [
    s.resistances.length ? block(t('sheet.resistances'), 'sh-resist', h('p', {}, join(s.resistances))) : null,
    block(t('sheet.training'), 'sh-train', h('ul', { class: 'sh-train' }, line(t('sheet.trainGear'), gear, 'sh-profs'), line(t('sheet.trainTools'), s.tool_proficiencies, 'sh-tools'), line(t('sheet.languages'), s.languages, 'sh-langs'))),
  ];
}

export function renderOverview(s, spellName) {
  const conc = s.concentrating_on ? h('p', { class: 'sh-conc', 'data-testid': 'sh-conc' }, t('sheet.concentrating', { spell: spellName(s.concentrating_on) })) : null;
  return [
    vitals(s),
    conc,
    conditions(s),
    deathSaves(s),
    block(t('sheet.abilities'), 'sh-ab', abilities(s)),
    block(t('sheet.skills'), 'sh-sk', skills(s)),
    block(t('sheet.attacks'), 'sh-at', attacks(s)),
    features(s),
    ...training(s),
  ];
}
