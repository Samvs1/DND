// Sheet "Inventory" tab: carried items with weight and value, equipped slots, equip / unequip / drop (server
// messages), gold and the shared camp supplies. Gear changes wait until a fight ends.
import { assetUrl } from '../assets.js';
import { t } from '../strings.js';
import { h } from '../ui/dom.js';

const round = (n) => Math.round(n * 100) / 100;
const WEARABLE = new Set(['weapon', 'armor']);

function line(item, locked, client) {
  const total = round(item.weight * item.qty);
  const worn = Boolean(item.equipped_slot);
  const act = (type, label, key) =>
    h('button', { type: 'button', class: 'btn btn-small', disabled: locked, 'data-testid': `${type}-${item.item}`, 'aria-label': t(key, { name: item.name }), onclick: () => client.send(type, { item_id: item.item }) }, label);
  const wear = worn ? act('unequip', t('sheet.unequip'), 'sheet.unequipItem') : act('equip', t('sheet.equip'), 'sheet.equipItem');
  return h(
    'li',
    { class: `inv-line${worn ? ' worn' : ''}`, 'data-testid': 'inv-line', 'data-item': item.item },
    h('img', { src: assetUrl([`item_icon.${item.item}`, `item_icon.${item.category || 'gear'}`]), alt: '', width: 32, height: 32 }),
    h(
      'div',
      { class: 'inv-main' },
      h('strong', {}, item.name),
      item.qty > 1 ? h('span', { class: 'hint' }, ` x${item.qty}`) : null,
      worn ? h('span', { class: 'tag', 'data-testid': 'inv-slot' }, `${t('sheet.equipped')}: ${t(`sheet.slot_${item.equipped_slot}`)}`) : null,
      h('div', { class: 'hint inv-meta' }, `${t('sheet.weightLine', { n: total })}, ${t('sheet.valueLine', { n: round(item.value_gp * item.qty) })}`),
    ),
    h('div', { class: 'inv-actions' }, WEARABLE.has(item.category) ? wear : null, act('drop', t('sheet.drop'), 'sheet.dropItem')),
  );
}

export function renderInventory(s, { client, camp, locked }) {
  const weight = round(s.inventory.reduce((n, i) => n + i.weight * i.qty, 0));
  return [
    h('p', { class: 'sh-gold', 'data-testid': 'sh-gold' }, t('sheet.gold', { n: s.gold }), ' ', t('sheet.carried', { n: weight })),
    h('p', { class: 'sh-supplies', 'data-testid': 'sh-supplies' }, t('sheet.supplies', { n: camp })),
    locked ? h('p', { class: 'hint' }, t('sheet.gearLocked')) : null,
    s.inventory.length ? h('ul', { class: 'inv-list', 'data-testid': 'inv-list' }, ...s.inventory.map((i) => line(i, locked, client))) : h('p', { class: 'hint' }, t('sheet.invEmpty')),
    s.inventory.some((i) => i.category === 'potion') ? h('p', { class: 'hint' }, t('sheet.potionHint')) : null,
  ];
}
