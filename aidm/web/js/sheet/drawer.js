// The character sheet drawer: a modal side panel (native <dialog>: focus trap, Escape, focus returns to the
// opener) with Overview, Inventory and Spellbook tabs. It opens when `store.sheetOpen` is set and reads the
// latest `sheet` message (kept fresh by sheet/sync.js). With `embed: (state) => boolean` it is an inline section
// instead (the phone's Hero tab), shown while `embed(state)` holds.
import { assetUrl } from '../assets.js';
import { portraitKeys } from '../table/party.js';
import { myHero, publicState } from '../table/lookup.js';
import { t } from '../strings.js';
import { clear, h } from '../ui/dom.js';
import { titleCase } from '../ui/format.js';
import { renderInventory } from './inventory.js';
import { renderOverview } from './overview.js';
import { renderSpellbook } from './spellbook.js';

const TABS = ['overview', 'inventory', 'spells'];

function openDialog(dialog) {
  if (dialog.open) return;
  if (typeof dialog.showModal === 'function') dialog.showModal();
  else dialog.setAttribute('open', '');
}

function spellNameOf(sheet) {
  const names = new Map();
  const c = sheet.spellcasting;
  for (const sp of [...(c?.cantrips ?? []), ...(c?.levels ?? []).flatMap((g) => g.spells)]) names.set(sp.index, sp.name);
  return (index) => names.get(index) ?? titleCase(index);
}

function header(sheet, hero, store) {
  const xp = sheet.xp_next ? t('sheet.xp', { xp: sheet.xp, next: sheet.xp_next }) : t('sheet.xpMax', { xp: sheet.xp });
  const ratio = sheet.xp_next ? Math.min(1, sheet.xp / sheet.xp_next) : 1;
  const fill = h('span', { class: 'hp-fill good' });
  fill.style.width = `${Math.round(ratio * 100)}%`;
  const ready = Boolean(store.get().sheet?.level_up);
  return [
    h('img', { class: 'sh-portrait', src: assetUrl(portraitKeys(hero ?? { class_index: sheet.class_index })), alt: '', width: 56, height: 56 }),
    h(
      'div',
      { class: 'sh-title' },
      h('h2', { id: 'sheet-h' }, sheet.name),
      h('p', { class: 'muted' }, t('table.classLine', { level: sheet.level, race: titleCase(sheet.race), cls: titleCase(sheet.class_index) }), sheet.subclass ? ` (${titleCase(sheet.subclass)})` : ''),
      h('div', { class: 'hp sh-xp', 'aria-hidden': 'true' }, fill),
      h('p', { class: 'hint' }, xp),
      ready ? h('button', { type: 'button', class: 'btn btn-small btn-primary', 'data-testid': 'sheet-levelup', onclick: () => store.update({ levelUpOpen: true }) }, t('sheet.levelButton')) : null,
    ),
  ];
}

export function mountSheet(root, { store, client }, embed = null) {
  const head = h('header', { class: 'sh-head' });
  const tabs = h('div', { class: 'sh-tabs', role: 'tablist', 'aria-label': t('sheet.tabs') });
  const panel = h('div', { class: 'sh-panel', id: 'sheet-panel', role: 'tabpanel', tabindex: '0', 'data-testid': 'sheet-panel' });
  const status = h('p', { class: 'form-error', role: 'status', 'data-testid': 'sheet-status' });
  const close = h('button', { type: 'button', class: 'btn btn-small sh-close', 'data-testid': 'sheet-close', 'aria-label': t('sheet.close') }, t('sheet.close'));
  const dialog = embed
    ? h('section', { class: 'sheet-embed', 'aria-labelledby': 'sheet-h', 'data-testid': 'sheet' }, head, tabs, status, panel)
    : h('dialog', { class: 'sheet-drawer', 'aria-labelledby': 'sheet-h', 'data-testid': 'sheet' }, close, head, tabs, status, panel);
  root.append(dialog);
  let wasOpen = false;
  let tab = 'overview';
  let last = '';
  let lastRefusal = store.get().refusal?.n ?? 0;

  close.addEventListener('click', () => dialog.close());
  if (!embed) dialog.addEventListener('close', () => store.update({ sheetOpen: false }));
  const buttons = TABS.map((id) => {
    const b = h('button', { type: 'button', role: 'tab', id: `tab-${id}`, class: 'sh-tab', 'data-testid': `tab-${id}` }, t(`sheet.tab_${id}`));
    b.addEventListener('click', () => select(id));
    b.addEventListener('keydown', (event) => {
      const step = { ArrowRight: 1, ArrowLeft: -1 }[event.key];
      if (!step) return;
      event.preventDefault();
      const next = TABS[(TABS.indexOf(id) + step + TABS.length) % TABS.length];
      select(next);
      tabs.querySelector(`#tab-${next}`).focus();
    });
    return b;
  });
  tabs.append(...buttons);

  function select(id) {
    tab = id;
    last = '';
    render(store.get());
  }

  function body(state, sheet) {
    const camp = publicState(state)?.camp_supplies ?? 0;
    const locked = Boolean(publicState(state)?.combat);
    const party = (publicState(state)?.party ?? []).filter((p) => !p.dead).map((p) => ({ id: p.id, name: p.name }));
    if (tab === 'inventory') return renderInventory(sheet, { client, camp, locked, party });
    if (tab === 'spells') return renderSpellbook(sheet);
    return renderOverview(sheet, spellNameOf(sheet));
  }

  function render(state) {
    const wanted = embed ? embed(state) : state.sheetOpen;
    if (embed) dialog.hidden = !wanted;
    if (!wanted) {
      if (!embed && dialog.open) dialog.close();
      wasOpen = false;
      return;
    }
    if (!wasOpen) client.send('request_sheet');
    wasOpen = true;
    if (!embed) openDialog(dialog);
    const refusal = state.refusal;
    if (refusal && refusal.n !== lastRefusal) {
      lastRefusal = refusal.n;
      const text = t(`refusal.${refusal.code}`);
      status.textContent = text === `refusal.${refusal.code}` ? t('refusal.generic') : text;
    }
    const sheet = state.sheet?.sheet;
    const key = JSON.stringify([tab, sheet, publicState(state)?.camp_supplies, Boolean(publicState(state)?.combat), state.sheet?.level_up?.level, (publicState(state)?.party ?? []).map((p) => [p.id, p.dead])]);
    if (key === last) return;
    last = key;
    clear(head);
    clear(panel);
    buttons.forEach((b, i) => {
      b.setAttribute('aria-selected', TABS[i] === tab ? 'true' : 'false');
      b.tabIndex = TABS[i] === tab ? 0 : -1;
      b.setAttribute('aria-controls', 'sheet-panel');
    });
    panel.setAttribute('aria-labelledby', `tab-${tab}`);
    if (!sheet) {
      panel.append(h('p', { class: 'hint' }, t('sheet.loading')));
      return;
    }
    head.append(...header(sheet, myHero(state), store));
    panel.append(...body(state, sheet).filter(Boolean));
  }
  render(store.get());
  return store.subscribe(render);
}
