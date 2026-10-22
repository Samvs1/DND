// The finale card (M23.9): once the last region is resolved the party chooses how the story ends. The card shows the
// plan's question and its two endings as buttons; pressing one asks "Are you sure? This ends the story." with Yes /
// Back, and only Yes sends `choose_finale {option_id, confirm: true}`. Like the quest offer card it is NOT modal: it
// sits in the sticky sheet slot (the party may still wander, rest and talk), comes from the snapshot (`finale`, so a
// reconnecting phone shows it again), shows in full on the Play tab only, with a slim strip on the other tabs, and
// hides while an encounter offer or a fight is on. Once an ending is chosen (`finale.chosen`) the card is gone.
import { mySeat } from '../state.js';
import { t } from '../strings.js';
import { clear, h } from '../ui/dom.js';
import { tipButton } from '../ui/tip.js';
import { publicState } from './lookup.js';

export function mountFinale(root, { store, client }) {
  const box = h('section', { class: 'panel quest-card finale-card', hidden: true, 'aria-live': 'polite', 'data-testid': 'finale-card' });
  const strip = h('div', { class: 'quest-strip', hidden: true, 'data-testid': 'finale-strip' });
  root.append(box, strip);
  let shownKey = null;

  function choices(finale) {
    clear(box);
    box.append(
      h('h3', {}, t('table.finaleTitle'), tipButton('word:finale', t('table.finaleTitle'))),
      h('p', { class: 'dialog-text', 'data-testid': 'finale-question' }, finale.question),
      h(
        'div',
        { class: 'finale-options' },
        ...finale.options.map((option) =>
          h('button', { type: 'button', class: 'btn btn-primary', 'data-testid': 'finale-option', 'data-option': option.id, onclick: () => sure(finale, option) }, option.title),
        ),
      ),
      h('p', { class: 'hint quest-hint' }, t('table.finaleHint')),
    );
  }

  function sure(finale, option) {
    clear(box);
    const yes = () => {
      box.querySelectorAll('button').forEach((b) => (b.disabled = true));
      client.send('choose_finale', { option_id: option.id, confirm: true });
    };
    box.append(
      h('h3', {}, t('table.finaleSure')),
      h('p', { class: 'dialog-text', 'data-testid': 'finale-picked' }, t('table.finalePicked', { title: option.title })),
      h(
        'div',
        { class: 'dialog-actions' },
        h('button', { type: 'button', class: 'btn btn-primary', 'data-testid': 'finale-confirm', onclick: yes }, t('table.finaleYes')),
        h('button', { type: 'button', class: 'btn', 'data-testid': 'finale-back', onclick: () => choices(finale) }, t('table.finaleBack')),
      ),
    );
  }

  function render(state) {
    const view = publicState(state);
    const finale = view?.finale ?? null;
    const mine = Boolean(mySeat(state)?.creature_id);
    const blocked = Boolean(view?.offer) || Boolean(view?.combat) || state.snapshot?.state.phase === 'defeated';
    if (!finale || finale.chosen || !mine || blocked) {
      shownKey = null;
      box.hidden = true;
      strip.hidden = true;
      return;
    }
    const key = finale.question;
    if (shownKey !== key) {
      shownKey = key;
      choices(finale);
    }
    const onPlay = (state.ctab ?? 'play') === 'play';
    box.hidden = !onPlay;
    strip.hidden = onPlay;
    if (!onPlay) {
      clear(strip);
      strip.append(
        h('span', { class: 'quest-strip-text' }, t('table.finaleStrip')),
        h('button', { type: 'button', class: 'btn btn-small', 'data-testid': 'finale-answer', onclick: () => store.update({ ctab: 'play' }) }, t('table.finaleStripAnswer')),
      );
    }
  }
  render(store.get());
  return store.subscribe(render);
}
