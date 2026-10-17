// The roll stage (M26.6, docs/next/GOAL_DICE.md): a check or save out of combat gets the whole TV. The
// scene dims; the skill ribbon, who rolls, the DC plaque (left) and the named bonuses (right) come in; one
// big d20 (two with advantage or disadvantage) is thrown and bounces on the impacts of its sound; the
// bonuses add into the total; the verdict slams in with its sting; then the stage fades and the story
// goes on (the pacer releases what waited). A natural 1 cracks; a natural 20 plays its own show,
// choreographed to its sound (js/show/natural20.js). ~3.8 s, a natural 20 ~4.7 s.
import { assetUrl } from '../assets.js';
import { portraitKeys } from '../table/party.js';
import { creatureName, publicState } from '../table/lookup.js';
import { t } from '../strings.js';
import { h } from '../ui/dom.js';
import { showClock } from './clock.js';
import { playNatural20 } from './natural20.js';
import { natural } from './timing.js';
import { FALLBACK_TRACK, flicker, makeDie, setSprite, throwFrames } from './throw.js';
import { verdictOf } from './words.js';

const STAGE_W = 1280;
const READ_MS = 500; // owner tuning 2026-10-16: the stage shows half a second before the die flies
const STAGE_H = 720;

/** Title, who, DC, bonuses and verdict of a stage roll, from its DiceView. */
export function stageModel(dice, state) {
  const label = dice.label || t('show.roll');
  const title = dice.kind === 'check' && !/check$/i.test(label) ? t('show.check', { label }) : label;
  const parts = dice.parts?.length ? dice.parts : dice.modifier ? [{ name: 'BONUS', value: dice.modifier }] : [];
  const hero = publicState(state)?.party.find((c) => c.id === dice.roller_id);
  const two = dice.rolls.length === 2;
  const face = natural(dice);
  const kept = two ? dice.rolls.indexOf(face) : 0;
  return {
    title: title.toUpperCase(),
    who: creatureName(state, dice.roller_id),
    portrait: hero ? assetUrl(portraitKeys(hero)) : '',
    dc: dice.target,
    tier: dice.difficulty || '',
    parts,
    rolls: dice.rolls,
    kept,
    face,
    adv: two ? dice.adv : null,
    advWhy: (dice.adv_why || []).join(', '),
    total: dice.total,
    verdict: verdictOf(dice),
  };
}

function sign(n) {
  return `${n >= 0 ? '+' : '-'}${Math.abs(n)}`;
}

function build(m) {
  const bonus = m.parts.map((p) => h('div', { class: 'ss-bon' }, sign(p.value), h('span', {}, p.name)));
  const els = {
    zone: h('div', { class: 'ss-zone' }),
    bonus,
    total: h('b', { class: 'ss-total', 'data-testid': 'stage-total' }, String(m.face)),
    ops: h('span', { class: 'ss-ops' }),
    sum: null,
    verdictSlot: h('div', { class: 'ss-vslot' }),
  };
  els.sum = h('div', { class: 'ss-sum' }, h('span', {}, String(m.face)), els.ops, ' = ', els.total, h('span', { class: 'ss-vs' }, t('show.vsDc', { n: m.dc })));
  const adv = m.adv
    ? h('div', { class: `ss-adv ${m.adv === 'advantage' ? 'up' : 'down'}` },
        h('img', { src: assetUrl(m.adv === 'advantage' ? 'ui_icon.roll-adv' : 'ui_icon.roll-dis'), alt: '' }),
        h('b', {}, t(`show.${m.adv}`)), m.advWhy ? h('span', {}, m.advWhy) : null)
    : null;
  const box = h(
    'div',
    { class: 'ss-box' },
    h('div', { class: 'ss-title' }, m.title),
    h('div', { class: 'ss-who' }, m.portrait ? h('span', { class: 'ss-portrait' }, h('img', { src: m.portrait, alt: '' })) : null, h('b', {}, m.who)),
    adv,
    h('div', { class: 'ss-row' },
      h('div', { class: 'ss-plaque' }, h('div', { class: 'ss-pl' }, t('show.difficulty')), h('div', { class: 'ss-big' }, String(m.dc ?? '')), h('div', { class: 'ss-tier' }, m.tier)),
      els.zone,
      h('div', { class: 'ss-plaque' }, h('div', { class: 'ss-pl' }, t('show.bonuses')), ...bonus)),
    els.sum,
    els.verdictSlot,
  );
  const root = h('div', { class: 'show-stage', 'data-testid': 'roll-stage', role: 'status', 'aria-label': t('show.aria', { title: m.title, who: m.who }) }, h('div', { class: 'ss-dim' }), box);
  return { root, box, els };
}

function fit(box) {
  const scale = Math.min(window.innerWidth / STAGE_W, window.innerHeight / STAGE_H);
  box.style.transform = `translate(-50%, -50%) scale(${scale})`;
}

function placeDice(m, els, sfx, clock) {
  const two = m.rolls.length === 2;
  const timing = sfx?.timing?.();
  const name = sfx ? sfx.pick(two ? 'dice_throw_two' : 'dice_throw') : '';
  const tracks = two ? timing?.throw_two?.[name] : timing?.throw?.[name] ? [timing.throw[name]] : null;
  const side = Math.random() < 0.5 ? -1 : 1;
  const dice = m.rolls.map((value, i) => {
    const host = h('div', { class: 'ss-host' });
    const shadow = h('div', { class: 'ss-shadow' });
    const die = makeDie('hero', two ? 170 : 210, value);
    host.append(shadow, die);
    els.zone.append(host);
    const track = tracks?.[i] || FALLBACK_TRACK;
    const toX = two ? (i === 0 ? -95 : 95) : 0;
    const fromX = side * (420 + Math.random() * 140) + (two ? (i ? 60 : -60) : 0);
    return { value, die, shadow, track, toX, plan: throwFrames(track, { fromX, toX }) };
  });
  return { dice, name, played: !clock.still && clock.scale > 0.9 };
}

