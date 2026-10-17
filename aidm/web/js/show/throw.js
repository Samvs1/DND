// A thrown die (M26.6): its look (pixel sprite + the face number drawn by CSS), its path and its flicker.
// The path bounces on the impact times of the throw's sound (audio/sfx/dice_timing.json), so the die hits
// the table exactly when each clack is heard; without the timing it uses a built-in bounce. Every throw
// gets its own entry side, spin and tilt, and the face flickers random numbers that never show the result
// before the last impact (docs/next/GOAL_DICE.md "Repeatable, never boring").
import { assetUrl } from '../assets.js';
import { h } from '../ui/dom.js';

export const FALLBACK_TRACK = [[0.23, 0.95], [0.47, 0.72], [0.62, 0.48], [0.72, 0.34], [0.78, 0.25], [0.82, 0.19], [0.85, 0.45]];
const SPRITES = { hero: 'ui_icon.die-d20', foe: 'ui_icon.die-d20-foe', crit: 'ui_icon.die-d20-crit', fumble: 'ui_icon.die-d20-fumble' };

/** The sprite key of a die: 'hero' | 'foe' | 'crit' | 'fumble' for a d20, else `ui_icon.die-d<sides>`. */
export function spriteKey(kind) {
  return SPRITES[kind] || `ui_icon.die-${kind}`;
}

/** A die element `size` px wide showing `value`; `.face` is the sprite, `.num` the number. */
export function makeDie(kind, size, value) {
  const face = h('img', { class: 'sh-face', src: assetUrl(spriteKey(kind)), alt: '' });
  const num = h('b', { class: 'sh-num' }, String(value));
  num.style.fontSize = `${Math.round(size * 0.42)}px`;
  const die = h('div', { class: 'sh-die', 'data-testid': 'show-die' }, face, num);
  die.style.width = `${size}px`;
  die.style.height = `${size}px`;
  die.face = face;
  die.num = num;
  return die;
}

export function setSprite(die, kind) {
  die.face.src = assetUrl(spriteKey(kind));
}

const rnd = (a, b) => a + Math.random() * (b - a);

/** Keyframes for a stage throw from `fromX` to `toX` (px), bouncing on `track` ([[t s, strength]...]). */
export function throwFrames(track, { fromX, toX, height = rnd(260, 340), spin = rnd(520, 980), tilt = rnd(-7, 7) }) {
  const land = track[track.length - 1][0];
  const first = track[0][0];
  const gravity = (8 * 105) / (track[1][0] - first) ** 2; // the first bounce rises about 105 px
  const steps = Math.max(30, Math.round(land * 90));
  const die = [];
  const shadow = [];
  for (let i = 0; i <= steps; i++) {
    const u = i / steps;
    const t = land * u;
    let rise = 0;
    let scale = 1;
    if (t < first) {
      const v = t / first;
      rise = height * (1 - v * v);
      scale = 1.5 - 0.5 * v; // it comes in close to the camera
    } else {
      let k = 0;
      while (k < track.length - 1 && t > track[k + 1][0]) k++;
      if (k < track.length - 1) {
        const [a, s] = track[k];
        const gap = track[k + 1][0] - a;
        const w = t - a;
        rise = ((gravity * w * (gap - w)) / 2) * Math.min(1, s * 1.15);
      }
    }
    let sx = 1;
    let sy = 1;
    for (const [at, s] of track) {
      const near = Math.abs(t - at);
      if (near < 0.03) {
        const k = (1 - near / 0.03) * s;
        sy = 1 - 0.12 * k; // squash on each impact
        sx = 1 + 0.08 * k;
      }
    }
    const x = fromX + (toX - fromX) * (1 - (1 - u) ** 2.4);
    const rot = tilt - spin * (1 - u) ** 2.8;
    die.push({ offset: u, transform: `translate(${x}px, ${-rise}px) rotate(${rot}deg) scale(${scale * sx}, ${scale * sy})` });
    shadow.push({ offset: u, transform: `translateX(${x}px) scale(${Math.max(0.35, 1 - rise / 320)})`, opacity: Math.max(0.12, 0.7 - rise / 420) });
  }
  return { die, shadow, land, tilt };
}

/** Flicker random faces while the die tumbles; the real face lands with the last impact. Returns stop(). */
export function flicker(die, track, value, faces, scale, later) {
  const land = track[track.length - 1][0];
  const stops = [];
  for (let t = 0; t < land * 0.62; t += 0.065) stops.push(t);
  for (const [t] of track.slice(0, -1)) stops.push(t);
  stops.sort((a, b) => a - b);
  let shown = value;
  const timers = stops.map((t) =>
    later(() => {
      let next;
      do next = 1 + Math.floor(Math.random() * faces);
      while (next === shown || next === value);
      shown = next;
      die.num.textContent = String(next);
    }, t * 1000 * scale),
  );
  die.classList.add('spin');
  const settle = () => {
    timers.forEach((id) => clearTimeout(id));
    die.num.textContent = String(value);
    die.classList.remove('spin');
  };
  timers.push(later(settle, land * 1000 * scale));
  return settle;
}
