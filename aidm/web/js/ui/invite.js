// The "invite friends" panel: LAN address and QR code (from /api/lan and /api/lan-qr.svg).
import { t } from '../strings.js';
import { clear, h } from './dom.js';

export async function fetchLan(store) {
  try {
    const response = await fetch('/api/lan');
    if (response.ok) store.update({ lan: await response.json() });
  } catch {
    // No LAN info: the panel falls back to the local-only hint.
  }
}

let panels = 0; // each panel on a page needs its own heading id (the screen shows two)

export function invitePanel(lan) {
  const id = `invite-h-${(panels += 1)}`;
  const body =
    lan.lan && lan.url
      ? [
          h('p', { class: 'hint' }, t('lobby.inviteHint')),
          h('img', { class: 'qr', src: '/api/lan-qr.svg', alt: t('lobby.qrAlt'), width: 168, height: 168 }),
          h('p', { class: 'lan-url', 'data-testid': 'lan-url' }, lan.url),
        ]
      : [h('p', { class: 'hint' }, t('lobby.localOnly'))];
  return h(
    'section',
    { class: 'panel invite', 'aria-labelledby': id },
    h('h2', { id }, t('lobby.invite')),
    ...body,
  );
}

export function mountInvite(slot, store) {
  function render(state) {
    clear(slot);
    slot.append(invitePanel(state.lan));
  }
  render(store.get());
  let last = store.get().lan;
  return store.subscribe((state) => {
    if (state.lan !== last) {
      last = state.lan;
      render(state);
    }
  });
}
