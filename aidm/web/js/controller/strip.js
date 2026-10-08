// Persistent top strip of the phone: hero portrait and name, HP bar, AC, conditions, a resources summary and
// the turn/floor status chip.
import { assetUrl } from '../assets.js';
import { conditionIcons, hpBar, portraitKeys } from '../table/party.js';
import { myHero } from '../table/lookup.js';
import { t } from '../strings.js';
import { clear, h } from '../ui/dom.js';
import { titleCase } from '../ui/format.js';
import { statusOf } from './status.js';

function resourceText(state) {
  const rows = state.sheet?.sheet?.resources ?? [];
  return rows.map((r) => t('sheet.resourceLine', { key: titleCase(r.key), current: r.current, max: r.maximum })).join(' | ');
}

export function mountStrip(root, store) {
  const chip = h('span', { class: 'ct-chip-status', role: 'status', 'data-testid': 'status-chip' });
  const body = h('div', { class: 'ct-strip-body' });
  root.append(body, chip);
  let last = '';

  function render(state) {
    const hero = myHero(state);
    const status = statusOf(state);
    const resources = resourceText(state);
    const key = JSON.stringify([hero, status, resources]);
    if (key === last) return;
    last = key;
    chip.textContent = status.text;
    chip.dataset.status = status.key;
    clear(body);
    if (!hero) return void body.append(h('p', { class: 'hint' }, t('ct.noHero')));
    body.append(
      h('img', { class: 'ct-portrait', src: assetUrl(portraitKeys(hero)), alt: '', width: 40, height: 40 }),
      h(
        'div',
        { class: 'ct-hero' },
        h('div', { class: 'ct-hero-top' }, h('strong', { 'data-testid': 'strip-name' }, hero.name), h('span', { class: 'ct-ac', 'data-testid': 'strip-ac' }, t('table.ac', { n: hero.ac })), conditionIcons(hero)),
        hpBar(hero),
        resources ? h('p', { class: 'ct-res hint', 'data-testid': 'strip-resources' }, resources) : null,
      ),
    );
  }
  render(store.get());
  return store.subscribe(render);
}
