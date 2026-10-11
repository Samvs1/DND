// The BG3-style hotbar for the active hero: action / bonus / movement pips, attacks with hit-chance
// tooltips, spells and items popovers, standard and bonus actions, class feature actions with their uses left,
// end turn, number-key shortcuts.
// Non-active players see who is acting and can send suggestions (suggest.js).
import { t } from '../strings.js';
import { clear, h } from '../ui/dom.js';
import { attackSlots, bonusSlots, featureSlots, moveSlots } from './hotbar_slots.js';
import { itemPopover, spellPopover } from './hotbar_magic.js';
import { combatOf, isMyTurn, myCreatureId, tokenById } from './model.js';
import { mountSuggest } from './suggest.js';

const NO_ECON = { action: false, bonus_action: false, movement_left: 0, reaction: false, attacks_left: 0 };

function pip(label, on, testid) {
  return h(
    'span',
    { class: `pip-chip ${on ? 'on' : 'spent'}`, 'data-testid': testid, title: `${label}: ${on ? t('hotbar.ready') : t('hotbar.spent')}` },
    h('span', { class: 'pip-dot', 'aria-hidden': 'true' }),
    h('span', {}, label),
    h('span', { class: 'sr-only' }, on ? t('hotbar.ready') : t('hotbar.spent')),
  );
}

function pips(econ, speed) {
  const feet = econ.movement_left;
  const fill = h('span', { class: 'move-fill' });
  fill.style.width = `${Math.min(100, Math.round((feet / Math.max(speed || 30, feet, 1)) * 100))}%`;
  return h(
    'div',
    { class: 'pips', 'data-testid': 'pips' },
    pip(t('hotbar.action'), econ.action, 'pip-action'),
    pip(t('hotbar.bonusAction'), econ.bonus_action, 'pip-bonus'),
    h('span', { class: 'pip-chip move', 'data-testid': 'pip-move' }, t('hotbar.movement'), ' ', h('strong', {}, t('hotbar.movementFeet', { n: feet })), h('span', { class: 'move-bar', 'aria-hidden': 'true' }, fill)),
    pip(t('hotbar.reaction'), econ.reaction, 'pip-reaction'),
    econ.attacks_left > 0 ? h('span', { class: 'pip-chip', 'data-testid': 'pip-attacks' }, t('hotbar.attacksLeft', { n: econ.attacks_left })) : null,
  );
}

function keyBadge(number) {
  return number <= 9 ? h('span', { class: 'hb-key', 'aria-hidden': 'true' }, String(number)) : null;
}

function slotButton(desc, number) {
  const adv = desc.adv && desc.adv !== 'normal' ? h('span', { class: `adv-mark ${desc.adv}`, 'data-testid': 'adv-mark' }, t(desc.adv === 'advantage' ? 'hotbar.advUp' : 'hotbar.advDown')) : null;
  return h(
    'button',
    { type: 'button', class: `hb-slot ${desc.group}`, 'data-testid': `slot-${desc.id}`, 'data-key': number <= 9 ? String(number) : null, 'aria-keyshortcuts': number <= 9 ? String(number) : null, disabled: Boolean(desc.off), 'aria-describedby': `tip-${desc.id}`, onclick: desc.run },
    keyBadge(number),
    desc.art ? h('img', { class: 'hb-art', src: desc.art, alt: '', width: 28, height: 28 }) : null,
    h('span', { class: 'hb-label' }, desc.label),
    desc.sub ? h('span', { class: 'hb-sub', 'data-testid': 'slot-sub' }, desc.sub) : null,
    adv,
    h('span', { class: 'hb-tip', role: 'tooltip', id: `tip-${desc.id}` }, desc.tip),
  );
}

function popButton(id, label, tip, open, onclick, number) {
  return h(
    'button',
    { type: 'button', class: `hb-slot pop${open ? ' open' : ''}`, 'data-testid': `slot-${id}`, 'data-key': number <= 9 ? String(number) : null, 'aria-keyshortcuts': number <= 9 ? String(number) : null, 'aria-expanded': open ? 'true' : 'false', 'aria-describedby': `tip-${id}`, onclick },
    keyBadge(number),
    h('span', { class: 'hb-label' }, label),
    h('span', { class: 'hb-tip', role: 'tooltip', id: `tip-${id}` }, tip),
  );
}

function aimBar(ctrl) {
  const a = ctrl.ui.arming;
  const spec = a?.steps[a.step];
  if (!spec) return null;
  const prompt = typeof spec.prompt === 'function' ? spec.prompt(a.picks[a.step].length) : spec.prompt;
  return [
    h('span', {}, prompt),
    (spec.count ?? 1) > 1 ? h('button', { type: 'button', class: 'btn btn-small', 'data-testid': 'aim-done', onclick: () => ctrl.doneEarly() }, t('combat.pickDone')) : null,
    h('button', { type: 'button', class: 'btn btn-small', 'data-testid': 'aim-cancel', onclick: () => ctrl.cancel() }, t('combat.pickCancel')),
  ];
}

