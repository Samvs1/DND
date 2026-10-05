// Action input: free-text submit_action. Disabled while you already have an action waiting, while the
// table is paused, in a fight outside your turn (on your turn it sends a creative action) or before your hero exists. A refused
// action shows the table's gentle notice under the box; nothing raw is ever printed.
import { isMyTurn } from '../combat/model.js';
import { mySeat } from '../state.js';
import { t } from '../strings.js';
import { h } from '../ui/dom.js';
import { hasPendingAction, publicState } from './lookup.js';

const MAX_TEXT = 1000;
const NOTICE_MS = 8000;

function blockedReason(state) {
  const view = publicState(state);
  if (!view) return 'wait';
  if (!mySeat(state)?.creature_id) return 'noHero';
  if (view.paused) return 'paused';
  if (view.combat) return isMyTurn(state) ? null : 'fight';
  if (!view.combat && hasPendingAction(state)) return 'pending';
  return null;
}

export function mountAction(root, { store, client }) {
  const input = h('textarea', {
    id: 'action-text',
    rows: 2,
    maxlength: MAX_TEXT,
    placeholder: t('table.actionPlaceholder'),
    'aria-label': t('table.actionLabel'),
    'data-testid': 'action-input',
  });
  const send = h('button', { type: 'submit', class: 'btn btn-primary', 'data-testid': 'action-send' }, t('table.send'));
  const note = h('p', { class: 'action-note', role: 'status', 'data-testid': 'action-note' });
  const gentle = h('p', { class: 'action-gentle', role: 'status', 'data-testid': 'action-gentle' });
  const form = h('form', { class: 'action', novalidate: true }, input, send);
  root.append(form, note, gentle);
  let gentleTimer = null;
  let lastNotice = store.get().notices.at(-1) ?? null;

  function showGentle(text) {
    gentle.textContent = text;
    clearTimeout(gentleTimer);
    gentleTimer = setTimeout(() => (gentle.textContent = ''), NOTICE_MS);
  }

  function render(state) {
    const why = blockedReason(state);
    input.disabled = why !== null;
    send.disabled = why !== null;
    note.textContent = why ? t(`table.blocked_${why}`) : '';
    const latest = state.notices.at(-1) ?? null;
    if (latest && latest !== lastNotice && latest.kind === 'refused') showGentle(latest.text);
    lastNotice = latest;
  }

  form.addEventListener('submit', (event) => {
    event.preventDefault();
    const text = input.value.trim();
    if (!text || send.disabled) return;
    if (client.send('submit_action', { text })) {
      input.value = '';
      gentle.textContent = '';
    }
  });
  input.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      form.requestSubmit();
    }
  });
  render(store.get());
  const stop = store.subscribe(render);
  return () => {
    stop();
    clearTimeout(gentleTimer);
  };
}
