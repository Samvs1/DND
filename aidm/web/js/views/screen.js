// Spectator screen (/screen): read-only. For now it shows the invite panel while waiting.
import { t } from '../strings.js';
import { h } from '../ui/dom.js';
import { fetchLan, mountInvite } from '../ui/invite.js';

export function mountScreen(root, ctx) {
  const slot = h('div', {});
  root.append(
    h('header', { class: 'masthead' }, h('h1', {}, t('app.title')), h('p', { class: 'tagline' }, t('screen.waiting'))),
    h('div', { class: 'lobby' }, slot),
  );
  const stop = mountInvite(slot, ctx.store);
  fetchLan(ctx.store);
  return stop;
}
