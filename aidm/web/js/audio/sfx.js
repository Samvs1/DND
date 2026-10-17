// Sound effects (M26.8, docs/next/GOAL_DICE.md): the dice throws, landings and verdict stings. Only the
// screen plays them (owner rule M16.2), through WebAudio so a throw starts on the frame its animation does.
// `play('dice_throw')` picks one of the variants (`dice_throw_1`..`_6`), never the one it played last; a
// full name plays that sound. It has its own mute and level (screen gear and the phones' remote).
// `timing()` is audio/sfx/dice_timing.json: the impact times of each throw, so the stage bounces the die
// exactly when each clack is heard. Tests read `window.__aidmSfxLog` (every play is logged there when set).
import { SFX_TIMING_URL, assetUrl } from '../assets.js';
import { audioMuted, currentSettings } from '../settings/model.js';

export const VARIANTS = { dice_throw: 6, dice_throw_two: 3, dice_clack: 4, roll_failure: 2, hit: 2, miss: 2 };
/** Single sounds the owner signed off on exactly (never alternated), plus the rare ones. */
const SINGLES = ['roll_success', 'roll_natural_20', 'roll_natural_1', 'crit'];
const wait = (ms) => new Promise((done) => setTimeout(done, ms));

/** The file names of a sound: its variants, or itself. `hit` and `miss` count their plain name as the first. */
export function variantsOf(name) {
  const count = VARIANTS[name];
  if (!count) return [name];
  const first = name === 'hit' || name === 'miss' ? name : `${name}_1`;
  return [first, ...Array.from({ length: count - 1 }, (_, i) => `${name}_${i + 2}`)];
}

export function createSfx({ store, mode, fetchFn = fetch }) {
  let ctx = null;
  const buffers = new Map(); // file name -> AudioBuffer | Promise
  const last = new Map(); // sound -> the variant played last
  let timing = null;

  const silent = () => mode !== 'screen' || audioMuted(currentSettings(), store.get(), mode, 'effects');
  const volume = () => (currentSettings().effectsVolume ?? 80) / 100;

  function load(file) {
    if (!ctx || buffers.has(file)) return;
    const url = assetUrl(`sfx.${file}`);
    if (!url) return;
    const attempt = (left) => fetchFn(url)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`); // an error page is not a sound
        return r.arrayBuffer();
      })
      .then((data) => ctx.decodeAudioData(data))
      .catch((err) => (left > 1 ? wait(400).then(() => attempt(left - 1)) : Promise.reject(err)));
    const pending = attempt(3)
      .then((buffer) => buffers.set(file, buffer))
      .catch(() => buffers.delete(file)); // still missing after three tries: silence, tried again on its next play
    buffers.set(file, pending);
  }

  /** Browsers suspend audio (a tab switch, a TV's power saving): wake it on the next play or touch. */
  function wake() {
    if (ctx && ctx.state === 'suspended') Promise.resolve(ctx.resume?.()).catch(() => {});
  }

  function pick(name) {
    const all = variantsOf(name);
    const pool = all.length > 1 ? all.filter((f) => f !== last.get(name)) : all;
    const file = pool[Math.floor(Math.random() * pool.length)];
    last.set(name, file);
    return file;
  }

  return {
    /** Call inside a user gesture (the screen's sound gate): creates or resumes the audio context. */
    unlock() {
      if (mode !== 'screen') return;
      try {
        if (!ctx) {
          ctx = new (window.AudioContext || window.webkitAudioContext)();
          document.addEventListener('pointerdown', wake, { passive: true });
          document.addEventListener('keydown', wake);
        }
        ctx.resume?.();
        for (const name of Object.keys(VARIANTS)) variantsOf(name).forEach(load);
        SINGLES.forEach(load);
      } catch {
        ctx = null; // no WebAudio: the shows run silent
      }
    },
    /** Play a sound (or one of its variants) now; returns the file name chosen, or '' when silent. */
    play(name, { gain = 1, file = null } = {}) {
      const chosen = file || pick(name);
      if (window.__aidmSfxLog) window.__aidmSfxLog.push(chosen);
      if (silent() || !ctx) return chosen;
      wake();
      const buffer = buffers.get(chosen);
      if (!(buffer instanceof AudioBuffer)) { // still loading (skip it, never delay) or failed (load it again)
        load(chosen);
        return chosen;
      }
      const src = ctx.createBufferSource();
      const level = ctx.createGain();
      src.buffer = buffer;
      level.gain.value = gain * volume();
      src.connect(level).connect(ctx.destination);
      src.start();
      return chosen;
    },
    /** Choose a variant without playing it (the show needs its timing first). */
    pick,
    /** The impact timing table, or null until loaded (the shows then use their built-in bounces). */
    timing: () => timing,
    async loadTiming() {
      try {
        timing = await (await fetchFn(SFX_TIMING_URL)).json();
      } catch {
        timing = null;
      }
      return timing;
    },
  };
}
