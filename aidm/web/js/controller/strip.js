// The hero strip of the phone (M24: just above the tab bar at the bottom): name, level and class, resources,
// conditions, the HP bar, the turn/floor status chip (with the turn timer's countdown, M15.1) and the AC on an
// iron shield.
import { conditionIcons, hpBar } from '../table/party.js';
import { myHero } from '../table/lookup.js';
import { t } from '../strings.js';
import { clear, h } from '../ui/dom.js';
import { titleCase } from '../ui/format.js';
import { everySecond } from '../ui/countdown.js';
import { statusOf } from './status.js';
import { eye, lightChip } from '../table/light.js';
import { tipButton } from '../ui/tip.js';

function resourceText(state) {
  const rows = state.sheet?.sheet?.resources ?? [];
  return rows.map((r) => t('sheet.resourceLine', { key: titleCase(r.key), current: r.current, max: r.maximum })).join(' | ');
}

function acShield(hero) {
  return h('span', { class: 'ct-ac', 'data-testid': 'strip-ac', title: t('table.ac', { n: hero.ac }) }, h('span', { class: 'ct-ac-l' }, 'AC'), h('span', { class: 'ct-ac-n' }, String(hero.ac)));
}

function hpWithTip(hero) {
  const bar = hpBar(hero);
  bar.append(tipButton('sheet:hp'));
  return bar;
}

export function mountStrip(root, store) {
  const chip = h('span', { class: 'ct-chip-status', role: 'status', 'data-testid': 'status-chip' });
  const body = h('div', { class: 'ct-strip-body' });
  const shield = h('div', { class: 'ct-strip-ac' });
  root.append(body, shield);
  let last = '';

  function renderChip(state) {
    const status = statusOf(state);
    if (chip.textContent !== status.text) chip.textContent = status.text;
    chip.dataset.status = status.key;
  }

  function render(state) {
    renderChip(state);
    const hero = myHero(state);
    const resources = resourceText(state);
    const key = JSON.stringify([hero, resources]);
    if (key === last) return;
    last = key;
    clear(body);
    clear(shield);
    if (!hero) return void body.append(h('p', { class: 'hint' }, t('ct.noHero')), chip);
    const meta = t('ct.stripMeta', { n: hero.level ?? 1, cls: titleCase(hero.class_index ?? '') });
    body.append(
      h(
        'div',
        { class: 'ct-hero-top' },
        h('strong', { 'data-testid': 'strip-name' }, hero.name),
        h('span', { class: 'ct-meta' }, meta),
        conditionIcons(hero, true),
        eye(hero),
        lightChip(hero),
        h('span', { class: 'ct-res', 'data-testid': 'strip-resources', hidden: !resources }, resources),
        chip,
      ),
      hpWithTip(hero),
    );
    shield.append(acShield(hero), tipButton('sheet:ac'));
  }
  render(store.get());
  const stopTick = everySecond(store, renderChip); // the turn countdown (M15.1)
  const stop = store.subscribe(render);
  return () => {
    stopTick();
    stop();
  };
}
