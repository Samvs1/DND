// Step 6: equipment packages (one option per class choice) plus what the class and background always give.
import { t } from '../strings.js';
import { h } from '../ui/dom.js';
import { block, card } from './ui.js';

function itemsText(lines) {
  return lines.map((l) => (l.qty > 1 ? `${l.name} x${l.qty}` : l.name)).join(', ');
}

function choiceBlock(env, choice) {
  const { draft, update } = env;
  const cards = choice.options.map((option, index) =>
    card({
      key: `eq-${choice.id}-${index}`,
      selected: draft.equipment[choice.id] === index,
      title: itemsText(option),
      onSelect: () => update((d) => (d.equipment[choice.id] = index)),
    }),
  );
  return block(choice.label, h('div', { class: 'wz-cards wz-cards-tight' }, ...cards));
}

export function renderEquipment(env) {
  const { ctx } = env;
  const fixed = [...ctx.cls.equipment.fixed, ...ctx.bg.gear];
  return h(
    'div',
    {},
    ...ctx.cls.equipment.choices.map((choice) => choiceBlock(env, choice)),
    block(t('wz.alwaysIncluded'), h('p', {}, itemsText(fixed))),
  );
}
