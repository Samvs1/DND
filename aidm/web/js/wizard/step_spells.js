// Step 7 (casters only): cantrips, racial cantrip, known spells or spellbook, prepared spells. Shipped spells only.
import { t } from '../strings.js';
import { h } from '../ui/dom.js';
import { casting } from './model.js';
import { block, counter, toggled } from './ui.js';

function spellCard(spell, selected, disabled, onToggle) {
  const level = spell.level === 0 ? t('wz.cantrip') : t('wz.spellLevel', { n: spell.level });
  const meta = [level, spell.school, spell.concentration ? t('wz.concentration') : null].filter(Boolean).join(' / ');
  return h(
    'button',
    {
      type: 'button',
      class: selected ? 'wz-card selected' : 'wz-card',
      'aria-pressed': String(selected),
      'data-key': `spell-${spell.index}`,
      disabled: disabled && !selected,
      onclick: onToggle,
    },
    h('span', { class: 'wz-card-body' }, h('strong', { class: 'wz-card-title' }, spell.name), h('span', { class: 'wz-line' }, meta), h('span', { class: 'wz-line wz-text' }, spell.text)),
  );
}

function spellBlock(env, { title, hint, pool, field, max, selected }) {
  const { data, update } = env;
  const cards = pool.map((id) =>
    spellCard(data.spells[id], selected.includes(id), selected.length >= max, () => update((d) => (d[field] = toggled(d[field], id, max)))),
  );
  return block(title, hint ? h('p', { class: 'hint' }, hint) : null, counter(selected.length, max), h('div', { class: 'wz-cards wz-cards-tight' }, ...cards));
}

export function renderSpells(env) {
  const { data, draft, ctx } = env;
  const cast = casting(draft, data, ctx);
  const note = cast.ability ? t('wz.spellNote', { ability: t(`abil.${cast.ability}`) }) : t('wz.raceSpellNote');
  const parts = [h('p', { class: 'hint' }, note)];
  if (cast.cantrip_count) {
    parts.push(spellBlock(env, { title: t('wz.cantrips'), pool: cast.cantrips, field: 'cantrips', max: cast.cantrip_count, selected: draft.cantrips }));
  }
  if (cast.raceCount) {
    parts.push(spellBlock(env, { title: t('wz.raceCantrip'), pool: cast.racePool, field: 'raceCantrips', max: cast.raceCount, selected: draft.raceCantrips }));
  }
  if (cast.spell_count) {
    const title = cast.spellbook ? t('wz.spellbook') : t('wz.spellsKnown');
    parts.push(spellBlock(env, { title, pool: cast.spells, field: 'spells', max: cast.spell_count, selected: draft.spells }));
  }
  if (cast.prepares) {
    const hint = cast.spellbook ? t('wz.prepareFromBook', { n: cast.limit }) : t('wz.prepareFromList', { n: cast.limit });
    parts.push(spellBlock(env, { title: t('wz.prepared'), hint, pool: cast.preparedPool, field: 'prepared', max: cast.limit, selected: draft.prepared }));
  }
  return h('div', {}, ...parts);
}
