// Sheet "Overview" tab: vitals, abilities and saves, skills, attacks, features and feature actions (uses left),
// conditions, death saves, resources, proficiencies. Pure rendering of the derived `CharacterSheet` the server sent.
import { t } from '../strings.js';
import { h } from '../ui/dom.js';
import { titleCase } from '../ui/format.js';

const signed = (n) => (n >= 0 ? `+${n}` : String(n));

function stat(label, value, testid, note) {
  return h('div', { class: 'sh-stat', 'data-testid': testid }, h('span', { class: 'sh-stat-label' }, label), h('strong', { class: 'sh-stat-value' }, value), note ? h('span', { class: 'sh-stat-note' }, note) : null);
}

function vitals(s) {
  const temp = s.temp_hp > 0 ? t('sheet.tempHp', { n: s.temp_hp }) : null;
  return h(
    'div',
    { class: 'sh-vitals' },
    stat(t('sheet.ac'), String(s.ac), 'sh-ac'),
    stat(t('sheet.hp'), `${s.hp}/${s.max_hp}`, 'sh-hp', temp),
    stat(t('sheet.speed'), t('sheet.speedFeet', { n: s.speed }), 'sh-speed'),
    stat(t('sheet.initiative'), signed(s.initiative_bonus), 'sh-init', t('sheet.initiativeNote', { bonus: signed(s.initiative_bonus) })),
    stat(t('sheet.proficiency'), signed(s.proficiency_bonus), 'sh-prof'),
    stat(t('sheet.passive'), String(s.passive_perception), 'sh-passive'),
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

function attacks(s) {
  return h(
    'ul',
    { class: 'sh-list', 'data-testid': 'sh-attacks' },
    ...s.attacks.map((a) => h('li', {}, h('strong', {}, a.name), ' ', t('sheet.attackLine', { bonus: signed(a.attack_bonus), damage: a.damage, type: a.damage_type }))),
    h('li', { class: 'hint' }, t('sheet.attacksPer', { n: s.attacks_per_action }), ' ', t('sheet.hitNote')),
  );
}

function deathSaves(s) {
  const d = s.death_saves;
  if (s.hp > 0 && d.successes === 0 && d.failures === 0) return null;
  const row = (n, cls) => h('span', { class: 'dsave-row', 'aria-hidden': 'true' }, ...Array.from({ length: 3 }, (_, i) => h('span', { class: i < n ? `pip ${cls}` : 'pip' })));
  return block(t('sheet.deathSaves'), 'sh-deathsaves', row(d.successes, 'ok'), row(d.failures, 'fail'), h('span', { class: 'sr-only' }, `${t('sheet.deathOk', { n: d.successes })}. ${t('sheet.deathFail', { n: d.failures })}`), d.stable ? h('span', { class: 'badge stable' }, t('sheet.stable')) : null);
}

function block(title, testid, ...children) {
  return h('section', { class: 'sh-block', 'data-testid': testid }, h('h4', {}, title), ...children);
}

function features(s) {
  return h('ul', { class: 'sh-features' }, ...s.features.map((f) => h('li', {}, h('details', {}, h('summary', {}, f.name), h('p', {}, f.summary)))));
}

function featureActions(s) {
  const list = s.feature_actions ?? [];
  if (!list.length) return null;
  const rows = list.map((f) =>
    h('li', { 'data-testid': 'sh-fa-line', 'data-feature': f.feature }, h('strong', {}, f.name), ` (${t(`hotbar.econ_${f.economy}`)})`, f.uses_max != null ? `, ${t('sheet.featureUses', { n: f.uses_left, max: f.uses_max })}` : '', f.heal ? `, ${t('hotbar.tip_heal', { dice: f.heal })}` : ''),
  );
  return block(t('sheet.featureActions'), 'sh-fa', h('ul', { class: 'sh-list' }, ...rows));
}

function conditions(s) {
  if (!s.conditions.length) return h('p', { class: 'hint' }, t('sheet.noConditions'));
  return h('ul', { class: 'sh-list' }, ...s.conditions.map((c) => h('li', {}, titleCase(c.name), c.rounds_left ? ` (${t('sheet.rounds', { n: c.rounds_left })})` : '')));
}

function resources(s) {
  if (!s.resources.length) return null;
  const rows = s.resources.map((r) => h('li', {}, t('sheet.resourceLine', { key: titleCase(r.key), current: r.current, max: r.maximum }), ` (${t(`sheet.recharge_${r.recharge}`)})`));
  return block(t('sheet.resources'), 'sh-res', h('ul', { class: 'sh-list' }, ...rows));
}

function lists(s) {
  const join = (items) => items.map(titleCase).join(', ');
  return [
    s.resistances.length ? block(t('sheet.resistances'), 'sh-resist', h('p', {}, join(s.resistances))) : null,
    block(t('sheet.proficiencies'), 'sh-profs', h('p', {}, join([...s.armor_proficiencies, ...s.weapon_proficiencies, ...s.tool_proficiencies]))),
    block(t('sheet.languages'), 'sh-langs', h('p', {}, join(s.languages))),
  ];
}

export function renderOverview(s, spellName) {
  const conc = s.concentrating_on ? h('p', { class: 'sh-conc', 'data-testid': 'sh-conc' }, t('sheet.concentrating', { spell: spellName(s.concentrating_on) })) : null;
  return [
    vitals(s),
    conc,
    block(t('sheet.abilities'), 'sh-ab', abilities(s)),
    block(t('sheet.skills'), 'sh-sk', skills(s)),
    block(t('sheet.attacks'), 'sh-at', attacks(s)),
    block(t('sheet.features'), 'sh-ft', features(s)),
    featureActions(s),
    block(t('sheet.conditions'), 'sh-cond', conditions(s)),
    deathSaves(s),
    resources(s),
    ...lists(s),
  ];
}