async function throwDice(thrown, sfx, clock) {
  if (thrown.played) sfx?.play('dice_throw', { file: thrown.name });
  const settles = thrown.dice.map((d) => flicker(d.die, d.track, d.value, 20, clock.scale, clock.later));
  await Promise.all(
    thrown.dice.map((d) =>
      Promise.all([
        clock.animate(d.die, d.plan.die, d.plan.land * 1000, { always: !clock.still }),
        clock.animate(d.shadow, d.plan.shadow, d.plan.land * 1000, { always: !clock.still }),
      ]),
    ),
  );
  settles.forEach((settle) => settle());
  if (!thrown.played) sfx?.play('dice_clack', { gain: 0.8 }); // no rattle at speed: one landing clack
  for (const d of thrown.dice) {
    d.die.getAnimations?.().forEach((a) => a.finish());
    clock.animate(d.die, [{ transform: `translate(${d.toX}px,0) rotate(${d.plan.tilt}deg)` }, { transform: `translate(${d.toX}px,0) rotate(${-d.plan.tilt * 0.4}deg)` }, { transform: `translate(${d.toX}px,0) rotate(0deg)` }], 150, { easing: 'ease-out' });
  }
}

async function keepOne(m, thrown, clock) {
  const kept = thrown.dice[m.kept];
  kept.die.classList.add('glow');
  if (thrown.dice.length === 2) {
    const drop = thrown.dice[1 - m.kept];
    drop.die.classList.add('dropped');
    clock.animate(drop.die, [{ transform: `translate(${drop.toX}px,0)`, opacity: 1 }, { transform: `translate(${drop.toX * 1.5}px,-60px) scale(.55)`, opacity: 0.45 }], 300, { easing: 'ease-out' });
    clock.animate(kept.die, [{ transform: `translate(${kept.toX}px,0)` }, { transform: 'translate(0,0) scale(1.18)' }], 300, { easing: 'ease-out' });
    await clock.wait(300);
  }
  return kept;
}

async function naturalOne(m, kept, sfx, clock) {
  if (m.verdict === 'nat1') {
    setSprite(kept.die, 'fumble');
    kept.die.classList.add('cracked');
    sfx?.play('roll_natural_1');
    await clock.wait(380);
  }
}

async function tally(m, els, clock) {
  els.sum.classList.add('on');
  let run = m.face;
  for (let i = 0; i < m.parts.length; i++) {
    els.bonus[i].classList.add('lit');
    run += m.parts[i].value;
    els.ops.textContent = m.parts.slice(0, i + 1).map((p) => ` ${p.value >= 0 ? '+' : '-'} ${Math.abs(p.value)}`).join('');
    els.total.textContent = String(i === m.parts.length - 1 ? m.total : run);
    clock.animate(els.total, [{ transform: 'scale(1.3)' }, { transform: 'scale(1)' }], 160, { easing: 'ease-out' });
    await clock.wait(170);
    els.bonus[i].classList.replace('lit', 'used');
  }
  els.total.textContent = String(m.total);
  await clock.wait(90);
}

async function verdict(m, els, kept, sfx, clock) {
  const v = h('div', { class: `ss-verdict v-${m.verdict}`, 'data-testid': 'stage-verdict' }, t(`show.${m.verdict}`));
  els.verdictSlot.append(v);
  clock.animate(v, [{ opacity: 0, transform: 'scale(2.2)' }, { opacity: 1, transform: 'scale(.94)', offset: 0.62 }, { transform: 'scale(1.04)', offset: 0.82 }, { transform: 'scale(1)' }], 420, { easing: 'cubic-bezier(.2,.8,.3,1.2)', always: true });
  if (m.verdict === 'success') sfx?.play('roll_success');
  if (m.verdict === 'failure') sfx?.play('roll_failure');
  kept.die.classList.add(m.verdict === 'failure' || m.verdict === 'nat1' ? 'dim' : 'win');
}

/** Play one stage roll in `layer`; resolves when the stage has faded (the pacer then moves on). */
export async function playStage(layer, dice, state, sfx, { scale = 1, signal } = {}) {
  const clock = showClock(scale, signal);
  const m = stageModel(dice, state);
  const { root, box, els } = build(m);
  layer.append(root);
  fit(box);
  try {
    await clock.animate(root, [{ opacity: 0 }, { opacity: 1 }], 200, { always: true });
    await clock.wait(READ_MS); // the table reads who rolls what against which DC before the throw
    const thrown = placeDice(m, els, sfx, clock);
    await throwDice(thrown, sfx, clock);
    await clock.wait(160);
    const kept = await keepOne(m, thrown, clock);
    if (m.verdict === 'nat20') {
      const ks = thrown.dice.length === 2 ? 1.18 : 1;
      await playNatural20({ m, els, kept, ks, root, box, sfx, scale, signal }); // until its fade begins
      if (clock.skipped()) await showClock(scale, null).wait(250);
    } else {
      await naturalOne(m, kept, sfx, clock);
      await tally(m, els, clock);
      const wasSkipped = clock.skipped();
      await verdict(m, els, kept, sfx, clock);
      await showClock(scale, null).wait(wasSkipped ? 250 : 1300);
    }
    await clock.animate(root, [{ opacity: 1 }, { opacity: 0 }], 280, { always: true });
  } finally {
    root.remove();
  }
}
