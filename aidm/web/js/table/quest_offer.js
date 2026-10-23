// The quest offer card (M23.4): a giver asks, "<giver> asks: <title>", the objective and Accept / Not now.
// Built from the encounter offer card's parts (dialog-text, dialog-actions, buttons) but NOT modal: it sits
// in the sticky sheet slot like an open vote, so the hero can keep acting (a typed action does not answer it).
// It comes from the snapshot (`quest_offer`), so a reconnecting phone shows it again; it hides while an
// encounter offer or a fight is on. Only the Play tab shows the full card; on the other tabs a slim one-line
// strip (with an Answer button that jumps to Play) keeps it from covering the Hero and Journal content.
import { mySeat } from '../state.js';
import { t } from '../strings.js';
import { clear, h } from '../ui/dom.js';
import { tipButton } from '../ui/tip.js';
import { publicState } from './lookup.js';

export function mountQuestOffer(root, { store, client }) {
  const box = h('section', { class: 'panel quest-card', hidden: true, 'aria-live': 'polite', 'data-testid': 'quest-offer' });
  const strip = h('div', { class: 'quest-strip', hidden: true, 'data-testid': 'quest-offer-strip' });
  root.append(box, strip);
  let shownId = null;

  function build(offer) {
    clear(box);
    const answer = (accept) => {
      box.querySelectorAll('button').forEach((b) => (b.disabled = true));
      client.send('answer_quest_offer', { quest_id: offer.quest_id, accept });
    };
    box.append(
      h('h3', { class: 'qo-head', 'data-testid': 'quest-offer-title' }, h('span', { class: 'qo-text' }, t('table.questOfferTitle', { giver: offer.giver, title: offer.title })), tipButton('word:quest-offer', offer.title)),
      offer.objective ? h('p', { class: 'dialog-text', 'data-testid': 'quest-offer-objective' }, offer.objective) : null,
      h('p', { class: 'hint quest-hint' }, t('table.questOfferHint')),
      h(
        'div',
        { class: 'dialog-actions' },
        h('button', { type: 'button', class: 'btn btn-primary', 'data-testid': 'quest-offer-accept', onclick: () => answer(true) }, t('table.questOfferAccept')),
        h('button', { type: 'button', class: 'btn', 'data-testid': 'quest-offer-later', onclick: () => answer(false) }, t('table.questOfferLater')),
      ),
    );
  }

  function render(state) {
    const view = publicState(state);
    const offer = view?.quest_offer ?? null;
    const mine = Boolean(mySeat(state)?.creature_id);
    const blocked = Boolean(view?.offer) || Boolean(view?.combat) || state.snapshot?.state.phase === 'defeated';
    if (!offer || !mine || blocked) {
      shownId = null;
      box.hidden = true;
      strip.hidden = true;
      return;
    }
    if (shownId !== offer.quest_id) {
      shownId = offer.quest_id;
      build(offer);
    }
    const onPlay = (state.ctab ?? 'play') === 'play';
    box.hidden = !onPlay;
    strip.hidden = onPlay;
    if (!onPlay) {
      clear(strip);
      strip.append(
        h('span', { class: 'quest-strip-text' }, t('table.questStrip', { giver: offer.giver, title: offer.title })),
        h('button', { type: 'button', class: 'btn btn-small', 'data-testid': 'quest-offer-answer', onclick: () => store.update({ ctab: 'play' }) }, t('table.questStripAnswer')),
      );
    }
  }
  render(store.get());
  return store.subscribe(render);
}