function fillBody(body, pop, c, ctrl) {
  const slots = [...attackSlots(c), ...moveSlots(c), ...bonusSlots(c)];
  let n = 0;
  const group = (name, descs, extras = []) => {
    const nodes = [...descs.map((d) => slotButton(d, ++n)), ...extras];
    if (nodes.length) body.append(h('div', { class: 'hb-group', role: 'group', 'aria-label': t(`hotbar.${name}`) }, ...nodes));
  };
  const attacks = slots.filter((s) => s.group === 'attacks');
  const extras = [];
  const next = () => attacks.length + 1 + extras.length;
  if (c.sheet?.spellcasting) extras.push(popButton('spells', t('hotbar.spellsOpen'), t('hotbar.tip_spells'), ctrl.ui.popup === 'spells', () => ctrl.setPopup('spells'), next()));
  extras.push(popButton('items', t('hotbar.itemsOpen'), t('hotbar.tip_items'), ctrl.ui.popup === 'items', () => ctrl.setPopup('items'), next()));
  group('attacks', attacks, extras);
  n += extras.length;
  group('moves', slots.filter((s) => s.group === 'moves'));
  group('bonus', slots.filter((s) => s.group === 'bonus'));
  group('features', featureSlots(c));
  body.append(h('button', { type: 'button', class: 'btn btn-primary hb-end', 'data-testid': 'end-turn', onclick: () => ctrl.send({ type: 'end_turn', actor_id: c.me }) }, t('hotbar.endTurn')));
  if (ctrl.ui.popup === 'spells') pop.append(spellPopover(c));
  if (ctrl.ui.popup === 'items') pop.append(itemPopover(c));
}

export function mountHotbar(root, ctx, ctrl) {
  const { store } = ctx;
  const head = h('div', { class: 'hb-head' });
  const note = h('p', { class: 'hb-note', role: 'status', 'data-testid': 'hotbar-note' });
  const aim = h('div', { class: 'hb-aim', 'data-testid': 'aim-bar' });
  const body = h('div', { class: 'hb-body' });
  const pop = h('div', { class: 'hb-popslot' });
  const tail = h('div', { class: 'hb-tail' });
  root.append(head, note, aim, pop, body, tail);
  const stopSuggest = mountSuggest(tail, ctx, ctrl);
  let last = '';

  function render(state) {
    const combat = combatOf(state);
    root.hidden = !combat || !myCreatureId(state);
    if (root.hidden) return;
    const mine = isMyTurn(state);
    const a = ctrl.ui.arming;
    const key = JSON.stringify([mine, combat.economy, combat.active_id, state.sheet, ctrl.ui.target, ctrl.ui.chances, a?.step, a?.picks, ctrl.ui.popup, ctrl.ui.message]);
    if (key === last) return;
    last = key;
    clear(head);
    clear(body);
    clear(pop);
    clear(aim);
    note.textContent = ctrl.ui.message;
    root.classList.toggle('waiting', !mine);
    if (!mine) {
      const who = tokenById(combat, combat.active_id ?? combat.turn_of)?.name ?? '';
      head.append(h('p', { class: 'hb-wait', 'data-testid': 'hotbar-wait' }, t('combat.notYourTurn', { name: who })));
      return;
    }
    const econ = combat.economy ?? NO_ECON;
    const sheet = state.sheet?.sheet ?? null;
    head.append(h('strong', { class: 'hb-turn' }, t('combat.yourTurn')), pips(econ, sheet?.speed), h('span', { class: 'hb-keys', 'data-testid': 'hotbar-keys' }, t('hotbar.keysHint')));
    const bar = aimBar(ctrl);
    if (bar) aim.append(...bar.filter(Boolean));
    fillBody(body, pop, { ctrl, sheet, econ, me: myCreatureId(state) }, ctrl);
  }

  function keys(event) {
    if (event.key === 'Escape') {
      if (ctrl.cancel()) event.preventDefault();
      return;
    }
    const tag = event.target?.tagName;
    if (event.ctrlKey || event.metaKey || event.altKey || tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
    if (/^[1-9]$/.test(event.key) && !root.hidden) {
      const button = root.querySelector(`[data-key="${event.key}"]:not(:disabled)`);
      if (button) {
        event.preventDefault();
        button.click();
      }
    }
  }
  document.addEventListener('keydown', keys);
  render(store.get());
  const stopStore = store.subscribe(render);
  const stopCtrl = ctrl.subscribe(() => render(store.get()));
  return () => {
    document.removeEventListener('keydown', keys);
    stopStore();
    stopCtrl();
    stopSuggest();
  };
}
