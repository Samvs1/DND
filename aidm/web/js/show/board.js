// Rolls in a fight, played on the board (M26.7, docs/next/GOAL_DICE.md): an attack's die arcs from the
// attacker's token and lands under the target's, the verdict floats over the target (told from the party's
// side), damage dice pop in a row under it, and the damage taken floats up while the token's HP bar drains.
// A save drops a die under each saver; a death save under the fallen hero. Everything lives in a fixed
// layer above the board (the board itself only re-renders when the pacer releases the next state).
import { creatureName } from '../table/lookup.js';
import { h } from '../ui/dom.js';
import { showClock } from './clock.js';
import { natural, SPELL_LINE_MS } from './timing.js';
import { flicker, makeDie } from './throw.js';
import { boardVerdict, onPartySide } from './words.js';

const ARC_MS = 430;
const LAND_MS = 160;
const FLOAT_LIFE_MS = 1500;
const UNDER_PX = 64; // a die rests this far under the token's centre
const FLOAT_GAP = 8; // px between two floats

const overlap = (a, b) => a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;

function tokenOf(id) {
  return id ? document.querySelector(`.board [data-testid=token][data-creature="${CSS.escape(id)}"]`) : null;
}

function centre(el) {
  const r = el.getBoundingClientRect();
  return { x: r.left + r.width / 2, y: r.top + r.height / 2, w: r.width };
}

/** The sides of the dice in an expression like "1d6+1d6+3" or "2d4": one entry per die. */
export function diceSides(expression, count) {
  const sides = [];
  for (const [, n, d] of String(expression).matchAll(/(\d*)d(\d+)/g)) for (let i = 0; i < Number(n || 1); i++) sides.push(Number(d));
  while (sides.length < count) sides.push(sides[sides.length - 1] || 6);
  return sides.slice(0, count);
}

function dieKind(sides) {
  return [4, 6, 8, 10, 12].includes(sides) ? `d${sides}` : 'hero';
}

