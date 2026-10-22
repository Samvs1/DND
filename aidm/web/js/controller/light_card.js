// The light and gear part of the Now card (M27.8): "It is dark here." in a dark place, the "Torch lit" chip and the
// free **Put out light** button for the bearer, the chips of the gear boons I carry, and the last light line
// (the warning that a light shows you to anything waiting, a put-out, a fight start that a light gave away) so the
// phone says it too, not only the screen.
import { myHero, publicState } from '../table/lookup.js';
import { lightChip, putOutButton } from '../table/light.js';
import { t } from '../strings.js';
import { h } from '../ui/dom.js';

const NOTE_KINDS = new Set(['light_lit', 'light_ended', 'encounter_started']);
const NOTE_MS = 15000;

export function mountLightCard(root, { store, story, client }) {
  const dark = h('p', { class: 'ct-now-dark', hidden: true, 'data-testid': 'now-dark' }, t('light.darkHere'));
  const gear = h('div', { class: 'ct-now-gear', hidden: true, 'data-testid': 'now-gear' });
  const note = h('p', { class: 'ct-now-note', hidden: true, role: 'status', 'data-testid': 'light-note' });
  root.append(dark, gear, note);
  let last = '';
  let timer = null;

  function render(state) {
    const view = publicState(state);
    const hero = myHero(state);
    dark.hidden = !(view?.scene?.dark && !view.combat);
    const key = JSON.stringify([hero?.light, hero?.boons]);
    if (key === last) return;
    last = key;
    gear.replaceChildren(
      ...(hero?.light ? [lightChip(hero), putOutButton(client)] : []),
      ...(hero?.boons ?? []).map((b) => h('span', { class: 'boon-chip', 'data-testid': 'boon-chip', title: t('light.boons') }, b.helps.length ? t('light.boonChip', { name: b.name, helps: b.helps.join(', ') }) : t('light.boonChipPlain', { name: b.name }))),
    );
    gear.hidden = !gear.childElementCount;
  }
  const stop = story.subscribe((change) => {
    const item = change.item;
    if (change.type !== 'item' || item?.kind !== 'event' || !NOTE_KINDS.has(item.eventKind)) return;
    if (item.eventKind === 'encounter_started' && !/dark|light/i.test(item.text)) return;
    note.textContent = item.text;
    note.hidden = false;
    clearTimeout(timer);
    timer = setTimeout(() => (note.hidden = true), NOTE_MS);
  });
  render(store.get());
  const stopStore = store.subscribe(render);
  return () => {
    stop();
    stopStore();
    clearTimeout(timer);
  };
}
