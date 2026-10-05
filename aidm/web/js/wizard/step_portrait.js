// Step 8: preset portraits (art through assetUrl portrait keys). The class portrait (real v1 art) comes
// first, then the race portraits; the table shows the class art for a portrait that has no real art yet.
import { assetUrl } from '../assets.js';
import { t } from '../strings.js';
import { h } from '../ui/dom.js';

function ordered(env) {
  const { data, draft } = env;
  const first = (p) => (p.id === `class.${draft.cls}` ? 0 : p.race === draft.race ? 1 : 2);
  return [...data.portraits].sort((a, b) => first(a) - first(b));
}

export function renderPortrait(env) {
  const { draft, update } = env;
  const tiles = ordered(env).map((p) => {
    const on = draft.portrait === p.id;
    return h(
      'button',
      {
        type: 'button',
        class: on ? 'wz-portrait selected' : 'wz-portrait',
        'aria-pressed': String(on),
        'aria-label': p.label,
        'data-key': `portrait-${p.id}`,
        onclick: () => update((d) => (d.portrait = p.id)),
      },
      h('img', { src: assetUrl(p.key), alt: '', width: 96, height: 96 }),
      h('span', {}, p.label),
    );
  });
  return h('div', {}, h('p', { class: 'hint' }, t('wz.portraitHint')), h('div', { class: 'wz-portraits' }, ...tiles));
}