export function createBoardShows({ layer, store, sfx, onStep }) {
  const floats = new Map(); // creature id -> { el, x, y, timer }
  const name = (id) => creatureName(store.get(), id);

  function pin(el, x, y) {
    el.style.left = `${x}px`;
    el.style.top = `${y}px`;
    layer.append(el);
    return el;
  }

  /** Where a float's text sits (it hangs from x, y: centred, bottom-aligned). */
  function box(f) {
    const w = f.el.offsetWidth;
    const tall = [...f.el.children].reduce((sum, c) => sum + c.offsetHeight, 0);
    return { left: f.x - w / 2, right: f.x + w / 2, top: f.y - tall, bottom: f.y };
  }

  /** A new float goes over its token, else beside the float in the way, else above it: the first spot
   *  that covers no other float and no zone name. */
  function place(f, c) {
    const names = [...document.querySelectorAll('.board .hex-name')].map((n) => n.getBoundingClientRect());
    const others = [...floats.values()].map(box);
    const w = f.el.offsetWidth;
    const y = c.y - c.w * 0.5;
    const spots = [{ x: c.x, y }];
    for (const o of others) {
      const right = { x: o.right + FLOAT_GAP + w / 2, y };
      const left = { x: o.left - FLOAT_GAP - w / 2, y };
      spots.push(...(c.x >= (o.left + o.right) / 2 ? [right, left] : [left, right]), { x: c.x, y: o.top - FLOAT_GAP });
    }
    const clear = (spot) => {
      const b = box({ ...f, ...spot });
      return !others.some((o) => overlap(b, o)) && !names.some((n) => overlap(b, n));
    };
    Object.assign(f, spots.find(clear) ?? spots[1] ?? spots[0]);
    f.el.style.left = `${f.x}px`;
    f.el.style.top = `${f.y}px`;
  }

  /** One float per creature: the verdict, then the number under it. */
  function float(id, { word, tone, num, hurt }) {
    const token = tokenOf(id);
    if (!token) return;
    let f = floats.get(id);
    const fresh = !f;
    if (fresh) {
      f = { el: h('div', { class: 'sb-float', 'data-testid': 'show-float' }), x: 0, y: 0, timer: 0 };
      layer.append(f.el);
    }
    if (word) {
      f.el.dataset.tone = tone;
      let tag = f.el.querySelector('.sb-word');
      if (!tag) f.el.prepend((tag = h('span', { class: 'sb-word' })));
      tag.textContent = word;
    }
    if (num !== undefined) {
      let n = f.el.querySelector('.sb-num');
      if (!n) f.el.append((n = h('span', { class: 'sb-num' })));
      n.classList.toggle('hurt', Boolean(hurt));
      n.textContent = num;
      n.animate?.([{ transform: 'scale(1.6)', opacity: 0 }, { transform: 'scale(.95)', opacity: 1, offset: 0.6 }, { transform: 'scale(1)' }], { duration: 240, easing: 'ease-out' });
    }
    if (fresh) {
      place(f, centre(token));
      floats.set(id, f);
      f.el.animate?.([{ opacity: 0, transform: 'translate(-50%,-80%) scale(.55)' }, { opacity: 1, transform: 'translate(-50%,-100%) scale(1.08)', offset: 0.6 }, { opacity: 1, transform: 'translate(-50%,-100%)' }], { duration: 200, fill: 'forwards', easing: 'ease-out' });
    }
    clearTimeout(f.timer);
    f.timer = setTimeout(() => {
      floats.delete(id);
      const out = f.el.animate?.([{ opacity: 1 }, { opacity: 0, transform: 'translate(-50%,-125%)' }], { duration: 320, fill: 'forwards' });
      if (out) out.finished.then(() => f.el.remove(), () => f.el.remove());
      else f.el.remove();
    }, FLOAT_LIFE_MS);
  }

  function restingDie(kind, size, value, x, y) {
    const host = pin(h('div', { class: 'sb-host' }), x, y);
    const die = makeDie(kind, size, value);
    host.append(die);
    return { host, die };
  }

  function fade(piece, clock, after = 500) {
    clock.animate(piece.host, [{ opacity: 1 }, { opacity: 0 }], 350, { delay: after, always: true }).then(() => piece.host.remove());
  }

  /** The d20 arcs from `fromId` to under `toId` and lands with a clack. */
  async function arc(fromId, toId, kind, value, clock) {
    const from = tokenOf(fromId);
    const to = tokenOf(toId);
    if (!to) return null;
    const b = centre(to);
    const a = from ? centre(from) : { x: b.x, y: b.y - 220 };
    const end = { x: b.x, y: b.y + UNDER_PX };
    const piece = restingDie(kind, 56, '?', 0, 0);
    const ctrl = { x: (a.x + end.x) / 2, y: Math.min(a.y, end.y) - 110 - Math.random() * 60 };
    const spin = (500 + Math.random() * 320) * (Math.random() < 0.5 ? -1 : 1);
    const frames = Array.from({ length: 31 }, (_, i) => {
      const u = i / 30;
      const x = (1 - u) ** 2 * a.x + 2 * (1 - u) * u * ctrl.x + u * u * end.x;
      const y = (1 - u) ** 2 * a.y + 2 * (1 - u) * u * ctrl.y + u * u * end.y;
      return { offset: u, transform: `translate(${x}px, ${y}px) rotate(${spin * (1 - (1 - u) ** 2)}deg) scale(${0.7 + 0.5 * Math.sin(Math.PI * u)})` };
    });
    piece.host.style.left = '0px';
    piece.host.style.top = '0px';
    const settle = flicker(piece.die, [[ARC_MS / 1000, 1]], value, 20, clock.scale, clock.later);
    await clock.animate(piece.host, frames, ARC_MS, { always: !clock.still });
    settle();
    piece.host.getAnimations?.().forEach((x) => x.cancel());
    piece.host.style.left = `${end.x}px`;
    piece.host.style.top = `${end.y}px`;
    if (clock.scale > 0.6) sfx?.play('dice_clack', { gain: 0.9 });
    clock.animate(piece.die, [{ transform: 'scale(1.15,.85)' }, { transform: 'translateY(-9px) rotate(-6deg)', offset: 0.25 }, { transform: 'rotate(3deg)', offset: 0.45 }, { transform: 'translateY(-3px)', offset: 0.65 }, { transform: 'none' }], 200, { easing: 'ease-out' });
    return piece;
  }

  async function attack(dice, clock) {
    const crit = natural(dice) === 20 && dice.success;
    const ours = onPartySide(store.get(), dice.roller_id);
    const piece = await arc(dice.roller_id, dice.target_id, crit ? 'crit' : ours ? 'hero' : 'foe', natural(dice), clock);
    await clock.wait(LAND_MS);
    const verdict = boardVerdict(dice, store.get(), name);
    float(dice.target_id, verdict);
    sfx?.play(dice.success ? (crit ? 'crit' : 'hit') : 'miss', { gain: 0.8 });
    onStep?.({ type: 'attack', dice, verdict, name, ours });
    await clock.wait(dice.success ? 420 : 700);
    if (piece) {
      if (dice.success) clock.animate(piece.host, [{ opacity: 1 }, { opacity: 0.4 }], 200, { always: true });
      fade(piece, clock, dice.success ? 900 : 200);
    }
  }

  async function rolledOn(dice, clock, { tone }) {
    const token = tokenOf(dice.target_id || dice.roller_id);
    if (!token) return;
    const c = centre(token);
    const sides = diceSides(dice.expression, dice.rolls.length);
    const pieces = [];
    for (let i = 0; i < dice.rolls.length; i++) {
      const x = c.x - ((dice.rolls.length - 1) * 36) / 2 + i * 36 + 30;
      const piece = restingDie(dieKind(sides[i]), 36, dice.rolls[i], x, c.y + UNDER_PX);
      clock.animate(piece.die, [{ transform: 'scale(.2) rotate(-180deg)', opacity: 0 }, { transform: 'scale(1.15) rotate(10deg)', opacity: 1, offset: 0.7 }, { transform: 'none' }], 220, { easing: 'ease-out' });
      if (i === 0 || i === dice.rolls.length - 1) sfx?.play('dice_clack', { gain: 0.45 });
      pieces.push(piece);
      await clock.wait(130);
    }
    onStep?.({ type: tone, dice, name });
    pieces.forEach((p) => fade(p, clock, 700));
    await clock.wait(300);
  }

  async function dropOn(dice, clock) {
    const token = tokenOf(dice.roller_id);
    if (!token) return;
    const c = centre(token);
    const ours = onPartySide(store.get(), dice.roller_id);
    const piece = restingDie(ours ? 'hero' : 'foe', 46, '?', c.x, c.y + UNDER_PX);
    const settle = flicker(piece.die, [[0.3, 1]], natural(dice), 20, clock.scale, clock.later);
    await clock.animate(piece.die, [{ transform: 'translateY(-120px) rotate(-320deg) scale(.6)', opacity: 0 }, { transform: 'scale(1.1,.9)', opacity: 1, offset: 0.85 }, { transform: 'none' }], 300, { easing: 'ease-in', always: !clock.still });
    settle();
    if (clock.scale > 0.6) sfx?.play('dice_clack', { gain: 0.7 });
    await clock.wait(260);
    const verdict = boardVerdict(dice, store.get(), name);
    float(dice.roller_id, verdict);
    sfx?.play(verdict.tone === 'good' ? 'hit' : 'miss', { gain: 0.6 });
    onStep?.({ type: dice.kind, dice, verdict, name, ours });
    fade(piece, clock, 700);
    await clock.wait(300);
  }

  /** Damage taken on a creature: the number floats up and its HP bars drain (until the state arrives). */
  function onBody(msg) {
    const id = msg.subject_id;
    if (msg.kind === 'spell_cast') {
      onStep?.({ type: 'spell', line: msg.line });
    } else if (msg.kind === 'damage_taken' && msg.amount) {
      float(id, { num: `-${msg.amount}`, hurt: true });
      drain(id, -msg.amount);
      onStep?.({ type: 'taken', id, amount: msg.amount, name });
    } else if (msg.kind === 'creature_died') {
      tokenOf(id)?.classList.add('show-fallen');
      onStep?.({ type: 'fell', id, ours: onPartySide(store.get(), id), name });
    }
  }

  function drain(id, delta) {
    const view = store.get().snapshot?.state;
    const c = view?.party?.find((p) => p.id === id) || view?.combat?.tokens?.find((tk) => tk.creature_id === id);
    if (!c?.max_hp) return;
    const hp = Math.max(0, Math.min(c.max_hp, (c.hp ?? 0) + delta));
    const pct = `${Math.round((hp / c.max_hp) * 100)}%`;
    for (const fill of document.querySelectorAll(`[data-creature="${CSS.escape(id)}"] .hp-fill`)) fill.style.width = pct; // token and party card
  }

  return {
    /** The board show of one message; resolves when its beat is over. */
    play(msg, { scale, signal }) {
      const clock = showClock(scale, signal);
      if (msg.type === 'event') {
        onBody(msg);
        return clock.wait(msg.kind === 'spell_cast' ? SPELL_LINE_MS : 500);
      }
      const dice = msg.dice;
      if (dice.kind === 'attack') return attack(dice, clock);
      if (dice.kind === 'damage') return rolledOn(dice, clock, { tone: 'damage' });
      if (dice.kind === 'heal') return rolledOn(dice, clock, { tone: 'heal' });
      if (dice.kind === 'save' || dice.kind === 'check' || dice.kind === 'death_save') return dropOn(dice, clock);
      return clock.wait(400);
    },
  };
}
