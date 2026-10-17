// The natural 20 on the roll stage (M26.6, docs/next/GOAL_DICE.md; owner sign-off 2026-10-17: "they look
// perfect now"). One 3 s sound, and the show is choreographed to it beat by beat: the beats come from the
// sound itself (dice_timing.json `natural_20`, measured by scripts/gen_dice_sfx.py, so a new sound re-times
// the show) and the show runs on the sound's clock AS HEARD (js/audio/sfx.js `cue`), so a speaker's delay
// never puts the picture ahead of the sound. Without sound it runs on the show clock with the same beats.
//
// gather (the swell: the glow turns gold, motes stream in) -> flare (the ignite hit: gold face, a white
// flash, a ring of light, a pop) -> rise (the riser: the bonuses add up across it, the die lifts, its glow
// beats faster, rays charge) -> pull-in (the die crouches, the rays contract; the banner starts so that it
// LANDS on the slam) -> slam (the die bursts out, the stage shakes, the rays blow out, gold dust) -> the
// recording's own ring (the spark jumps out of the die) -> the fade (the stage fades with the sound).
import { assetUrl } from '../assets.js';
import { t } from '../strings.js';
import { h } from '../ui/dom.js';
import { showClock } from './clock.js';
import { setSprite } from './throw.js';

/** The beats of the shipped sound (s), used until dice_timing.json is in. */
export const N20_BEATS = { flare: 0.21, slam: 1.315, chime: 1.79, fade: 2.7, end: 3.0 };
const LEAD = 0.03; // a frame plus the screen's own delay: a visual fires this early to be SEEN on its beat
const BANNER_LAND = 0.26; // the banner's slam frame: 62 % of its 420 ms entrance (linear overall)

const glow = (r, a) => `drop-shadow(0 0 ${r}px rgba(236,199,100,${a}))`;

/** The stage's white flash (css .show-stage.flash), restarted for the second hit. */
function flash(root) {
  root.classList.remove('flash');
  void root.offsetWidth;
  root.classList.add('flash');
}

/** The clock of the show: the sound's as heard when it plays, else the show clock (scaled). */
function beatClock(cue, scale, signal) {
  const start = performance.now();
  const now = cue ? cue.now : () => (performance.now() - start) / 1000 / scale;
  const at = (sec) =>
    new Promise((resolve) => {
      let done = false;
      const finish = () => {
        if (done) return;
        done = true;
        signal?.removeEventListener('abort', finish);
        resolve();
      };
      const tick = () => (done ? null : signal?.aborted || now() >= sec - LEAD ? finish() : requestAnimationFrame(tick));
      signal?.addEventListener('abort', finish, { once: true }); // a hidden tab stops frames; skip still ends it
      tick();
    });
  return { at };
}

function addBits(die, cls, n) {
  return Array.from({ length: n }, () => {
    const bit = h('div', { class: cls });
    die.append(bit);
    return bit;
  });
}

async function gatherAndFlare({ die, sc, go, at, beats, root }) {
  go(die, [{ filter: glow(12, 0.35), transform: sc(1) }, { filter: glow(30, 0.95), transform: sc(1.06) }], beats.flare * 1000, 'ease-in');
  addBits(die, 'sh-mote', 7).forEach((mote, i) => {
    const a = (i / 7) * Math.PI * 2 + Math.random() * 0.5;
    const r = 120 + Math.random() * 50;
    go(mote, [{ opacity: 0, transform: `translate(${Math.cos(a) * r}px,${Math.sin(a) * r}px)` }, { opacity: 1, offset: 0.35 }, { opacity: 0.9, transform: 'translate(0,0) scale(.4)' }], beats.flare * 1000, 'ease-in');
  });
  await at(beats.flare);
  hold(die, sc(1.04), glow(26, 0.9));
  die.querySelectorAll('.sh-mote').forEach((m) => m.remove());
  setSprite(die, 'crit');
  die.classList.add('gold');
  flash(root);
  const ring = h('div', { class: 'sh-ring' });
  die.prepend(ring);
  go(ring, [{ opacity: 1, transform: 'scale(.45)' }, { opacity: 0, transform: 'scale(2.1)' }], 480, 'cubic-bezier(.1,.7,.3,1)');
  go(die, [{ transform: sc(1.13) }, { transform: sc(1.04) }], 260, 'ease-out');
}

/** Pin the die where it is (inline) and drop its running animations. */
function hold(die, transform, filter) {
  die.style.transform = transform;
  die.style.filter = filter;
  die.getAnimations?.().forEach((a) => a.cancel());
}

async function rise({ m, els, die, rays, sc, go, at, beats }) {
  const from = beats.flare + 0.25;
  const to = beats.slam - 0.3;
  await at(from);
  const ms = (to - from) * 1000;
  go(die, [{ transform: sc(1.04) }, { transform: sc(1.08, -12) }], ms, 'ease-in-out');
  const pulse = [[22, 0.8, 0], [30, 0.95, 0.3], [22, 0.8, 0.5], [33, 1, 0.65], [22, 0.82, 0.76], [36, 1, 0.85], [24, 0.85, 0.92], [40, 1, 1]];
  go(die, pulse.map(([r, a, offset]) => ({ filter: glow(r, a), offset })), ms);
  go(rays, [{ opacity: 0, transform: 'scale(.6) rotate(0deg)' }, { opacity: 0.5, transform: 'scale(.92) rotate(70deg)' }], ms, 'ease-in');
  els.sum.classList.add('on');
  let run = m.face;
  const n = m.parts.length;
  for (let i = 0; i < n; i++) {
    await at(from + ((i + 0.5) * (to - from)) / n);
    if (i) els.bonus[i - 1].classList.replace('lit', 'used');
    els.bonus[i].classList.add('lit');
    run += m.parts[i].value;
    els.ops.textContent = m.parts.slice(0, i + 1).map((p) => ` ${p.value >= 0 ? '+' : '-'} ${Math.abs(p.value)}`).join('');
    els.total.textContent = String(i === n - 1 ? m.total : run);
    go(els.total, [{ transform: 'scale(1.3)' }, { transform: 'scale(1)' }], 160, 'ease-out');
  }
  await at(to);
  if (n) els.bonus[n - 1].classList.replace('lit', 'used');
  els.total.textContent = String(m.total);
}

