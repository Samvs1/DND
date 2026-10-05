// Shop panel: when a shop is open (`shop_stock` arrived and the scene still has that shop open) it lists the
// stock with prices and a Buy button, the hero's pack with Sell buttons, gold and camp supplies. Refusals come
// back as typed codes (`shop_<reason>`) and are shown as friendly text. With no open shop it offers a Trade
// button per shopkeeper in the party's place; that opens the table's shop vote.
import { assetUrl } from '../assets.js';
import { t } from '../strings.js';
import { createPanel } from '../ui/modal.js';
import { clear, h } from '../ui/dom.js';
import { myHero, publicState } from '../table/lookup.js';
import { sellPrice, sellable } from './pricing.js';

function stockRow(line, ctx) {
  const { gold, qty, send } = ctx;
  const price = line.price_gp * qty();
  const buy = h('button', { type: 'button', class: 'btn btn-small', 'data-testid': 'shop-buy', 'data-item': line.item_id, 'aria-label': t('shop.buyOne', { name: line.name }), disabled: gold < line.price_gp * qty(), onclick: () => send('shop_buy', line) }, t('shop.buy'));
  return h(
    'li',
    { class: 'shop-line', 'data-testid': 'shop-line', 'data-item': line.item_id },
    h('img', { src: assetUrl([`item_icon.${line.item_id}`, `item_icon.${line.category || 'gear'}`]), alt: '', width: 32, height: 32 }),
    h('div', { class: 'shop-main' }, h('strong', {}, line.name), line.supply ? h('span', { class: 'hint' }, ` ${t('shop.supplyLine', { n: line.supply })}`) : null),
    h('span', { class: 'shop-price' }, t('shop.price', { n: price })),
    buy,
  );
}

function packRow(item, ctx) {
  const each = sellPrice(item);
  const sell = h('button', { type: 'button', class: 'btn btn-small', 'data-testid': 'shop-sell', 'data-item': item.item, 'aria-label': t('shop.sellOne', { name: item.name }), onclick: () => ctx.send('shop_sell', { item_id: item.item, name: item.name }) }, t('shop.sell'));
  return h(
    'li',
    { class: 'shop-line', 'data-testid': 'shop-pack-line', 'data-item': item.item },
    h('img', { src: assetUrl([`item_icon.${item.item}`, `item_icon.${item.category || 'gear'}`]), alt: '', width: 32, height: 32 }),
    h('div', { class: 'shop-main' }, h('strong', {}, item.name), item.qty > 1 ? h('span', { class: 'hint' }, ` x${item.qty}`) : null),
    h('span', { class: 'shop-price' }, t('shop.sellFor', { n: each })),
    sell,
  );
}

function closedView(view, client, store) {
  const keepers = (view.scene?.npcs ?? []).filter((n) => (view.scene?.shopkeepers ?? []).includes(n.id));
  if (!keepers.length) return [h('p', { class: 'hint', 'data-testid': 'shop-closed' }, `${t('shop.closed')} ${t('shop.nobody')}`)];
  const rows = keepers.map((npc) =>
    h(
      'li',
      {},
      h('button', { type: 'button', class: 'btn', 'data-testid': 'shop-visit', 'data-npc': npc.id, onclick: () => { client.send('submit_action', { text: `trade with ${npc.name}` }); store.update({ panel: null }); } }, t('shop.visit', { name: npc.name })),
    ),
  );
  return [h('p', { class: 'hint', 'data-testid': 'shop-closed' }, t('shop.closed')), h('ul', { class: 'shop-visit-list' }, ...rows), h('p', { class: 'hint' }, t('shop.visitHint'))];
}

export function mountShop(root, ctx) {
  const { store, client } = ctx;
  const panel = createPanel(root, store, { key: 'shop', title: t('shop.title'), testid: 'shop' });
  const status = h('p', { class: 'form-error shop-status', role: 'status', 'data-testid': 'shop-status' });
  const qtyInput = h('input', { type: 'number', min: 1, max: 99, value: 1, id: 'shop-qty', class: 'shop-qty', 'data-testid': 'shop-qty' });
  let pending = null;
  let lastRefusal = store.get().refusal?.n ?? 0;
  let last = '';

  const qty = () => Math.min(99, Math.max(1, Math.round(Number(qtyInput.value) || 1)));
  qtyInput.addEventListener('change', () => {
    last = '';
    render(store.get());
  });

  function send(type, line) {
    const shop = store.get().shop;
    if (!shop) return;
    const gold = myHero(store.get())?.gold ?? 0;
    pending = { kind: type === 'shop_buy' ? 'bought' : 'sold', gold };
    status.textContent = '';
    client.send(type, { npc_id: shop.npc_id, item_id: line.item_id ?? line.item, qty: qty() });
  }

  function feedback(state, gold) {
    const refusal = state.refusal;
    if (refusal && refusal.n !== lastRefusal) {
      lastRefusal = refusal.n;
      pending = null;
      const text = t(`refusal.${refusal.code}`);
      status.textContent = refusal.code.startsWith('shop_') && text !== `refusal.${refusal.code}` ? text : t('refusal.generic');
    } else if (pending && pending.gold !== gold) {
      status.textContent = t(`shop.${pending.kind}`);
      pending = null;
    }
  }

  function render(state) {
    if (!panel.sync(state)) return;
    const view = publicState(state);
    const hero = myHero(state);
    const gold = hero?.gold ?? 0;
    feedback(state, gold);
    const shop = state.shop;
    const open = Boolean(shop && view?.scene?.shop_npc_id === shop.npc_id);
    const pack = (state.sheet?.sheet?.inventory ?? []).filter(sellable);
    const key = JSON.stringify([open, shop, gold, view?.camp_supplies, pack, view?.scene?.shopkeepers, qty()]);
    if (key === last) return;
    last = key;
    clear(panel.body);
    if (!view) return;
    if (!open) {
      panel.body.append(...closedView(view, client, store));
      return;
    }
    const sendCtx = { gold, qty, send };
    panel.body.append(
      h('p', { class: 'shop-keeper' }, h('strong', {}, t('shop.keeper', { name: shop.npc_name }))),
      h('p', { class: 'shop-gold', 'data-testid': 'shop-gold' }, t('shop.gold', { n: gold }), ' ', h('span', { 'data-testid': 'shop-supplies' }, t('shop.supplies', { n: view.camp_supplies }))),
      h('div', { class: 'shop-qty-row' }, h('label', { for: 'shop-qty' }, t('shop.qty')), qtyInput),
      h('h3', {}, t('shop.buyHeading')),
      h('ul', { class: 'shop-list', 'data-testid': 'shop-stock' }, ...shop.stock.map((line) => stockRow(line, sendCtx))),
      h('h3', {}, t('shop.sellHeading')),
      pack.length ? h('ul', { class: 'shop-list', 'data-testid': 'shop-pack' }, ...pack.map((item) => packRow(item, sendCtx))) : h('p', { class: 'hint' }, t('shop.emptyPack')),
    );
  }
  panel.dialog.insertBefore(status, panel.body);
  render(store.get());
  const stop = store.subscribe(render);
  return () => {
    stop();
    panel.remove();
  };
}
