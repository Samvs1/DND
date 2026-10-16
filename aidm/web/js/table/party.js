// Party panel: portrait, name, class line, HP bar (with temp HP), AC, condition icons, dying or fallen
// state and the level-up badge. Art only through assetUrl.
import { assetUrl } from '../assets.js';
import { mySeat } from '../state.js';
import { t } from '../strings.js';
import { clear, h } from '../ui/dom.js';
import { titleCase } from '../ui/format.js';
import { publicState } from './lookup.js';

/** The hero's own portrait, else real class art, else a generic face (assetUrl prefers real art). */
export function portraitKeys(creature) {
  const keys = [];
  if (creature.portrait_id) keys.push(`portrait.${creature.portrait_id}`);
  if (creature.class_index) keys.push(`portrait.class.${creature.class_index}`);
  keys.push('portrait.npc.commoner');
  return keys;
}

export function hpBar(c) {
  const ratio = c.max_hp > 0 ? Math.max(0, Math.min(1, c.hp / c.max_hp)) : 0;
  const level = ratio > 0.5 ? 'good' : ratio > 0.25 ? 'warn' : 'low';
  const fill = h('span', { class: `hp-fill ${level}` });
  fill.style.width = `${Math.round(ratio * 100)}%`;
  const temp = c.temp_hp > 0 ? ` +${c.temp_hp}` : '';
  return h(
    'div',
    { class: 'hp-wrap' },
    h(
      'div',
      { class: 'hp', role: 'progressbar', 'aria-valuemin': 0, 'aria-valuemax': c.max_hp, 'aria-valuenow': c.hp, 'aria-label': t('table.hp') },
      fill,
    ),
    h('span', { class: 'hp-text', 'data-testid': 'hp-text' }, `${c.hp}/${c.max_hp}${temp}`),
  );
}

export function conditionIcons(c) {
  return h(
    'span',
    { class: 'conditions' },
    ...c.conditions.map((id) =>
      h('img', { class: 'cond', src: assetUrl(`condition_icon.${id}`), alt: titleCase(id), title: titleCase(id), width: 20, height: 20 }),
    ),
  );
}

function deathSaves(c) {
  if (c.dead || !(c.dying || c.stable)) return null;
  const marks = (n, cls) => Array.from({ length: 3 }, (_, i) => h('span', { class: i < n ? `pip ${cls}` : 'pip' }));
  return h(
    'span',
    { class: 'dsaves', 'data-testid': 'death-saves', title: t('table.dyingHint') },
    h('span', { class: 'sr-only' }, t('table.deathSaves', { ok: c.death_save_successes ?? 0, fail: c.death_save_failures ?? 0 })),
    h('span', { 'aria-hidden': 'true', class: 'dsave-row' }, ...marks(c.death_save_successes ?? 0, 'ok')),
    h('span', { 'aria-hidden': 'true', class: 'dsave-row' }, ...marks(c.death_save_failures ?? 0, 'fail')),
  );
}

function stateBadges(c, levelUp) {
  return [
    c.dead ? h('span', { class: 'badge dead' }, t('table.fallen')) : null,
    !c.dead && c.dying ? h('span', { class: 'badge dying', title: t('table.dyingHint') }, t('table.dying')) : null,
    !c.dead && c.stable ? h('span', { class: 'badge stable' }, t('table.stable')) : null,
    deathSaves(c),
    levelUp ? h('span', { class: 'badge levelup', 'data-testid': 'levelup-badge' }, t('table.levelUp')) : null,
  ];
}

function card(c, state, store) {
  const mine = mySeat(state)?.creature_id === c.id;
  const level = state.levelUps[c.id];
  const classes = ['pcard', mine ? 'mine' : '', c.dead ? 'dead' : '', c.dying ? 'dying' : ''].join(' ').trim();
  return h(
    'li',
    { class: classes, 'data-creature': c.id, 'data-testid': 'party-card' },
    h('img', { class: 'pc-portrait', src: assetUrl(portraitKeys(c)), alt: '', width: 48, height: 48 }),
    h(
      'div',
      { class: 'pc-body' },
      h('div', { class: 'pc-name' }, h('strong', {}, c.name), mine ? h('span', { class: 'tag' }, t('lobby.you')) : null),
      h('div', { class: 'pc-sub' }, t('table.classLine', { level: c.level ?? 1, race: titleCase(c.race), cls: titleCase(c.class_index) })),
      hpBar(c),
      h('div', { class: 'pc-meta' }, h('span', { class: 'pc-ac', title: t('table.ac', { n: c.ac }) }, h('small', {}, 'AC'), h('b', {}, String(c.ac))), conditionIcons(c), ...stateBadges(c, level && (c.level ?? 1) < level)),
      mine ? h('button', { type: 'button', class: 'btn btn-small sheet-open', 'data-testid': 'sheet-open', onclick: () => store.update({ sheetOpen: true }) }, t('sheet.open')) : null,
    ),
  );
}

export function mountParty(root, store) {
  const list = h('ul', { class: 'party', 'data-testid': 'party' });
  root.append(h('h3', { class: 'side-h' }, t('table.party')), list);
  let last = '';

  function render(state) {
    const view = publicState(state);
    if (!view) return;
    const key = JSON.stringify([view.party, state.levelUps, state.me.playerId, state.players.map((p) => p.creature_id)]);
    if (key === last) return;
    last = key;
    clear(list);
    for (const c of view.party) list.append(card(c, state, store));
  }
  render(store.get());
  return store.subscribe(render);
}
