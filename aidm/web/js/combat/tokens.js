// Token chips: one creature in the fight (portrait or monster token, name, HP bar for the party and a
// coarse state for enemies, condition icons). Art only through assetUrl.
import { assetUrl } from '../assets.js';
import { portraitKeys } from '../table/party.js';
import { t } from '../strings.js';
import { h } from '../ui/dom.js';
import { titleCase } from '../ui/format.js';
import { healthState, isEnemy } from './model.js';

function flame(flags) {
  return flags.flame ? h('img', { class: 'tk-flame', 'data-testid': 'token-flame', src: assetUrl('zone_icon.lit'), alt: t('light.lit'), title: t('light.lit'), width: 16, height: 16 }) : null;
}

export function tokenArt(token, hero) {
  if (hero) return assetUrl(portraitKeys(hero));
  const index = token.monster_index || token.creature_id.replace(/-?\d+$/, '');
  return assetUrl([`monster_token.${index}`, 'monster_token.goblin']);
}

function hpBar(token) {
  const ratio = token.max_hp > 0 ? Math.max(0, Math.min(1, token.hp / token.max_hp)) : 0;
  const level = ratio > 0.5 ? 'good' : ratio > 0.25 ? 'warn' : 'low';
  const fill = h('span', { class: `hp-fill ${level}` });
  fill.style.width = `${Math.round(ratio * 100)}%`;
  return h(
    'span',
    { class: 'tk-hp' },
    h('span', { class: 'hp', 'aria-hidden': 'true' }, fill),
    h('span', { class: 'tk-hp-text' }, `${token.hp}/${token.max_hp}`),
  );
}

function conditions(token) {
  if (!token.conditions.length) return null;
  return h(
    'span',
    { class: 'conditions', 'aria-label': t('combat.conditions') },
    ...token.conditions.map((id) =>
      h('img', { class: 'cond', src: assetUrl(`condition_icon.${id}`), alt: titleCase(id), title: titleCase(id), width: 18, height: 18 }),
    ),
  );
}

function stateOf(token) {
  if (token.withdrawn) return 'fled';
  return healthState(token);
}

/** One chip. `flags`: {active, targeted, mine, pickable}. Returns a <button> so it is keyboard operable. */
export function tokenChip(token, { hero, zoneName, flags, onPick }) {
  const state = stateOf(token);
  const enemy = isEnemy(token);
  const classes = ['tk', enemy ? 'foe' : 'ally', `is-${state}`, flags.active ? 'active' : '', flags.targeted ? 'targeted' : '', flags.mine ? 'mine' : '', flags.pickable ? 'pickable' : '']
    .filter(Boolean)
    .join(' ');
  const label = t('combat.tokenLabel', { name: token.name, state: t(`combat.${state}`), zone: zoneName });
  return h(
    'button',
    { type: 'button', class: classes, 'data-testid': 'token', 'data-creature': token.creature_id, 'data-side': token.side, 'aria-label': label, 'aria-pressed': flags.targeted ? 'true' : 'false', onclick: () => onPick(token) },
    h('img', { class: 'tk-art', src: tokenArt(token, hero), alt: '', width: 40, height: 40 }),
    h(
      'span',
      { class: 'tk-body' },
      h('span', { class: 'tk-name' }, token.name),
      hero || !enemy ? hpBar(token) : h('span', { class: `tk-state state-${state}`, 'data-testid': 'enemy-state' }, t(`combat.${state}`)),
      conditions(token),
    ),
    flame(flags),
    flags.targeted ? h('span', { class: 'tk-flag' }, t('combat.targeted')) : null,
  );
}
