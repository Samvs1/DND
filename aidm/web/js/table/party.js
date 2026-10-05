// Party panel: portrait, name, class line, HP bar (with temp HP), AC, condition icons, dying or fallen
// state and the level-up badge. Art only through assetUrl.
import { assetUrl } from '../assets.js';
import { mySeat } from '../state.js';
import { t } from '../strings.js';
import { clear, h } from '../ui/dom.js';
import { titleCase } from '../ui/format.js';
import { publicState } from './lookup.js';

export function portraitKeys(creature) {
  const own = creature.portrait_id ? `portrait.${creature.portrait_id}` : null;
  const fallback = creature.class_index ? `portrait.class.${creature.class_index}` : 'portrait.npc.commoner';
  return own ?? fallback;
}

function hpBar(c) {
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

function conditionIcons(c) {
  return h(
    'span',
    { class: 'conditions' },
    ...c.conditions.map((id) =>
      h('img', { class: 'cond', src: assetUrl(`condition_icon.${id}`), alt: titleCase(id), title: titleCase(id), width: 20, height: 20 }),
    ),
  );
}

function stateBadges(c, levelUp) {
  return [
    c.dead ? h('span', { class: 'badge dead' }, t('table.fallen')) : null,
    !c.dead && c.dying ? h('span', { class: 'badge dying', title: t('table.dyingHint') }, t('table.dying')) : null,
    levelUp ? h('span', { class: 'badge levelup', 'data-testid': 'levelup-badge' }, t('table.levelUp')) : null,
  ];
}

function card(c, state) {
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
      h('div', { class: 'pc-meta' }, h('span', {}, t('table.ac', { n: c.ac })), conditionIcons(c), ...stateBadges(c, level && (c.level ?? 1) < level)),
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
    for (const c of view.party) list.append(card(c, state));
  }
  render(store.get());
  return store.subscribe(render);
}
