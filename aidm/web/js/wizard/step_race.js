// Step 1: race and subrace, plus the heritage picks they bring (half-elf abilities, tools, languages, ancestry).
import { assetUrl } from '../assets.js';
import { t } from '../strings.js';
import { h } from '../ui/dom.js';
import { languageOptions, racePicks, toolOptions } from './model.js';
import { block, bonusText, card, chips, counter, namer, toggled } from './ui.js';

function traitList(effective) {
  return h(
    'ul',
    { class: 'wz-traits' },
    ...effective.traits.map((tr) => h('li', {}, h('strong', {}, tr.name), ' ', tr.summary)),
  );
}

function pickBlock(title, key, options, selected, max, onToggle) {
  return block(title, counter(selected.length, max), chips({ prefix: key, options, selected, max, onToggle }));
}

function heritagePicks(env) {
  const { data, draft, ctx, update } = env;
  const picks = racePicks(ctx);
  const names = namer(data);
  const out = [];
  if (picks.abilities) {
    const opts = ctx.effective.ability_choice.options.map((a) => ({ id: a, label: names.ability(a) }));
    const toggle = (id) => update((d) => (d.abilityPicks = toggled(d.abilityPicks, id, picks.abilities)));
    const title = t('wz.abilityPicks', { bonus: ctx.effective.ability_choice.bonus });
    out.push(pickBlock(title, 'apick', opts, draft.abilityPicks, picks.abilities, toggle));
  }
  for (const pick of picks.traits) {
    const opts = pick.options.map((o) => ({ id: o.id, label: o.name, hint: o.summary }));
    const chosen = draft.featureChoices[pick.id] ?? [];
    const toggle = (id) => update((d) => (d.featureChoices[pick.id] = toggled(chosen, id, pick.choose)));
    out.push(pickBlock(pick.name, `trait-${pick.id}`, opts, chosen, pick.choose, toggle));
  }
  if (picks.tools) {
    const opts = toolOptions(ctx).map((x) => ({ id: x, label: names.tool(x) }));
    const toggle = (id) => update((d) => (d.tools = toggled(d.tools, id, picks.tools)));
    out.push(pickBlock(t('wz.toolPick'), 'tool', opts, draft.tools, picks.tools, toggle));
  }
  if (picks.languages) {
    const opts = languageOptions(data, ctx).map((x) => ({ id: x, label: names.language(x) }));
    const toggle = (id) => update((d) => (d.languages = toggled(d.languages, id, picks.languages)));
    out.push(pickBlock(t('wz.languagePick'), 'lang', opts, draft.languages, picks.languages, toggle));
  }
  return out;
}

function subraceCards(env) {
  const { draft, ctx, update } = env;
  const cards = ctx.race.subraces.map((s) =>
    card({
      key: `sub-${s.index}`,
      selected: draft.subrace === s.index,
      title: s.name,
      lines: [bonusText(s.effective.ability_bonuses)],
      onSelect: () => update((d) => (d.subrace = s.index)),
    }),
  );
  return block(t('wz.subrace'), h('div', { class: 'wz-cards' }, ...cards));
}

function details(env) {
  const { ctx } = env;
  if (!ctx.race) return h('div', {});
  const parts = [h('h3', {}, ctx.race.name)];
  if (ctx.race.subraces.length) parts.push(subraceCards(env));
  if (ctx.effective) parts.push(traitList(ctx.effective), ...heritagePicks(env));
  return h('div', { class: 'wz-details panel' }, ...parts);
}

export function renderRace(env) {
  const { data, draft, update } = env;
  const cards = data.races.map((race) =>
    card({
      key: `race-${race.index}`,
      selected: draft.race === race.index,
      art: assetUrl(`portrait.race.${race.index}.m`),
      title: race.name,
      lines: [bonusText(race.effective.ability_bonuses) || t('wz.choiceBonus'), t('wz.speed', { n: race.speed })],
      onSelect: () =>
        update((d) => {
          d.race = race.index;
          d.subrace = null;
        }),
    }),
  );
  return h('div', {}, h('div', { class: 'wz-cards' }, ...cards), details(env));
}
