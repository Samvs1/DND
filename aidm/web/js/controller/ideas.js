// Idea chips of the Play tab (M18.2): what you could do here, built from the public scene (people, things, ways
// on) plus a few actions that always make sense. A tap puts a sentence in the action box and focuses it (it
// never sends by itself); Trade opens the shop. Hidden in a fight and whenever the action box is blocked.
// M23.8: a locked way says why when tapped (`exit.locked_reason`, a world fact from the server).
import { assetUrl } from '../assets.js';
import { combatOf } from '../combat/model.js';
import { publicState } from '../table/lookup.js';
import { t } from '../strings.js';
import { clear, h } from '../ui/dom.js';
import { blockedReason } from './action.js';

/** The chip groups for a scene: [{group, chips: [{kind, label, text?, locked?, shop?}]}], empty groups dropped. */
export function ideaGroups(scene) {
  const people = (scene?.npcs ?? []).map((npc) => ({ kind: 'talk', label: npc.name, text: t('ct.say_talk', { name: npc.name }) }));
  const things = [
    ...(scene?.features ?? []).map((f) => ({ kind: 'examine', label: f.name, text: t('ct.say_examine', { name: f.name }) })),
    ...(scene?.items ?? []).map((item) => ({ kind: 'take', label: item, text: t('ct.say_take', { name: item }) })),
  ];
  const ways = (scene?.exits ?? []).map((exit) => ({ kind: 'travel', label: exit.name, text: t('ct.say_travel', { name: exit.name }), locked: exit.locked, why: exit.locked_reason || '' }));
  const always = [
    { kind: 'look', label: t('ct.idea_look'), text: t('ct.say_look') },
    { kind: 'search', label: t('ct.idea_search'), text: t('ct.say_search') },
    { kind: 'rest', label: t('ct.idea_rest'), text: t('ct.say_rest') },
  ];
  if (scene?.shop_npc_id || scene?.shopkeepers?.length) always.push({ kind: 'trade', label: t('ct.trade'), shop: true });
  return [
    { group: 'people', chips: people },
    { group: 'here', chips: things },
    { group: 'ways', chips: ways },
    { group: 'always', chips: always },
  ].filter((g) => g.chips.length > 0);
}

function chip(item, store, showWhy) {
  const props = {
    type: 'button',
    class: `ct-chip ct-chip-${item.kind}`,
    'data-kind': item.kind,
    'data-testid': item.shop ? 'open-shop' : 'idea-chip',
    'aria-disabled': item.locked ? 'true' : null,
    title: item.locked ? item.why || t('ct.locked') : null,
    'aria-haspopup': item.shop ? 'dialog' : null,
    onclick: () => {
      if (item.locked) showWhy(item.why || t('ct.locked'));
      else if (item.shop) store.update({ panel: 'shop' });
      else store.emit('compose', { text: item.text });
    },
  };
  const icon = h('img', { class: 'ct-chip-icon', src: assetUrl(`ui_icon.act-${item.kind}`), alt: '', width: 20, height: 20 });
  return h('button', props, icon, h('span', {}, item.label), item.locked ? h('span', { class: 'ct-chip-lock' }, t('ct.lockedShort')) : null);
}

export function mountIdeas(root, { store }) {
  const box = h('section', { class: 'ct-ideas', 'aria-label': t('ct.ideas'), 'data-testid': 'ideas' });
  const why = h('p', { class: 'ct-locked-why', role: 'status', hidden: true, 'data-testid': 'locked-why' });
  root.append(box);
  let last = '';
  const showWhy = (text) => {
    why.textContent = text;
    why.hidden = false;
  };

  function render(state) {
    const scene = publicState(state)?.scene ?? null;
    const shown = !combatOf(state) && blockedReason(state) === null;
    box.hidden = !shown;
    const groups = shown ? ideaGroups(scene) : [];
    const key = JSON.stringify(groups);
    if (key === last) return;
    last = key;
    clear(box);
    why.hidden = true;
    for (const { group, chips } of groups) {
      box.append(h('div', { class: 'ct-idea-group', 'data-group': group }, h('h3', { class: 'ct-idea-h' }, t(`ct.idea_${group}`)), h('div', { class: 'ct-chips' }, ...chips.map((c) => chip(c, store, showWhy)))));
      if (group === 'ways') box.append(why);
    }
  }
  render(store.get());
  return store.subscribe(render);
}
