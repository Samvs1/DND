// Sheet "Inventory" tab (M25): the purse line (gold, weight carried, the shared camp supplies), worn gear as
// labelled slots, the pack as a grid of slots with counts, and ONE detail card for the item last tapped, with its
// buttons: use (a potion, on yourself or a party member), equip / unequip, give to a person here (`give`, the
// same message typed giving uses), drop. Gear changes and item use wait until a fight ends (in a fight potions go
// through the hotbar). Keepsakes (M19.3: story objects with no price) are listed under the pack.
import { t } from '../strings.js';
import { clear, h } from '../ui/dom.js';
import { putOutButton } from '../table/light.js';
import { tipButton } from '../ui/tip.js';
import { itemArt } from './item_art.js';
import { useControls as hereControls } from './item_uses.js';

const round = (n) => Math.round(n * 100) / 100;
const WEARABLE = new Set(['weapon', 'armor']);
const WORN_ORDER = ['armor', 'main_hand', 'off_hand', 'shield', 'ranged'];
const PACK_MIN = 10; // two rows of slots, empty ones included, so the grid reads as a pack

let chosen = null; // the item key last tapped; kept across re-renders of the sheet

function useControls(item, { client, locked, party, me }) {
  const pick = h('select', { class: 'inv-target', disabled: locked, 'data-testid': `use-target-${item.item}`, 'aria-label': t('sheet.useOn', { name: item.name }) }, ...party.map((p) => h('option', { value: p.id }, p.id === me ? t('sheet.useSelf') : p.name)));
  const use = () => client.send('use_item', { item_id: item.item, target_id: pick.value && pick.value !== me ? pick.value : null });
  const button = h('button', { type: 'button', class: 'btn btn-small', disabled: locked, 'data-testid': `use-${item.item}`, 'aria-label': t('sheet.useItem', { name: item.name }), onclick: use }, t('sheet.use'));
  return party.length > 1 ? [pick, button] : [button];
}

/** A Give button and the list of people here, for an item or a keepsake (M23.7; items since M25). */
function giveControl(thing, { client, locked, npcs }, ids) {
  const reason = locked ? t('sheet.giveFight') : !npcs.length ? t('sheet.giveNobody') : '';
  const list = h('ul', { class: 'inv-give-list', hidden: true, 'data-testid': ids.list, 'aria-label': t('sheet.giveWho', { item: thing.name }) });
  for (const npc of npcs) {
    const go = () => client.send('give', { npc_id: npc.id, item_id: thing.id });
    list.append(h('li', {}, h('button', { type: 'button', class: 'btn btn-small', 'data-testid': ids.to, 'data-npc': npc.id, onclick: go }, t('sheet.giveTo', { item: thing.name, name: npc.name }))));
  }
  list.append(h('li', {}, h('button', { type: 'button', class: 'btn btn-small', 'data-testid': ids.cancel, onclick: () => (list.hidden = true) }, t('sheet.giveCancel'))));
  const open = h('button', { type: 'button', class: 'btn btn-small', disabled: Boolean(reason), title: reason, 'aria-label': t('sheet.giveWho', { item: thing.name }), 'data-testid': ids.open, onclick: () => (list.hidden = !list.hidden) }, t('sheet.give'));
  return { control: h('div', { class: 'inv-give' }, open, reason ? h('span', { class: 'hint', 'data-testid': ids.reason }, reason) : null), list };
}

const ITEM_GIVE = { list: 'give-item-list', to: 'give-item-to', cancel: 'give-item-cancel', open: 'give-item', reason: 'give-item-reason' };
const KEEPSAKE_GIVE = { list: 'give-list', to: 'give-to', cancel: 'give-cancel', open: 'give-keepsake', reason: 'give-reason' };

function cell(item, label, pick) {
  const count = item && item.qty > 1 ? h('span', { class: 'inv-count' }, String(item.qty)) : null;
  const slot = h('span', { class: 'inv-slot', 'aria-hidden': 'true' }, item ? h('img', { src: itemArt(item.item, { category: item.category }), alt: '', width: 36, height: 36 }) : null, count);
  if (!item) return h('span', { class: 'inv-cell empty' }, slot);
  return h('button', { type: 'button', class: 'inv-cell', 'data-testid': 'inv-item', 'data-item': item.item, 'aria-pressed': 'false', onclick: () => pick(item.item) }, slot, label ? h('span', { class: 'inv-k' }, label) : null, h('span', { class: 'inv-name' }, item.name));
}

