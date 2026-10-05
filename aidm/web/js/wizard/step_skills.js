// Step 5: skills (class picks, race picks, expertise) and the tools the character already has.
import { t } from '../strings.js';
import { h } from '../ui/dom.js';
import {
  classSkillOptions,
  grantedSkills,
  grantedTools,
  proficientSkills,
  raceSkillOptions,
} from './model.js';
import { block, chips, counter, namer, toggled } from './ui.js';

function skillOption(data, id) {
  const entry = data.skills[id];
  return { id, label: `${entry.name} (${t(`abil.${entry.ability}`)})` };
}

function skillBlock(env, { title, key, options, selected, max, field }) {
  const { data, update } = env;
  return block(
    title,
    counter(selected.length, max),
    chips({
      prefix: key,
      options: options.map((id) => skillOption(data, id)),
      selected,
      max,
      onToggle: (id) => update((d) => (d[field] = toggled(d[field], id, max))),
    }),
  );
}

function expertiseBlocks(env) {
  const { data, draft, ctx, update } = env;
  const proficient = proficientSkills(draft, ctx);
  return ctx.cls.expertise.map((ex) => {
    const chosen = draft.featureChoices[ex.id] ?? [];
    return block(
      ex.name,
      h('p', { class: 'hint' }, ex.summary),
      counter(chosen.length, ex.choose),
      chips({
        prefix: `exp-${ex.id}`,
        options: proficient.map((id) => skillOption(data, id)),
        selected: chosen,
        max: ex.choose,
        onToggle: (id) => update((d) => (d.featureChoices[ex.id] = toggled(chosen, id, ex.choose))),
      }),
    );
  });
}

export function renderSkills(env) {
  const { data, draft, ctx } = env;
  const names = namer(data);
  const granted = grantedSkills(ctx).map((id) => ({ id, label: names.skill(id) }));
  const tools = grantedTools(ctx);
  const parts = [
    block(
      t('wz.grantedSkills'),
      granted.length ? chips({ prefix: 'granted', options: [], selected: [], max: 0, locked: granted, onToggle: () => {} }) : h('p', { class: 'hint' }, t('wz.none')),
    ),
    skillBlock(env, {
      title: t('wz.classSkills', { class: ctx.cls.name }),
      key: 'cskill',
      options: classSkillOptions(ctx),
      selected: draft.classSkills,
      max: ctx.cls.skill_choice.choose,
      field: 'classSkills',
    }),
  ];
  const race = ctx.effective.skill_choice;
  if (race) {
    parts.push(
      skillBlock(env, {
        title: t('wz.raceSkills'),
        key: 'rskill',
        options: raceSkillOptions(draft, ctx),
        selected: draft.raceSkills,
        max: race.choose,
        field: 'raceSkills',
      }),
    );
  }
  parts.push(...expertiseBlocks(env));
  if (tools.length) parts.push(block(t('wz.grantedTools'), h('p', {}, tools.map(names.tool).join(', '))));
  return h('div', {}, ...parts);
}
