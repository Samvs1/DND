// The spell and item popovers of the hotbar: spells by level with slot pickers (upcasting), then targeting by
// the spell's kind; potions and the hero's gear uses in a fight with their cost (M27.6).
import { assetUrl } from '../assets.js';
import { t } from '../strings.js';
import { h } from '../ui/dom.js';
import { percent } from './model.js';

/** Slot levels this hero can still cast with: [{level, current, max}]. */
export function openSlots(casting) {
  const out = [];
  for (const group of casting?.levels ?? []) {
    const current = group.slots.reduce((n, s) => n + s.current, 0);
    const max = group.slots.reduce((n, s) => n + s.maximum, 0);
    if (max > 0) out.push({ level: group.level, current, max, pact: group.slots.some((s) => s.kind === 'pact') });
  }
  return out;
}

function castCommand(me, spell, slot, picks) {
  const cmd = { type: 'cast', actor_id: me, spell_id: spell.index, slot_level: spell.level === 0 ? null : slot };
  const first = picks[0] ?? [];
  if (spell.target_kind === 'area' || spell.target_kind === 'point') cmd.target_zone = first[0] ?? null;
  else cmd.target_ids = first;
  return cmd;
}

/** Start casting `spell` at `slot`: self and own-zone spells cast at once, the rest aim first. */
export function startCast(ctx, spell, slot) {
  const { ctrl, me } = ctx;
  const extra = Math.max(0, slot - spell.level) * (spell.count_per_slot || 0);
  const count = spell.target_count + extra;
  const live = (token) => !token.dead;
  const kind = spell.target_kind;
  if (kind === 'self' || (kind === 'area' && spell.range_kind === 'self')) return ctrl.send(castCommand(me, spell, slot, []));
  const step =
    kind === 'area' || kind === 'point'
      ? { need: 'zone', prompt: t('combat.pickZone') }
      : { need: 'creature', count: kind === 'creatures' ? count : 1, valid: live, prompt: kind === 'creatures' ? (n) => t('combat.pickAllies', { n: n + 1, total: count }) : t('combat.pickTarget') };
  ctrl.arm({ steps: [step], build: (picks) => castCommand(me, spell, slot, picks) });
}

// M20.4: an attack spell shows its hit chance on the picked target, like a weapon (`spell:<index>`).
function chanceTag(ctx, spell) {
  const target = ctx.ctrl.ui.target;
  const chance = target ? ctx.ctrl.ui.chances[target]?.[`spell:${spell.index}`] : null;
  if (!chance) return null;
  return h('span', { class: 'tag', 'data-testid': 'spell-chance' }, chance.in_range ? percent(chance.probability) : t('hotbar.outOfRange'));
}

function spellRow(ctx, spell, slots) {
  const { econ } = ctx;
  const bonus = spell.casting_time === 'bonus_action';
  const timeOk = spell.casting_time === 'action' ? econ.action : bonus ? econ.bonus_action : false;
  const levels = spell.level === 0 ? [0] : slots.filter((s) => s.level >= spell.level && s.current > 0).map((s) => s.level);
  const castable = timeOk && levels.length > 0;
  const buttons = levels.map((level, i) =>
    h('button', { type: 'button', class: i === 0 ? 'btn btn-small' : 'btn btn-small alt', disabled: !castable, 'data-testid': `cast-${spell.index}`, 'data-level': level, 'aria-label': spell.level === 0 ? spell.name : `${spell.name}, ${t('hotbar.slotPick')} ${level}`, onclick: () => startCast(ctx, spell, level) }, spell.level === 0 ? t('hotbar.cantrips') : i === 0 ? spell.name : String(level)),
  );
  if (levels.length > 1) buttons.splice(0, 1, h('span', { class: 'spell-name' }, spell.name), h('span', { class: 'hint' }, t('hotbar.slotPick')), buttons[0]);
  return h(
    'li',
    { class: `spell-row${castable ? '' : ' off'}` },
    h('img', { src: assetUrl([`spell_icon.${spell.index}`, 'spell_icon.school.arcane']), alt: '', width: 28, height: 28 }),
    levels.length > 1 ? null : h('span', { class: 'spell-name' }, spell.name),
    spell.concentration ? h('span', { class: 'tag', title: t('hotbar.concentration') }, 'C') : null,
    bonus ? h('span', { class: 'tag' }, t('hotbar.spellBonus')) : null,
    chanceTag(ctx, spell),
    ...(levels.length ? buttons : [h('span', { class: 'hint' }, t('hotbar.noSlot'))]),
  );
}

