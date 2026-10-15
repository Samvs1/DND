// Sheet "Inventory" tab: carried items with weight and value, equipped slots, equip / unequip / drop (server
// messages), potions used outside a fight on yourself or a party member (`use_item`), gold and the shared camp
// supplies. Gear changes and item use wait until a fight ends (in a fight potions go through the hotbar).
// Keepsakes (M19.3: story objects with no price) are listed under the items.
import { assetUrl } from '../assets.js';
import { t } from '../strings.js';
import { h } from '../ui/dom.js';

const round = (n) => Math.round(n * 100) / 100;
const WEARABLE = new Set(['weapon', 'armor']);

function useControls(item, { client, locked, party, me }) {
  const pick = h('select', { class: 'inv-target', disabled: locked, 'data-testid': `use-target-${item.item}`, 'aria-label': t('sheet.useOn', { name: item.name }) }, ...party.map((p) => h('option', { value: p.id }, p.id === me ? t('sheet.useSelf') : p.name)));
  const use = () => client.send('use_item', { item_id: item.item, target_id: pick.value && pick.value !== me ? pick.value : null });
  const button = h('button', { type: 'button', class: 'btn btn-small', disabled: locked, 'data-testid': `use-${item.item}`, 'aria-label': t('sheet.useItem', { name: item.name }), onclick: use }, t('sheet.use'));
  return party.length > 1 ? [pick, button] : [button];
}

function line(item, opts) {
  const { locked, client } = opts;
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
    h('div', { class: 'inv-actions' }, ...(item.category === 'potion' ? useControls(item, opts) : []), WEARABLE.has(item.category) ? wear : null, act('drop', t('sheet.drop'), 'sheet.dropItem')),
  );
}

export function renderInventory(s, { client, camp, locked, party = [], npcs = [] }) {
  const others = party.filter((p) => p.id !== s.id);
  const opts = { client, locked, party: [{ id: s.id, name: s.name }, ...others], me: s.id };
  const weight = round(s.inventory.reduce((n, i) => n + i.weight * i.qty, 0));
  return [
    h('p', { class: 'sh-gold', 'data-testid': 'sh-gold' }, t('sheet.gold', { n: s.gold }), ' ', t('sheet.carried', { n: weight })),
    h('p', { class: 'sh-supplies', 'data-testid': 'sh-supplies' }, t('sheet.supplies', { n: camp })),
    locked ? h('p', { class: 'hint' }, t('sheet.gearLocked')) : null,
    s.inventory.length ? h('ul', { class: 'inv-list', 'data-testid': 'inv-list' }, ...s.inventory.map((i) => line(i, opts))) : h('p', { class: 'hint' }, t('sheet.invEmpty')),
    s.inventory.some((i) => i.category === 'potion') ? h('p', { class: 'hint' }, t('sheet.potionHint')) : null,
    ...keepsakes(s.keepsakes ?? [], { client, locked, npcs }),
  ];
}

/** Give one keepsake to a person here (M23.7): a generic Give, so the button never hints at what a quest needs. */
function giveControl(k, { client, locked, npcs }) {
  const reason = locked ? t('sheet.giveFight') : !npcs.length ? t('sheet.giveNobody') : '';
  const list = h('ul', { class: 'inv-give-list', hidden: true, 'data-testid': 'give-list', 'aria-label': t('sheet.giveWho', { item: k.name }) });
  for (const npc of npcs) {
    const go = () => client.send('give', { npc_id: npc.id, item_id: k.id });
    list.append(h('li', {}, h('button', { type: 'button', class: 'btn btn-small', 'data-testid': 'give-to', 'data-npc': npc.id, onclick: go }, t('sheet.giveTo', { item: k.name, name: npc.name }))));
  }
  const open = h('button', { type: 'button', class: 'btn btn-small', disabled: Boolean(reason), title: reason, 'aria-label': t('sheet.giveWho', { item: k.name }), 'data-testid': 'give-keepsake', onclick: () => (list.hidden = !list.hidden) }, t('sheet.give'));
  return h('div', { class: 'inv-give' }, open, reason ? h('span', { class: 'hint', 'data-testid': 'give-reason' }, reason) : null, list);
}

function keepsakeLine(k, opts) {
  const note = k.quest_title ? t('sheet.questItem', { title: k.quest_title }) : t('sheet.keepsakeOnly');
  return h(
    'li',
    { class: `inv-line keepsake${k.quest_title ? ' quest-item' : ''}`, 'data-testid': 'keepsake', 'data-keepsake': k.id },
    h('div', { class: 'inv-main' }, h('strong', {}, k.name), h('div', { class: 'hint', 'data-testid': 'keepsake-note' }, note), k.description ? h('div', { class: 'hint inv-meta' }, k.description) : null),
    giveControl(k, opts),
  );
}

function keepsakes(list, opts) {
  if (!list.length) return [];
  return [h('h3', {}, t('sheet.keepsakes')), h('p', { class: 'hint' }, t('sheet.keepsakesHint')), h('ul', { class: 'inv-list', 'data-testid': 'keepsake-list' }, ...list.map((k) => keepsakeLine(k, opts)))];
}
