// The item card's gear Use (M27.8, docs/next/GOAL_ITEMS.md "What players see"): one **Use** button per use of the
// item outside a fight (`item.uses`, from data/bg3/item_uses.json), saying what it does here ("Light this dark
// place") and why it is off when it is ("Only works in a dark place."). A use aimed at a locked thing here gets a
// picker of the locked features. It sends the menu's own label (M36.10b: `Light the torch`, `Force this open with
// the crowbar Cellar door`; MenuAct in M36.11), so the engine, not the button, decides. In a fight gear goes
// through the hotbar.
import { t } from '../strings.js';
import { h } from '../ui/dom.js';

function reason(use, { scene, light, locked, blocked }, locks) {
  if (locked) return t('light.useFight');
  if (blocked) return t('light.useBlocked');
  if (use.when === 'dark_place' && !scene?.dark) return t('light.useNeedsDark');
  if (use.when === 'dark_place' && light) return t('light.useHasLight');
  if (use.when === 'locked' && !locks.length) return t('light.useNeedsLock');
  return '';
}

function here(use) {
  return use.when === 'dark_place' ? t('light.useDark') : use.label;
}

export function useControls(item, opts) {
  const locks = (opts.scene?.features ?? []).filter((f) => f.locked);
  return (item.uses ?? []).map((use) => {
    const why = reason(use, opts, locks);
    const pick = use.when === 'locked' ? h('select', { class: 'inv-target', disabled: Boolean(why), 'data-testid': `use-here-target-${use.use_id}`, 'aria-label': t('light.useTarget') }, ...locks.map((f) => h('option', { value: f.name }, f.name))) : null;
    const text = () => (pick ? `${use.label} ${pick.value}` : use.label);
    const button = h('button', { type: 'button', class: 'btn btn-small', disabled: Boolean(why), title: why || here(use), 'data-testid': `use-here-${use.use_id}`, onclick: () => opts.client.send('submit_action', { text: text() }) }, t('light.use'));
    return h('div', { class: 'inv-use', 'data-testid': 'inv-use' }, h('span', { class: 'hint inv-use-what' }, why || here(use)), pick, button);
  });
}
