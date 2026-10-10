// The action box: THE way to act out of combat (first come first served through the server queue). Enter sends,
// Shift+Enter adds a line. Disabled with a stated reason when the party fell, the hero is down, it is not your
// turn in a fight, the game is paused or an action of yours is already waiting. Tells the table while you type.
// In a fight it shows only on your own turn (M18.2); the idea chips fill it through `store.emit('compose', {text})`.
import { isMyTurn } from '../combat/model.js';
import { mySeat } from '../state.js';
import { hasPendingAction, publicState } from '../table/lookup.js';
import { t } from '../strings.js';
import { h } from '../ui/dom.js';
import { isDown, queuePosition } from './status.js';
import { createMic, micSupported } from './mic.js';
import { createTyping } from './typing.js';

const MAX_TEXT = 1000;
const NOTICE_MS = 8000;

export function blockedReason(state) {
  const view = publicState(state);
  if (!view) return 'wait';
  if (view.phase === 'defeated') return 'defeated';
  if (!mySeat(state)?.creature_id) return 'noHero';
  if (view.paused) return 'paused';
  if (isDown(state)) return 'down';
  if (view.combat) return isMyTurn(state) ? null : 'fight';
  return hasPendingAction(state) ? 'pending' : null;
}

export function mountAction(root, { store, client }) {
  const input = h('textarea', { id: 'action-text', rows: 2, maxlength: MAX_TEXT, placeholder: t('table.actionPlaceholder'), 'aria-label': t('table.actionLabel'), 'data-testid': 'action-input' });
  const send = h('button', { type: 'submit', class: 'btn btn-primary', 'data-testid': 'action-send' }, t('table.send'));
  const mic = h('span', { class: 'ct-mic', hidden: true, 'data-testid': 'mic-slot', 'aria-label': t('ct.mic') });
  const note = h('p', { class: 'action-note', role: 'status', 'data-testid': 'action-note' });
  const hint = h('p', { class: 'hint', 'data-testid': 'dictation-hint' }, t('ct.dictationHint'));
  const place = h('p', { class: 'action-note', role: 'status', 'data-testid': 'queue-place' });
  const gentle = h('p', { class: 'action-gentle', role: 'status', 'data-testid': 'action-gentle' });
  const form = h('form', { class: 'action', novalidate: true }, input, h('div', { class: 'ct-send' }, send, mic));
  root.append(form, note, place, gentle, hint);
  const typing = createTyping(client);
  if (micSupported()) {
    mic.hidden = false;
    hint.hidden = true;
    createMic(mic, input, (text) => (gentle.textContent = text), () => typing.change(input.value));
  }
  let gentleTimer = null;
  let lastNotice = store.get().notices.at(-1) ?? null;

  function showGentle(text) {
    gentle.textContent = text;
    clearTimeout(gentleTimer);
    gentleTimer = setTimeout(() => (gentle.textContent = ''), NOTICE_MS);
  }

  function render(state) {
    const why = blockedReason(state);
    root.hidden = why === 'fight'; // someone else's turn: the hotbar's suggestion box is the way to help
    input.disabled = why !== null;
    send.disabled = why !== null;
    if (why) typing.off();
    note.textContent = why ? t(`ct.blocked_${why}`) : '';
    const spot = queuePosition(state);
    place.textContent = spot ? t('ct.queuePlace', { n: spot }) : '';
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
      typing.off();
    }
  });
  input.addEventListener('input', () => typing.change(input.value));
  input.addEventListener('blur', () => typing.off());
  input.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      form.requestSubmit();
    }
  });
  function compose({ text }) {
    if (input.disabled || !text) return;
    input.value = text;
    input.focus();
    input.setSelectionRange(text.length, text.length);
    typing.change(text);
  }
  render(store.get());
  const stop = store.subscribe(render);
  const stopCompose = store.on('compose', compose);
  return () => {
    stop();
    stopCompose();
    typing.off();
    clearTimeout(gentleTimer);
  };
}
