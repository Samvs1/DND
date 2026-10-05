// Shared wizard widgets: choice cards, chip pickers, pick counters and name lookups.
import { t } from '../strings.js';
import { h } from '../ui/dom.js';

/** Add or remove `id`; with max 1 the pick behaves like a radio group. */
export function toggled(list, id, max) {
  if (list.includes(id)) return list.filter((x) => x !== id);
  if (max === 1) return [id];
  return list.length < max ? [...list, id] : list;
}

export function card({ key, selected, onSelect, art, title, lines = [], tag }) {
  return h(
    'button',
    {
      type: 'button',
      class: selected ? 'wz-card selected' : 'wz-card',
      'aria-pressed': String(Boolean(selected)),
      'data-key': key,
      onclick: onSelect,
    },
    art ? h('img', { class: 'wz-art', src: art, alt: '', width: 56, height: 56 }) : null,
    h(
      'span',
      { class: 'wz-card-body' },
      h('strong', { class: 'wz-card-title' }, title),
      ...lines.map((line) => h('span', { class: 'wz-line' }, line)),
    ),
    tag ? h('span', { class: 'tag' }, tag) : null,
  );
}

export function counter(n, max) {
  return h('p', { class: 'wz-counter', 'aria-live': 'polite' }, t('wz.chosen', { n, max }));
}

/** options: [{id, label, hint}]; locked ids render as fixed chips. */
export function chips({ prefix, options, selected, max, onToggle, locked = [] }) {
  const full = selected.length >= max;
  return h(
    'div',
    { class: 'wz-chips', role: 'group' },
    ...locked.map((o) => h('span', { class: 'wz-chip locked', title: t('wz.granted') }, o.label)),
    ...options.map((o) => {
      const on = selected.includes(o.id);
      return h(
        'button',
        {
          type: 'button',
          class: on ? 'wz-chip selected' : 'wz-chip',
          'aria-pressed': String(on),
          'data-key': `${prefix}-${o.id}`,
          disabled: !on && full,
          title: o.hint || null,
          onclick: () => onToggle(o.id),
        },
        o.label,
      );
    }),
  );
}

export function block(title, ...children) {
  return h('section', { class: 'wz-block' }, h('h3', {}, title), ...children);
}

export function namer(data) {
  const lang = new Map(data.languages.map((l) => [l.index, l.name]));
  return {
    skill: (s) => data.skills[s]?.name ?? s,
    tool: (s) => data.tools[s] ?? s,
    language: (s) => lang.get(s) ?? s,
    spell: (s) => data.spells[s]?.name ?? s,
    ability: (a) => t(`abil.${a}`),
  };
}

export function bonusText(bonuses) {
  return Object.entries(bonuses)
    .filter(([, n]) => n)
    .map(([a, n]) => `${n > 0 ? '+' : ''}${n} ${t(`abil.${a}`)}`)
    .join(', ');
}