async function slam({ els, die, rays, sc, go, at, beats, root, box }) {
  hold(die, sc(1.08, -12), glow(40, 1));
  go(die, [{ transform: sc(1.08, -12) }, { transform: sc(0.93) }], 280, 'cubic-bezier(.6,0,.9,.5)');
  go(rays, [{ opacity: 0.5, transform: 'scale(.92) rotate(70deg)' }, { opacity: 0.8, transform: 'scale(.5) rotate(100deg)' }], 290, 'ease-in');
  await at(beats.slam - BANNER_LAND);
  const v = h('div', { class: 'ss-verdict v-nat20', 'data-testid': 'stage-verdict' }, t('show.nat20'));
  els.verdictSlot.append(v);
  go(v, [{ opacity: 0, transform: 'scale(2.2)', easing: 'cubic-bezier(.55,0,.9,.55)' }, { opacity: 1, transform: 'scale(.94)', offset: 0.62, easing: 'ease-out' }, { transform: 'scale(1.04)', offset: 0.82, easing: 'ease-in-out' }, { transform: 'scale(1)' }], 420, 'linear', true);
  await at(beats.slam);
  hold(die, sc(1), glow(24, 0.9));
  go(die, [{ transform: sc(1.24) }, { transform: sc(0.98), offset: 0.55 }, { transform: sc(1) }], 380, 'ease-out');
  flash(root);
  go(box, [{ translate: '0 0' }, { translate: '-8px 4px' }, { translate: '7px -3px' }, { translate: '-4px 2px' }, { translate: '2px -1px' }, { translate: '0 0' }], 320);
  go(rays, [{ opacity: 0.9, transform: 'scale(.5) rotate(100deg)' }, { opacity: 0, transform: 'scale(1.8) rotate(125deg)' }], 420, 'cubic-bezier(.1,.7,.3,1)');
  els.total.classList.add('gold');
  const span = beats.fade - 0.12 - beats.slam;
  addBits(die, 'sh-fleck', 16).forEach((fleck) => {
    const a = -Math.PI / 2 + (Math.random() - 0.5) * Math.PI * 1.6;
    const r = 90 + Math.random() * 130;
    const d = 0.65 + Math.random() * 0.35;
    go(fleck, [{ opacity: 0, transform: 'translate(0,0)' }, { opacity: 1, offset: 0.15 }, { opacity: 0, transform: `translate(${Math.cos(a) * r}px,${Math.sin(a) * r * 0.6 + 70}px)` }], d * 1000, 'cubic-bezier(.2,.6,.4,1)', (0.06 + Math.random() * Math.max(0, span - d)) * 1000);
  });
}

async function spark({ die, go, at, beats }) {
  await at(beats.chime - 0.04);
  const burst = h('img', { class: 'sh-burst', src: assetUrl('ui_icon.roll-burst'), alt: '' });
  die.prepend(burst);
  go(burst, [
    { opacity: 0, transform: 'scale(.35) rotate(0deg)', easing: 'cubic-bezier(.15,.85,.35,1)' },
    { opacity: 1, transform: 'scale(1.18) rotate(22deg)', offset: 0.17, easing: 'ease-in-out' },
    { opacity: 1, transform: 'scale(1) rotate(40deg)', offset: 0.36, easing: 'linear' },
    { opacity: 0.95, transform: 'scale(1) rotate(70deg)', offset: 0.62, easing: 'ease-in' },
    { opacity: 0, transform: 'scale(.92) rotate(95deg)' },
  ], (beats.fade - 0.05 - beats.chime + 0.04) * 1000);
}

/** Play the natural 20 from the landing to the start of the fade. `kept` is the kept die, `ks` its scale. */
export async function playNatural20({ m, els, kept, ks, root, box, sfx, scale, signal }) {
  const beats = { ...N20_BEATS, ...(sfx?.timing?.()?.natural_20 || {}) };
  const cue = scale >= 0.45 ? sfx?.cue?.('roll_natural_20') : null; // the tests' fast shows stay silent
  const clock = showClock(cue ? 1 : scale, signal); // with sound, every animation runs in real time
  const go = (el, frames, ms, easing = 'linear', delay = 0, always = false) => clock.animate(el, frames, ms, { easing, delay, always });
  const { at } = beatClock(cue, scale, signal);
  const die = kept.die;
  const sc = (k, y = 0) => `translate(0,${y}px) scale(${ks * k})`;
  const rays = h('img', { class: 'sh-rays', src: assetUrl('ui_icon.roll-burst'), alt: '' });
  die.prepend(rays);
  const ctx = { m, els, die, rays, sc, go, at, beats, root, box };
  try {
    await gatherAndFlare(ctx);
    await rise(ctx);
    await slam(ctx);
    await spark(ctx);
    await at(beats.fade);
  } finally {
    if (signal?.aborted) cue?.stop(150);
  }
  return Boolean(cue);
}
