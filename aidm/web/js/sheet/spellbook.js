// Sheet "Spellbook" tab: casting numbers, slot trackers (current/max, pact slots), the concentration
// indicator and spells by level (cantrips first). Re-preparing spells is Tier 2: prepared status is shown only.
// M27.7: a wizard's "Copy a scroll" list: each carried scroll that can be copied, its cost and a Copy button
// (`copy_scroll`; out of a fight only, the server's scroll rules decide).
import { assetUrl } from '../assets.js';
import { t } from '../strings.js';
import { h } from '../ui/dom.js';
import { tipButton } from '../ui/tip.js';

const signed = (n) => (n >= 0 ? `+${n}` : String(n));

function slotTracker(group) {
  return group.slots.map((slot) => {
    const pips = Array.from({ length: slot.maximum }, (_, i) => h('span', { class: i < slot.current ? 'slot-pip full' : 'slot-pip', 'aria-hidden': 'true' }));
    const label = slot.kind === 'pact' ? t('sheet.slotsPact', { n: group.level }) : t('sheet.slotsLevel', { n: group.level });
    return h(
      'div',
      { class: 'slot-row', 'data-testid': 'slot-tracker', 'data-level': group.level },
      h('span', { class: 'slot-label' }, label),
      h('span', { class: 'slot-pips' }, ...pips),
      h('span', { class: 'slot-count', 'data-testid': 'slot-count' }, t('sheet.slotsCount', { current: slot.current, max: slot.maximum })),
    );
  });
}

function status(spell) {
  if (spell.level === 0) return null;
  if (spell.always_prepared) return t('sheet.alwaysPrepared');
  return spell.prepared ? t('sheet.prepared') : t('sheet.notPrepared');
}

function spellRow(spell, concentratingOn) {
  const range = spell.range_kind === 'feet' ? t('sheet.rangeFeet', { n: spell.range_feet }) : t(`sheet.range_${spell.range_kind}`);
  const meta = t('sheet.spellMeta', { time: t(`sheet.time_${spell.casting_time}`), range });
  const state = status(spell);
  return h(
    'li',
    { class: `spell-line${spell.prepared ? '' : ' dim'}`, 'data-testid': 'spell-line', 'data-spell': spell.index },
    h('img', { src: assetUrl([`spell_icon.${spell.index}`, 'spell_icon.school.arcane']), alt: '', width: 28, height: 28 }),
    h(
      'div',
      { class: 'spell-main' },
      h('strong', {}, spell.name),
      tipButton(`spell:${spell.index}`, spell.name),
      spell.concentration ? h('span', { class: 'tag' }, t('sheet.concentration')) : null,
      concentratingOn === spell.index ? h('span', { class: 'tag active-conc', 'data-testid': 'conc-active' }, t('sheet.concentrating', { spell: spell.name })) : null,
      h('div', { class: 'hint' }, meta),
    ),
    state ? h('span', { class: 'spell-state' }, state) : null,
  );
}

function spellSection(title, spells, concentratingOn) {
  return h('section', { class: 'sh-block' }, h('h4', {}, title), h('ul', { class: 'spell-lines' }, ...spells.map((sp) => spellRow(sp, concentratingOn))));
}

function copyRow(line, { client, locked }) {
  const label = t('sheet.copyItem', { name: line.name, cost: line.cost });
  const why = locked ? t('sheet.copyWhyFight') : line.affordable ? '' : t('sheet.copyWhyGold', { cost: line.cost });
  return h(
    'li',
    { class: 'spell-line', 'data-testid': 'copy-line', 'data-item': line.item },
    h('img', { src: assetUrl([`item_icon.${line.item}`, 'item_icon.scroll']), alt: '', width: 28, height: 28 }),
    h('div', { class: 'spell-main' }, h('strong', {}, line.name), h('div', { class: 'hint' }, t('sheet.copyLine', { level: line.level, cost: line.cost }))),
    h('div', { class: 'copy-act' }, h('button', { type: 'button', class: 'btn btn-small', disabled: Boolean(why), 'data-testid': `copy-${line.item}`, 'aria-label': label, onclick: () => client.send('copy_scroll', { item_id: line.item }) }, t('sheet.copyButton')), why ? h('span', { class: 'hint copy-why', 'data-testid': 'copy-why' }, why) : null),
  );
}

function copySection(lines, opts) {
  if (!lines?.length || !opts?.client) return null;
  const hint = opts.locked ? t('sheet.copyFight') : t('sheet.copyHint');
  return h('section', { class: 'sh-block', 'data-testid': 'sh-copy' }, h('h4', {}, t('sheet.copyScrolls')), h('p', { class: 'hint' }, hint), h('ul', { class: 'spell-lines' }, ...lines.map((line) => copyRow(line, opts))));
}

export function renderSpellbook(s, opts = null) {
  const c = s.spellcasting;
  if (!c) return [h('p', { class: 'hint', 'data-testid': 'no-spells' }, t('sheet.noSpells'))];
  const prepared = c.levels.flatMap((g) => g.spells).filter((sp) => sp.prepared && !sp.always_prepared && sp.source === 'class').length;
  const limit = c.prepared_limit ? ` ${t('sheet.preparedLine', { n: prepared, max: c.prepared_limit })}` : '';
  const out = [
    h('p', { class: 'sh-gold', 'data-testid': 'sh-casting' }, t('sheet.castingLine', { attack: signed(c.attack_bonus), dc: c.save_dc }), limit),
    h('section', { class: 'sh-block', 'data-testid': 'sh-slots' }, h('h4', {}, t('sheet.slots'), tipButton('sheet:slots', t('sheet.slots'))), ...c.levels.flatMap(slotTracker)),
  ];
  if (c.cantrips.length) out.push(spellSection(t('sheet.cantrips'), c.cantrips, s.concentrating_on));
  for (const group of c.levels) {
    if (group.spells.length) out.push(spellSection(t('sheet.spellLevel', { n: group.level }), group.spells, s.concentrating_on));
  }
  const copies = copySection(s.scroll_copies, opts);
  if (copies) out.push(copies);
  out.push(h('p', { class: 'hint' }, t('sheet.reprepare')));
  return out;
}
