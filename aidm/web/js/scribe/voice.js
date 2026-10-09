// One voice for the Scribe on a device. A `scribe_line` shows his subtitle (`store.scribeLine`) and plays the
// clip on the narrator channel (narration volume and mute); `store.scribeSpeaking` is true only while the clip
// plays, and narration.js holds its queue until it clears. The line ends when the clip ends, or after a reading
// time when there is no clip, it fails or the sound is off, or on `scribe_skip`.
import { audioMuted, currentSettings } from '../settings/model.js';

const MS_PER_WORD = 420;
const MIN_MS = 4000;
const GRACE_MS = 15000;

export function readingMs(text) {
  const words = String(text ?? '').split(/\s+/).filter(Boolean).length;
  return Math.max(MIN_MS, words * MS_PER_WORD);
}

/** accept(msg) decides whether this device shows the line (the screen takes all; a phone its own and shared). */
export function createScribeVoice({ store, mode, makeAudio, accept }) {
  let current = null;
  let el = null;
  let timer = null;
  let waiting = null;

  function release() {
    waiting = null;
    clearTimeout(timer);
    timer = null;
    if (el) {
      el.onended = null;
      el.onerror = null;
      try {
        el.pause();
      } catch {
        // A fake or broken element: nothing to stop.
      }
      el = null;
    }
  }

  function finish() {
    release();
    current = null;
    store.update({ scribeLine: null, scribeSpeaking: false });
  }

  function readOnly(msg) {
    release();
    store.update({ scribeSpeaking: false });
    timer = setTimeout(finish, readingMs(msg.text));
  }

  // The browser refused to autoplay: keep his subtitle, raise the sound gate and replay the clip once unlocked.
  function blockedRead(msg) {
    readOnly(msg);
    waiting = msg;
    store.update({ audioBlocked: true });
  }

  function onStoreChange(state) {
    if (!waiting || state.audioBlocked) return;
    const msg = waiting;
    waiting = null;
    if (current === msg) {
      release();
      play(msg);
    }
  }

  function play(msg) {
    try {
      el = makeAudio(msg.audio_url);
      el.volume = currentSettings().narrationVolume / 100;
      el.onended = finish;
      el.onerror = () => current === msg && readOnly(msg);
      Promise.resolve(el.play()).catch((err) => current === msg && (err?.name === 'NotAllowedError' ? blockedRead(msg) : readOnly(msg)));
    } catch {
      return readOnly(msg);
    }
    store.update({ scribeSpeaking: true });
    timer = setTimeout(finish, readingMs(msg.text) * 2 + GRACE_MS); // safety net if `ended` never comes
  }

  function onLine(msg) {
    if (!accept(msg)) return;
    release();
    current = msg;
    store.update({ scribeLine: msg });
    if (msg.audio_url && !audioMuted(currentSettings(), store.get(), mode)) play(msg);
    else readOnly(msg);
  }

  function onSkip(msg) {
    if (current && (!msg.line_id || msg.line_id === current.line_id)) finish();
  }

  const stops = [store.subscribe(onStoreChange), store.on('scribe_line', onLine), store.on('scribe_skip', onSkip)];
  return () => {
    stops.forEach((stop) => stop());
    release();
    store.update({ scribeLine: null, scribeSpeaking: false });
  };
}