function detail(item, opts) {
  const { locked, client } = opts;
  const worn = Boolean(item.equipped_slot);
  const where = worn ? t('sheet.wornIn', { slot: t(`sheet.slot_${item.equipped_slot}`) }) : item.qty > 1 ? `x${item.qty}` : '';
  const meta = [where, t('sheet.weightLine', { n: round(item.weight * item.qty) }), t('sheet.valueLine', { n: round(item.value_gp * item.qty) })].filter(Boolean).join(' \u00b7 ');
  const act = (type, label, key) => h('button', { type: 'button', class: 'btn btn-small', disabled: locked, 'data-testid': `${type}-${item.item}`, 'aria-label': t(key, { name: item.name }), onclick: () => client.send(type, { item_id: item.item }) }, label);
  const wear = worn ? act('unequip', t('sheet.unequip'), 'sheet.unequipItem') : act('equip', t('sheet.equip'), 'sheet.equipItem');
  const { control, list } = giveControl({ id: item.item, name: item.name }, opts, ITEM_GIVE);
  return [
    h('span', { class: 'inv-slot', 'aria-hidden': 'true' }, h('img', { src: itemArt(item.item, { category: item.category }), alt: '', width: 32, height: 32 })),
    h('div', { class: 'inv-main' }, h('strong', { 'data-testid': 'inv-detail-name' }, item.name), tipButton(`item:${item.item}`, item.name), ...(item.uses ?? []).map((u) => tipButton(`use:${u.use_id}`, u.label)), h('div', { class: 'hint inv-meta' }, meta)),
    h('div', { class: 'inv-actions' }, ...(item.category === 'potion' ? useControls(item, opts) : []), WEARABLE.has(item.category) ? wear : null, control, act('drop', t('sheet.drop'), 'sheet.dropItem')),
    ...hereControls(item, opts),
    list,
  ];
}

function slotOrder(item) {
  const at = WORN_ORDER.indexOf(item.equipped_slot);
  return at < 0 ? WORN_ORDER.length : at;
}

export function renderInventory(s, { client, camp, locked, party = [], npcs = [], here = {} }) {
  const others = party.filter((p) => p.id !== s.id);
  const opts = { client, locked, party: [{ id: s.id, name: s.name }, ...others], me: s.id, npcs, ...here };
  const weight = round(s.inventory.reduce((n, i) => n + i.weight * i.qty, 0));
  const worn = s.inventory.filter((i) => i.equipped_slot).sort((a, b) => slotOrder(a) - slotOrder(b));
  const pack = s.inventory.filter((i) => !i.equipped_slot);
  if (!s.inventory.some((i) => i.item === chosen)) chosen = (worn[0] ?? pack[0])?.item ?? null;
  const card = h('section', { class: 'inv-detail', 'data-testid': 'inv-detail', 'aria-live': 'polite' });
  const cells = [];
  const pick = (key) => {
    chosen = key;
    cells.forEach((c) => c.setAttribute('aria-pressed', c.dataset.item === key ? 'true' : 'false'));
    clear(card);
    const item = s.inventory.find((i) => i.item === key);
    if (item) card.append(...detail(item, opts).filter(Boolean));
  };
  const wornGrid = h('div', { class: 'inv-worn' }, ...worn.map((i) => cell(i, t(`sheet.slot_${i.equipped_slot}`), pick)));
  const packGrid = h('div', { class: 'inv-pack' }, ...pack.map((i) => cell(i, '', pick)), ...Array.from({ length: Math.max(0, PACK_MIN - pack.length) }, () => cell(null, '', pick)));
  cells.push(...wornGrid.querySelectorAll('[data-item]'), ...packGrid.querySelectorAll('[data-item]'));
  if (chosen) pick(chosen);
  return [
    h(
      'div',
      { class: 'inv-purse' },
      h('p', { class: 'sh-gold', 'data-testid': 'sh-gold' }, h('strong', {}, t('sheet.goldShort', { n: s.gold })), h('span', {}, t('sheet.carriedShort', { n: weight }))),
      h('p', { class: 'sh-supplies', 'data-testid': 'sh-supplies' }, t('sheet.suppliesShort', { n: camp })),
    ),
    here.light ? h('p', { class: 'inv-light', 'data-testid': 'inv-light' }, t('light.litChip', { name: here.light }), ' ', putOutButton(client)) : null,
    locked ? h('p', { class: 'hint' }, t('sheet.gearLocked')) : null,
    s.inventory.length
      ? h(
          'div',
          { class: 'inv-list', 'data-testid': 'inv-list' },
          worn.length ? h('section', { class: 'sh-block' }, h('h4', {}, t('sheet.worn')), wornGrid) : null,
          chosen ? card : null,
          h('section', { class: 'sh-block' }, h('h4', {}, t('sheet.pack')), packGrid),
        )
      : h('p', { class: 'hint' }, t('sheet.invEmpty')),
    s.inventory.some((i) => i.category === 'potion') ? h('p', { class: 'hint' }, t('sheet.potionHint')) : null,
    ...keepsakes(s.keepsakes ?? [], { client, locked, npcs }),
  ];
}

function keepsakeLine(k, opts) {
  const note = k.quest_title ? t('sheet.questItem', { title: k.quest_title }) : t('sheet.keepsakeOnly');
  const { control, list } = giveControl(k, opts, KEEPSAKE_GIVE);
  return h(
    'li',
    { class: `inv-line keepsake${k.quest_title ? ' quest-item' : ''}`, 'data-testid': 'keepsake', 'data-keepsake': k.id },
    h('div', { class: 'inv-main' }, h('strong', {}, k.name), tipButton(k.quest_title ? 'sheet:quest-item' : 'sheet:keepsake', k.name), h('div', { class: 'hint', 'data-testid': 'keepsake-note' }, note), k.description ? h('div', { class: 'hint inv-meta' }, k.description) : null),
    control,
    list,
  );
}

function keepsakes(list, opts) {
  if (!list.length) return [];
  return [h('h3', {}, t('sheet.keepsakes')), h('p', { class: 'hint' }, t('sheet.keepsakesHint')), h('ul', { class: 'inv-list', 'data-testid': 'keepsake-list' }, ...list.map((k) => keepsakeLine(k, opts)))];
}
