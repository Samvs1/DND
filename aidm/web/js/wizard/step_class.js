// Step 2: class (hit die, saves, level-1 features) and its level-1 choices (fighting style).
import { assetUrl } from '../assets.js';
import { t } from '../strings.js';
import { h } from '../ui/dom.js';
import { block, card, chips, counter, namer, toggled } from './ui.js';

function classChoices(env) {
  const { draft, ctx, update } = env;
  return ctx.cls.class_choices.map((choice) => {
    const chosen = draft.classChoices[choice.id] ?? [];
    const opts = choice.options.map((o) => ({ id: o.id, label: o.name, hint: o.summary }));
    const info = choice.options.filter((o) => chosen.includes(o.id)).map((o) => h('p', { class: 'hint' }, o.summary));
    return block(
      t(`wz.choice_${choice.kind}`),
      counter(chosen.length, choice.choose),
      chips({
        prefix: `cc-${choice.id}`,
        options: opts,
        selected: chosen,
        max: choice.choose,
        onToggle: (id) => update((d) => (d.classChoices[choice.id] = toggled(chosen, id, choice.choose))),
      }),
      ...info,
    );
  });
}

function featurePicks(env) {
  const { draft, ctx, update } = env;
  return ctx.cls.feature_picks.map((pick) => {
    const chosen = draft.featureChoices[pick.id] ?? [];
    const opts = pick.options.map((o) => ({ id: o.id, label: o.name, hint: o.summary }));
    return block(
      pick.name,
      counter(chosen.length, pick.choose),
      chips({
        prefix: `fp-${pick.id}`,
        options: opts,
        selected: chosen,
        max: pick.choose,
        onToggle: (id) => update((d) => (d.featureChoices[pick.id] = toggled(chosen, id, pick.choose))),
      }),
    );
  });
}

function details(env) {
  const { data, ctx } = env;
  if (!ctx.cls) return h('div', {});
  const names = namer(data);
  const cls = ctx.cls;
  const facts = [
    t('wz.hitDie', { n: cls.hit_die }),
    t('wz.saves', { list: cls.saves.map(names.ability).join(', ') }),
    t('wz.armor', { list: cls.armor.join(', ') || t('wz.none') }),
  ];
  return h(
    'div',
    { class: 'wz-details panel' },
    h('h3', {}, cls.name),
    h('ul', { class: 'wz-facts' }, ...facts.map((f) => h('li', {}, f))),
    h('ul', { class: 'wz-traits' }, ...cls.features.map((f) => h('li', {}, h('strong', {}, f.name), ' ', f.summary))),
    ...classChoices(env),
    ...featurePicks(env),
  );
}

export function renderClass(env) {
  const { data, draft, update } = env;
  const names = namer(data);
  const cards = data.classes.map((cls) =>
    card({
      key: `class-${cls.index}`,
      selected: draft.cls === cls.index,
      art: assetUrl(`portrait.icon.${cls.index}`),
      title: cls.name,
      lines: [t('wz.hitDie', { n: cls.hit_die }), cls.primary.map(names.ability).join(' / ')],
      tag: cls.casting ? t('wz.caster') : null,
      onSelect: () => update((d) => (d.cls = cls.index)),
    }),
  );
  return h('div', {}, h('div', { class: 'wz-cards' }, ...cards), details(env));
}
