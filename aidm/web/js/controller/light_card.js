// The light and gear part of the Now card (M27.8): "It is dark here." in a dark place, the "Torch lit" chip and the
// free **Put out light** button for the bearer, the chips of the gear boons I carry, and the last light line
// (the warning that a light shows you to anything waiting, a put-out, a fight start that a light gave away) so the
// phone says it too, not only the screen.
import { myHero, publicState } from '../table/lookup.js';
import { lightChip, putOutButton } from '../table/light.js';
import { t } from '../strings.js';
import { h } from '../ui/dom.js';
import { tipButton } from '../ui/tip.js';

const NOTE_KINDS = new Set(['light_lit', 'light_ended', 'encounter_started', 'place_alerted']);
const NOTE_MS = 15000;

export function mountLightCard(root, { store, story, client }) {
  const dark = h('p', { class: 'ct-now-dark', hidden: true, 'data-testid': 'now-dark' }, t('light.darkHere'));
  const gear = h('div', { class: 'ct-now-gear', hidden: true, 'data-testid': 'now-gear' });
  const note = h('p', { class: 'ct-now-note', hidden: true, role: 'status', 'data-testid': 'light-note' });
  const darkTip = tipButton('word:dark', t('light.darkHere'));
  const litTip = tipButton('word:lit', t('light.darkHere'));
  const darkRow = h('div', { class: 'ct-now-darkrow', hidden: true }, dark, darkTip, litTip);
  const noteRow = h('div', { class: 'ct-now-noterow', hidden: true }, note, tipButton('word:light-note', t('light.noteTitle')));
  root.append(darkRow, gear, noteRow);
  let last = '';
  let timer = null;

  function render(state) {
    const view = publicState(state);
    const hero = myHero(state);
    const lit = view?.scene?.lit;
    dark.textContent = lit ? t('light.litHere', { name: lit.toLowerCase() }) : t('light.darkHere');
    dark.hidden = !(view?.scene?.dark && !view.combat);
    darkRow.hidden = dark.hidden;
    darkTip.style.display = lit ? 'none' : '';
    litTip.style.display = lit ? '' : 'none';
    const key = JSON.stringify([hero?.light, hero?.boons]);
    if (key === last) return;
    last = key;
    gear.replaceChildren(
      ...(hero?.light ? [lightChip(hero), tipButton('word:lit', t('light.litChip', { name: hero.light })), putOutButton(client)] : []),
      ...(hero?.boons ?? []).map((b) => [h('span', { class: 'boon-chip', 'data-testid': 'boon-chip', title: t('light.boons') }, b.helps.length ? t('light.boonChip', { name: b.name, helps: b.helps.join(', ') }) : t('light.boonChipPlain', { name: b.name })), tipButton('word:boon', b.name)]).flat(),
    );
    gear.hidden = !gear.childElementCount;
  }
  const stop = story.subscribe((change) => {
    const item = change.item;
    if (change.type !== 'item' || item?.kind !== 'event' || !NOTE_KINDS.has(item.eventKind)) return;
    if (item.eventKind === 'encounter_started' && !/dark|light/i.test(item.text)) return;
    note.textContent = item.text;
    note.hidden = false;
    noteRow.hidden = false;
    clearTimeout(timer);
    timer = setTimeout(() => {
      note.hidden = true;
      noteRow.hidden = true;
    }, NOTE_MS);
  });
  render(store.get());
  const stopStore = store.subscribe(render);
  return () => {
    stop();
    stopStore();
    clearTimeout(timer);
  };
}
