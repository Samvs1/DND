// The '?' tooltip (M28.2): `tipButton(key)` returns a small button that opens a non-modal popup with the text of
// `GET /api/tips` (keys `<kind>:<id>`). One popup at a time. It closes on its X, a tap outside, Esc and a view change.
// No press-and-hold anywhere. The tips load once; if that fails there is no '?' (fail soft, nothing shown).
import { t } from '../strings.js';
import { currentSettings, onSettingsChange } from '../settings/model.js';
import { h } from './dom.js';

const GAP = 6;
const EDGE = 8;
let tipsPromise = null;
let known = {};
const buttons = new Set();
let open = null; // { button, pop, stop }
let viewKey = '';

export function loadTips() {
  if (!tipsPromise) {
    tipsPromise = fetch('/api/tips')
      .then((res) => (res.ok ? res.json() : { tips: {} }))
      .then((body) => (known = body?.tips ?? {}))
      .catch(() => (known = {}));
  }
  return tipsPromise;
}

export function tipsEnabled() {
  return currentSettings().tooltips !== false;
}

function refresh() {
  for (const b of [...buttons]) {
    if (!b.isConnected) {
      buttons.delete(b);
      continue;
    }
    b.dataset.tip = b.tipKeys.find((k) => known[k]) ?? b.tipKeys[0];
    b.hidden = !tipsEnabled() || !known[b.dataset.tip];
    if (b.hidden && open?.button === b) closeTip(false);
  }
}

function bottomLimit(button) {
  const vh = window.innerHeight;
  const strip = document.querySelector('.ct-strip');
  if (!strip || strip.contains(button)) return vh - EDGE;
  const top = strip.getBoundingClientRect().top;
  return (top > 0 ? Math.min(vh, top) : vh) - EDGE; // keep the hero strip usable while a tip is open
}

function place(pop, button) {
  pop.style.maxHeight = '';
  pop.style.overflowY = '';
  const r = button.getBoundingClientRect();
  const w = pop.offsetWidth;
  const vw = document.documentElement.clientWidth;
  const below = bottomLimit(button) - (r.bottom + GAP);
  const above = r.top - GAP - EDGE;
  const hh = pop.offsetHeight;
  const up = hh > below && above > below;
  const room = up ? above : below;
  if (hh > room) {
    pop.style.maxHeight = `${Math.max(room, 60)}px`;
    pop.style.overflowY = 'auto';
  }
  const height = Math.min(hh, Math.max(room, 60));
  let left = r.left;
  if (left + w > vw - EDGE) left = r.right - w; // flip to the left at the right edge
  const top = up ? r.top - height - GAP : r.bottom + GAP;
  pop.style.left = `${Math.max(EDGE, Math.min(left, vw - w - EDGE))}px`;
  pop.style.top = `${Math.max(EDGE, top)}px`;
}

export function closeTip(returnFocus = true) {
  if (!open) return;
  const { button, pop, stop } = open;
  open = null;
  stop();
  pop.remove();
  button.setAttribute('aria-expanded', 'false');
  if (returnFocus && button.isConnected) button.focus();
}

function openTip(button) {
  closeTip(false);
  let tip = known[button.dataset.tip];
  if (!tip) return;
  if (button.tipMerge) {
    const all = button.tipKeys.map((k) => known[k]).filter(Boolean); // one '?' for several facts: their titles and lines in order
    tip = { title: all.map((x) => x.title).join(', '), lines: all.flatMap((x) => x.lines) };
  }
  const close = h('button', { type: 'button', class: 'tip-close', 'aria-label': t('tip.close'), 'data-testid': 'tip-close' }, '×');
  const pop = h('div', { class: 'tip-pop', role: 'dialog', tabindex: '-1', 'aria-label': tip.title, 'data-testid': 'tip-pop' },
    close, h('strong', { class: 'tip-title' }, tip.title), ...[...tip.lines, button.tipExtra].filter(Boolean).map((l) => h('p', { class: 'tip-line' }, l)));
  (button.closest('dialog') ?? document.body).append(pop);
  place(pop, button);
  button.setAttribute('aria-expanded', 'true');
  const onDown = (e) => {
    if (!pop.contains(e.target) && !button.contains(e.target)) closeTip(false);
  };
  const onKey = (e) => {
    if (e.key !== 'Escape') return;
    e.preventDefault();
    e.stopPropagation();
    closeTip();
  };
  const onSize = () => place(pop, button);
  close.addEventListener('click', () => closeTip());
  document.addEventListener('pointerdown', onDown, true);
  document.addEventListener('keydown', onKey, true);
  window.addEventListener('resize', onSize);
  const stop = () => {
    document.removeEventListener('pointerdown', onDown, true);
    document.removeEventListener('keydown', onKey, true);
    window.removeEventListener('resize', onSize);
  };
  open = { button, pop, stop };
  pop.focus();
}

/** A '?' button for a tip key (or a list of keys: the first known one is used). It stays hidden while tips are off,
 * still loading or unknown, so it is safe to place. */
export function tipButton(key, label = '', extra = '', merge = false) {
  const keys = [key].flat();
  const button = h('button', { type: 'button', class: 'tip-btn', hidden: true, 'data-tip': keys[0], 'data-testid': 'tip-btn', 'aria-haspopup': 'dialog', 'aria-expanded': 'false' }, '?');
  button.tipKeys = keys;
  button.tipExtra = extra;
  button.tipMerge = merge;
  button.setAttribute('aria-label', t('tip.what', { title: label }));
  button.addEventListener('click', (e) => {
    e.stopPropagation();
    if (open?.button === button) closeTip();
    else openTip(button);
  });
  buttons.add(button);
  loadTips().then(() => {
    button.setAttribute('aria-label', t('tip.what', { title: label || known[button.dataset.tip]?.title || '' }));
    refresh();
  });
  return button;
}

/** Wire the tips to the app: settings changes show or hide every '?', and a view change closes the popup. */
export function bindTips(store) {
  onSettingsChange(refresh);
  const view = (s) => [s.ctab, s.jtab, s.panel].join('|');
  viewKey = view(store.get());
  store.subscribe((s) => {
    const next = view(s);
    if (next !== viewKey) {
      viewKey = next;
      closeTip(false);
    }
  });
  loadTips().then(refresh);
}
