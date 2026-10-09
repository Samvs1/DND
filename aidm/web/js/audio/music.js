// Background music: one looping bed per game state, crossfaded when the state changes.
// Exploration (the ambient bed) while the story runs, combat while a fight is on; when a fight ends a
// victory or defeat stinger plays once, then the exploration bed fades back in. Keys come from assetUrl
// (`music.<state>`); a state with no file is silence (a missing stinger goes straight back to the bed).
// It follows the same mute/volume settings and the same screen-is-the-audio-device default as narration.
// Audio elements come from `makeAudio(url)` (tests install a fake as `window.__aidmMakeAudio`).
import { assetUrl, hasAsset } from '../assets.js';
import { audioMuted, currentSettings, onSettingsChange, reducedMotion } from '../settings/model.js';

export const FADE_MS = 1500;
const TICK_MS = 50;
const GAIN = 0.8; // music sits under the narration voice
const STINGERS = ['victory', 'defeat'];

/** Which track the public state calls for: defeat, combat, a pending stinger, exploration, or null (silence). */
export function wantedState(snap, stinger) {
  if (snap?.phase === 'defeated') return 'defeat'; // the defeat screen (M11.1): the defeat track
  if (!snap || snap.phase !== 'play') return null;
  if (snap.combat) return 'combat';
  return stinger ?? 'exploration';
}

/** The stinger for how a fight ended (combat_state.outcome, M15.1): victory or defeat; a fled or parleyed
 * fight (or an unknown outcome) has none. Never inferred from party HP: that snapshot may be stale. */
export function stingerFor(outcome) {
  return outcome === 'victory' || outcome === 'defeat' ? outcome : null;
}

export function createMusic({ store, mode, makeAudio = (url) => new Audio(url) }) {
  let channel = null; // { key, url, el, level } the track that is (fading) in
  const fading = new Set(); // channels fading out
  let stinger = null;
  let wasCombat = false;
  let timer = null;
  let blocked = false;

  const muted = () => audioMuted(currentSettings(), store.get(), mode, 'music');
  const target = () => (currentSettings().musicVolume / 100) * GAIN;

  function setVolume(ch, level) {
    ch.level = level;
    ch.el.volume = Math.max(0, Math.min(1, level * target()));
  }

  function halt(ch) {
    ch.el.onended = null;
    try {
      ch.el.pause();
    } catch {
      // A fake or broken element: nothing to stop.
    }
  }

  function tick() {
    const step = reducedMotion() ? 1 : TICK_MS / FADE_MS; // reduced motion: switch beds without a fade
    if (channel && channel.level < 1) setVolume(channel, Math.min(1, channel.level + step));
    for (const ch of [...fading]) {
      setVolume(ch, ch.level - step);
      if (ch.level <= 0) {
        halt(ch);
        fading.delete(ch);
      }
    }
    if ((!channel || channel.level >= 1) && fading.size === 0) {
      clearInterval(timer);
      timer = null;
    }
  }

  function startTicking() {
    if (timer === null) timer = setInterval(tick, TICK_MS);
  }

  function silence() {
    if (channel) halt(channel);
    for (const ch of fading) halt(ch);
    channel = null;
    fading.clear();
    clearInterval(timer);
    timer = null;
  }

  function onPlayError(ch, err) {
    if (channel !== ch) return;
    if (err?.name === 'NotAllowedError') {
      blocked = true;
      if (!store.get().audioBlocked) store.update({ audioBlocked: true });
    }
    channel = null;
  }

  function begin(key) {
    const url = assetUrl(`music.${key}`);
    let el;
    try {
      el = makeAudio(url);
    } catch {
      return;
    }
    const ch = { key, url, el, level: 0 };
    el.loop = !STINGERS.includes(key);
    el.preload = 'auto';
    setVolume(ch, 0);
    el.onended = () => {
      if (channel === ch && STINGERS.includes(key)) {
        stinger = null;
        channel = null;
        sync();
      }
    };
    channel = ch;
    let promise;
    try {
      promise = Promise.resolve(el.play());
    } catch (err) {
      promise = Promise.reject(err);
    }
    promise.catch((err) => onPlayError(ch, err));
    startTicking();
  }

  function sync() {
    const state = store.get();
    let key = muted() ? null : wantedState(state.snapshot?.state, stinger);
    if (key && !hasAsset(`music.${key}`)) {
      if (STINGERS.includes(key)) {
        stinger = null;
        key = hasAsset('music.exploration') ? 'exploration' : null;
      } else {
        key = null;
      }
    }
    if (muted()) {
      stinger = null;
      silence();
      return;
    }
    if ((channel?.key ?? null) === key) return;
    if (channel) {
      fading.add(channel);
      channel = null;
      startTicking();
    }
    if (key && !blocked) begin(key);
  }

  function onStore(state) {
    const snap = state.snapshot?.state;
    const inCombat = Boolean(snap?.combat);
    if (wasCombat && !inCombat && snap) stinger = stingerFor(state.lastOutcome);
    if (inCombat) stinger = null;
    wasCombat = inCombat;
    sync();
  }

  /** The player interacted: the browser now allows playback, so start whatever should be playing. */
  function unlock() {
    if (!blocked) return;
    blocked = false;
    if (store.get().audioBlocked) store.update({ audioBlocked: false });
    sync();
  }

  const stopSettings = onSettingsChange(() => {
    if (channel) setVolume(channel, channel.level);
    for (const ch of fading) setVolume(ch, ch.level);
    sync();
  });
  const stopStore = store.subscribe(onStore);
  document.addEventListener('pointerdown', unlock);
  document.addEventListener('keydown', unlock);
  onStore(store.get());

  return {
    state: () => ({
      playing: channel?.key ?? null,
      url: channel?.url ?? null,
      fadingOut: [...fading].map((c) => c.key),
      muted: muted(),
      blocked,
    }),
    stop() {
      stopSettings();
      stopStore();
      silence();
      document.removeEventListener('pointerdown', unlock);
      document.removeEventListener('keydown', unlock);
    },
  };
}
