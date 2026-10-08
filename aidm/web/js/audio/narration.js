// Narration audio: plays each sentence's audio in order and tells the feed when to reveal its text.
// `enqueue(url, reveal)` returns true when this client will play the clip (the feed then waits and
// `reveal()` runs when playback STARTS); false means no audio here (muted, blocked, no url) and the feed
// types the sentence at the reading speed. Every failure path reveals the text, so a sentence is never lost.
// Audio elements come from `makeAudio(url)` (tests install a fake as `window.__aidmMakeAudio`).
import { audioMuted, currentSettings, onSettingsChange } from '../settings/model.js';

export function createNarrationAudio({ store, mode, makeAudio = (url) => new Audio(url) }) {
  const queue = [];
  const played = [];
  let current = null;
  let blocked = false;

  const muted = () => audioMuted(currentSettings(), store.get(), mode);
  const volume = () => currentSettings().narrationVolume / 100;

  function reveal(item) {
    if (item.revealed) return;
    item.revealed = true;
    item.reveal();
  }

  function setBlocked(value) {
    blocked = value;
    if (store.get().audioBlocked !== value) store.update({ audioBlocked: value });
  }

  function stopCurrent() {
    if (!current) return;
    const item = current;
    current = null;
    item.el.onended = null;
    item.el.onerror = null;
    try {
      item.el.pause();
    } catch {
      // A fake or broken element: nothing to stop.
    }
    reveal(item);
  }

  /** Drop everything queued (revealing the text) and stop the clip in progress. */
  function flush() {
    stopCurrent();
    for (const item of queue.splice(0)) reveal(item);
  }

  function end(item) {
    if (current !== item) return;
    current = null;
    played.push(item.url);
    reveal(item);
    pump();
  }

  function refused(item, err) {
    if (current !== item) return;
    if (err?.name === 'NotAllowedError') {
      setBlocked(true);
      flush();
    } else {
      end(item);
    }
  }

  function start(item) {
    current = item;
    item.el.volume = volume();
    item.el.onended = () => end(item);
    item.el.onerror = () => end(item);
    let promise;
    try {
      promise = Promise.resolve(item.el.play());
    } catch (err) {
      promise = Promise.reject(err);
    }
    promise.then(
      () => current === item && reveal(item),
      (err) => refused(item, err),
    );
  }

  function pump() {
    if (current || blocked || queue.length === 0) return;
    if (muted()) {
      flush();
      return;
    }
    start(queue.shift());
  }

  function enqueue(url, revealFn) {
    if (!url || blocked || muted()) return false;
    let el;
    try {
      el = makeAudio(url);
      el.preload = 'auto';
    } catch {
      return false;
    }
    queue.push({ url, reveal: revealFn, el, revealed: false });
    pump();
    return true;
  }

  /** The player interacted (or pressed the hint button): browsers now allow playback. */
  function unlock() {
    if (blocked) setBlocked(false);
  }

  const stopSettings = onSettingsChange(() => {
    if (muted()) flush();
    else if (current) current.el.volume = volume();
  });
  const stopStore = store.subscribe(() => {
    if ((queue.length > 0 || current) && muted()) flush();
  });
  document.addEventListener('pointerdown', unlock);
  document.addEventListener('keydown', unlock);
  store.on('reset', flush);

  return {
    enqueue,
    unlock,
    flush,
    state: () => ({ queued: queue.map((i) => i.url), playing: current?.url ?? null, played: [...played], blocked, muted: muted() }),
    stop() {
      flush();
      stopSettings();
      stopStore();
      document.removeEventListener('pointerdown', unlock);
      document.removeEventListener('keydown', unlock);
    },
  };
}
