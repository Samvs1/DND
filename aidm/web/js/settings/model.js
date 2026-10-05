// Player settings (SPEC 12): kept in localStorage through `saved` (the ONLY thing besides the token and name
// that is persisted). `applySettings` writes the text size and the motion override onto <html>; the feed and
// the dice tray read `revealMs()` / `reducedMotion()`; the narration audio queue reads `audioMuted()` / volume
// and listens with `onSettingsChange`.

export const SPEEDS = ['instant', 'fast', 'normal', 'slow'];
export const SIZES = { small: 0.9, normal: 1, large: 1.15, xlarge: 1.3 };
export const DEFAULTS = { mute: false, muteSet: false, volume: 80, speed: 'normal', size: 'normal', reduceMotion: false };

const REVEAL = { instant: 0, fast: 500, normal: 1200, slow: 2400 };
let current = { ...DEFAULTS };
const listeners = new Set();

function clean(raw) {
  const out = { ...DEFAULTS };
  if (typeof raw?.mute === 'boolean') out.mute = raw.mute;
  if (typeof raw?.muteSet === 'boolean') out.muteSet = raw.muteSet;
  const volume = Number(raw?.volume);
  if (Number.isFinite(volume)) out.volume = Math.min(100, Math.max(0, Math.round(volume)));
  if (SPEEDS.includes(raw?.speed)) out.speed = raw.speed;
  if (Object.hasOwn(SIZES, raw?.size)) out.size = raw.size;
  if (typeof raw?.reduceMotion === 'boolean') out.reduceMotion = raw.reduceMotion;
  return out;
}

export function currentSettings() {
  return current;
}

/** Write the settings that change the page itself (text size, motion override). */
export function applySettings(next, root = document.documentElement) {
  current = clean(next);
  root.style.setProperty('--text-scale', String(SIZES[current.size]));
  if (current.reduceMotion) root.dataset.motion = 'reduced';
  else delete root.dataset.motion;
  for (const fn of [...listeners]) fn(current);
}

export function onSettingsChange(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

/**
 * Is this client's narration audio off? An explicit choice (`muteSet`) wins. Otherwise a player is muted
 * while a /screen client is connected (it is the default audio device); the /screen view itself never is.
 * Decision logged in docs/DECISIONS.md (M8.2).
 */
export function audioMuted(settings, state, mode) {
  if (settings.muteSet) return settings.mute;
  return mode === 'play' && (state?.snapshot?.state?.screens ?? 0) > 0;
}

export function loadSettings(saved) {
  applySettings(saved.settings());
}

export function updateSettings(patch, saved) {
  applySettings({ ...current, ...patch });
  saved.setSettings(current);
}

/** True when the player asked for less motion (the setting) or the device does. */
export function reducedMotion() {
  if (current.reduceMotion) return true;
  try {
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  } catch {
    return false;
  }
}

/** How long a typed sentence takes to appear, in ms; 0 shows it at once. */
export function revealMs() {
  return REVEAL[current.speed];
}
