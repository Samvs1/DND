// The Scribe tab: fallen heroes with the price to rewrite them into the story (25 gp per level, outside combat,
// paid by a standing hero). State comes from `state.scribe`; his refusals are text only, taken from
// /api/scribe/lines and never from the server's words. Pressing Rewrite sends `scribe_revive`; the server decides.
import { confirmButton } from '../host/confirm.js';
import { loadScribeLines, groupText, refusalText } from '../scribe/lines.js';
import { portraitSrc } from '../scribe/portrait.js';
import { myHero, publicState } from '../table/lookup.js';
import { t } from '../strings.js';
import { clear, h } from '../ui/dom.js';

const TOAST_MS = 6000;
const REASON_TEXT = { scribe_defeated: 'scribe.defeated', scribe_paused: 'scribe.paused' };

function heroDown(hero) {
  return Boolean(hero) && (hero.dead || hero.hp <= 0);
}

function fallenCard(f, { gold, locked, onRevive }) {
  const short = gold < f.price_gp;
  return h(
    'li',
    { class: 'sc-fallen', 'data-testid': 'scribe-fallen', 'data-id': f.creature_id },
    h('div', { class: 'sc-fallen-head' }, h('strong', { 'data-testid': 'scribe-fallen-name' }, f.name), h('span', { class: 'hint' }, t('scribe.fallenLevel', { n: f.level })), h('span', { class: 'sc-price', 'data-testid': 'scribe-price' }, t('scribe.price', { n: f.price_gp }))),
    locked ? h('button', { type: 'button', class: 'btn', disabled: true, 'data-testid': 'scribe-revive-off' }, t('scribe.revive')) : confirmButton({ label: t('scribe.revive'), ask: t('scribe.confirm', { price: f.price_gp, name: f.name }), yes: t('scribe.confirmYes'), testid: 'scribe-revive', onYes: () => onRevive(f.creature_id) }),
    short && !locked ? h('p', { class: 'sc-warn', role: 'status', 'data-testid': 'scribe-gold-warn' }, t('scribe.youHave', { n: gold })) : null,
  );
}

export function mountScribeTab(root, { store, client }, toastSlot) {
  const portrait = h('img', { class: 'sc-portrait', src: portraitSrc('seated'), alt: t('scribe.portraitAlt'), width: 96, height: 96, 'data-testid': 'scribe-portrait' });
  const reason = h('p', { class: 'sc-reason', 'data-testid': 'scribe-reason' });
  const hint = h('p', { class: 'hint', 'data-testid': 'scribe-hint' });
  const list = h('ul', { class: 'sc-list', 'aria-label': t('scribe.list'), 'data-testid': 'scribe-list' });
  const status = h('p', { class: 'sc-status', role: 'status', 'data-testid': 'scribe-status' });
  const toast = h('div', { class: 'ct-toast', hidden: true, role: 'status', 'data-testid': 'scribe-toast' });
  toastSlot.append(toast);
  root.append(
    h('header', { class: 'sc-head' }, portrait, h('div', {}, h('h2', { class: 'ct-h' }, t('scribe.name')), h('p', { class: 'sc-flavour', 'data-testid': 'scribe-flavour' }, t('scribe.flavour')))),
    reason,
    hint,
    list,
    status,
  );
  let lines = [];
  let lastKey = '';
  let lastRefusal = store.get().refusal?.n ?? 0;
  let timer = null;

  function say(text) {
    status.textContent = text;
    toast.textContent = text;
    toast.hidden = false;
    clearTimeout(timer);
    timer = setTimeout(() => (toast.hidden = true), TOAST_MS);
  }

  function refusal(state) {
    const r = state.refusal;
    if (!r || r.n === lastRefusal) return;
    lastRefusal = r.n;
    if (!String(r.code).startsWith('scribe_')) return;
    if (r.code === 'scribe_payer_down') say(t('scribe.heroDown'));
    else say(refusalText(lines, r.code));
  }

  function render(state) {
    refusal(state);
    const view = publicState(state)?.scribe;
    const hero = myHero(state);
    const gold = hero?.gold ?? 0;
    const down = heroDown(hero);
    const key = JSON.stringify([view, gold, down, lines.length]);
    if (!view || key === lastKey) return;
    lastKey = key;
    portrait.src = portraitSrc('seated');
    clear(list);
    hint.textContent = '';
    const fallen = view.fallen ?? [];
    const locked = !view.available || down;
    if (view.reason === 'scribe_in_combat') {
      reason.textContent = groupText(lines, 'refuse_combat');
      hint.textContent = t('scribe.onlyOutside');
    } else if (view.reason === 'scribe_none_fallen' || (view.available && fallen.length === 0)) {
      reason.textContent = groupText(lines, 'none_fallen');
    } else if (REASON_TEXT[view.reason]) {
      reason.textContent = t(REASON_TEXT[view.reason]);
    } else reason.textContent = '';
    if (down && view.available) hint.textContent = t('scribe.heroDown');
    list.append(...fallen.map((f) => fallenCard(f, { gold, locked, onRevive: (id) => client.send('scribe_revive', { target_id: id }) })));
  }

  loadScribeLines().then((rows) => {
    lines = rows;
    lastKey = '';
    render(store.get());
  });
  render(store.get());
  const stop = store.subscribe(render);
  return () => {
    stop();
    clearTimeout(timer);
  };
}