export function spellPopover(ctx) {
  const casting = ctx.sheet?.spellcasting;
  const slots = openSlots(casting);
  const groups = [];
  if (casting?.cantrips.length) groups.push(h('section', {}, h('h5', {}, t('hotbar.cantrips')), h('ul', { class: 'spell-list' }, ...casting.cantrips.map((s) => spellRow(ctx, s, slots)))));
  for (const group of casting?.levels ?? []) {
    if (!group.spells.length) continue;
    const slot = slots.find((s) => s.level === group.level);
    groups.push(
      h('section', {}, h('h5', {}, t('hotbar.spellLevel', { n: group.level }), slot ? h('span', { class: 'slot-count' }, ` ${t('hotbar.slotCount', { current: slot.current, max: slot.max })}`) : null), h('ul', { class: 'spell-list' }, ...group.spells.map((s) => spellRow(ctx, s, slots)))),
    );
  }
  return h('div', { class: 'hb-pop', role: 'group', 'aria-label': t('hotbar.magic'), 'data-testid': 'spell-pop' }, ...(groups.length ? groups : [h('p', { class: 'hint' }, t('hotbar.spellsEmpty'))]));
}

// M27.6: a gear use is aimed by what it takes (a foe, a fallen ally, a zone) and sent as the
// `use_item` combat command; the server's item rules decide (a refusal comes back as a typed code).
const GEAR_STEPS = {
  creature: () => [{ need: 'creature', valid: (tk) => !tk.dead && !tk.withdrawn, prompt: t('combat.pickTarget') }],
  ally: (me) => [{ need: 'creature', valid: (tk) => tk.side === 'party' && !tk.dead && tk.creature_id !== me, prompt: t('hotbar.pickFallen') }],
  zone: () => [{ need: 'zone', prompt: t('combat.pickZone') }],
};

function useGear(ctx, use) {
  const { ctrl, me } = ctx;
  const cmd = (extra) => ({ type: 'use_item', actor_id: me, item: use.item, use_id: use.use_id, ...extra });
  const steps = GEAR_STEPS[use.target];
  if (!steps) return ctrl.send(cmd({}));
  const aim = use.target === 'zone' ? (p) => cmd({ target_zone: p[0][0] }) : (p) => cmd({ target_id: p[0][0] });
  ctrl.arm({ steps: steps(me), build: aim });
}

function gearRow(ctx, use) {
  const bonus = use.cost === 'bonus';
  const ready = bonus ? ctx.econ.bonus_action : ctx.econ.action;
  return h('li', { class: `spell-row${ready ? '' : ' off'}`, 'data-testid': 'gear-row', 'data-use': use.use_id },
    h('img', { src: assetUrl([`item_icon.${use.item}`, 'item_icon.gear']), alt: '', width: 28, height: 28 }),
    h('span', { class: 'spell-name' }, use.name),
    h('span', { class: 'tag', 'data-testid': 'gear-cost' }, t(bonus ? 'hotbar.econ_bonus_action' : 'hotbar.econ_action')),
    use.qty > 1 ? h('span', { class: 'hint' }, t('hotbar.itemCount', { n: use.qty })) : null,
    h('button', { type: 'button', class: 'btn btn-small', disabled: !ready, 'data-testid': `gear-${use.use_id}`, 'aria-label': use.label, onclick: () => useGear(ctx, use) }, use.label));
}

export function itemPopover(ctx) {
  const { ctrl, me, econ } = ctx;
  const usable = (ctx.sheet?.inventory ?? []).filter((i) => i.category === 'potion');
  const rows = usable.map((item) =>
    h('li', { class: 'spell-row' },
      h('img', { src: assetUrl([`item_icon.${item.item}`, 'item_icon.potion']), alt: '', width: 28, height: 28 }),
      h('span', { class: 'spell-name' }, item.name),
      h('span', { class: 'tag' }, t('hotbar.econ_bonus_action')),
      h('span', { class: 'hint' }, t('hotbar.itemCount', { n: item.qty })),
      h('button', { type: 'button', class: 'btn btn-small', disabled: !econ.bonus_action, 'data-testid': `use-${item.item}`, 'aria-label': t('hotbar.useItem', { name: item.name }), onclick: () => ctrl.send({ type: 'use_item', actor_id: me, item: item.item }) }, t('hotbar.useItem', { name: item.name }))),
  );
  rows.push(...(ctx.sheet?.gear_uses ?? []).map((use) => gearRow(ctx, use)));
  return h('div', { class: 'hb-pop', role: 'group', 'aria-label': t('hotbar.items'), 'data-testid': 'item-pop' }, rows.length ? h('ul', { class: 'spell-list' }, ...rows) : h('p', { class: 'hint' }, t('hotbar.itemsEmpty')));
}
