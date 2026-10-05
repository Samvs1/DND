// Step 3: background (two skills, tools, starting gear, one flavour line).
import { t } from '../strings.js';
import { h } from '../ui/dom.js';
import { card, namer } from './ui.js';

function details(env) {
  const { data, ctx } = env;
  if (!ctx.bg) return h('div', {});
  const names = namer(data);
  const bg = ctx.bg;
  const gear = bg.gear.map((g) => (g.qty > 1 ? `${g.name} x${g.qty}` : g.name)).join(', ');
  return h(
    'div',
    { class: 'wz-details panel' },
    h('h3', {}, bg.name),
    h('p', {}, bg.flavour),
    h(
      'ul',
      { class: 'wz-facts' },
      h('li', {}, t('wz.skillsGranted', { list: bg.skills.map(names.skill).join(', ') })),
      bg.tools.length ? h('li', {}, t('wz.toolsGranted', { list: bg.tools.map(names.tool).join(', ') })) : null,
      h('li', {}, t('wz.gear', { list: gear })),
    ),
  );
}

export function renderBackground(env) {
  const { data, draft, update } = env;
  const names = namer(data);
  const cards = data.backgrounds.map((bg) =>
    card({
      key: `bg-${bg.index}`,
      selected: draft.background === bg.index,
      title: bg.name,
      lines: [bg.skills.map(names.skill).join(', ')],
      onSelect: () => update((d) => (d.background = bg.index)),
    }),
  );
  return h('div', {}, h('div', { class: 'wz-cards' }, ...cards), details(env));
}
