// The screen's sound gate (M16.2): browsers refuse autoplay until someone clicks the page, and only the screen
// plays sound (narrator, Scribe, music). A full-screen card asks for one click at load and again whenever a
// player is blocked (`store.audioBlocked`). The click primes audio inside the gesture, then unlocks everything.
import { t } from '../strings.js';
import { h } from '../ui/dom.js';

const SILENT_WAV = 'data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA=';

function prime() {
  try {
    const el = new Audio(SILENT_WAV);
    Promise.resolve(el.play()).then(() => el.pause()).catch(() => {});
  } catch {
    // No audio support: nothing to prime.
  }
}

export function mountSoundGate(root, { store, audio }) {
  const button = h('button', { type: 'button', class: 'btn sg-button', 'data-testid': 'sound-gate-button' }, t('gate.button'));
  const card = h('div', { class: 'sg', role: 'dialog', 'aria-modal': 'true', 'aria-labelledby': 'sg-title', 'data-testid': 'sound-gate', hidden: true },
    h('div', { class: 'sg-card' }, h('h2', { id: 'sg-title' }, t('gate.title')), h('p', {}, t('gate.body')), button));
  root.append(card);
  const open = () => {
    card.hidden = false;
    button.focus();
  };
  const unlock = (event) => {
    if (card.hidden) return;
    if (event.type === 'keydown' && event.key !== 'Enter' && event.key !== 'Escape' && event.key !== ' ') return;
    prime();
    audio.unlock();
    card.hidden = true;
    if (store.get().audioBlocked) store.update({ audioBlocked: false });
  };
  card.addEventListener('pointerdown', unlock);
  card.addEventListener('keydown', unlock);
  open(); // always at load: a navigation can carry user activation, yet a fresh tab still blocks autoplay
  const stop = store.subscribe((state) => {
    if (state.audioBlocked && card.hidden) open();
  });
  return () => {
    stop();
    card.remove();
  };
}
