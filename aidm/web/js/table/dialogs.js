// Table dialogs (native <dialog>, focus trapped by the browser): the point-of-no-return confirmation,
// the encounter offer (fight / surprise / escape / parley) and the minimal level-up notice.
import { mySeat } from '../state.js';
import { t } from '../strings.js';
import { clear, h } from '../ui/dom.js';
import { titleCase } from '../ui/format.js';
import { myHero, publicState } from './lookup.js';

function openDialog(dialog) {
  if (dialog.open) return;
  if (typeof dialog.showModal === 'function') dialog.showModal();
  else dialog.setAttribute('open', '');
}

function closeDialog(dialog) {
  if (!dialog.open) return;
  if (typeof dialog.close === 'function') dialog.close();
  else dialog.removeAttribute('open');
}

export function mountConfirm(root, { store, client }) {
  const text = h('p', { class: 'dialog-text', 'data-testid': 'confirm-text' });
  const dialog = h('dialog', { class: 'dialog', 'aria-labelledby': 'confirm-h', 'data-testid': 'confirm-dialog' });
  const answer = (type) => {
    store.update({ confirm: null });
    client.send(type);
  };
  dialog.append(
    h('h2', { id: 'confirm-h' }, t('table.confirmTitle')),
    text,
    h(
      'div',
      { class: 'dialog-actions' },
      h('button', { type: 'button', class: 'btn btn-primary', 'data-testid': 'confirm-yes', onclick: () => answer('confirm_hostile') }, t('table.confirmYes')),
      h('button', { type: 'button', class: 'btn', 'data-testid': 'confirm-no', onclick: () => answer('cancel_hostile') }, t('table.confirmNo')),
    ),
  );
  dialog.addEventListener('cancel', (event) => {
    event.preventDefault();
    answer('cancel_hostile');
  });
  root.append(dialog);

  function render(state) {
    const pending = state.confirm;
    if (pending && pending.playerId === state.me.playerId) {
      text.textContent = pending.prompt;
      openDialog(dialog);
    } else closeDialog(dialog);
  }
  render(store.get());
  return store.subscribe(render);
}

export function mountOffer(root, { store, client }) {
  const body = h('div', { class: 'dialog-body' });
  const dialog = h('dialog', { class: 'dialog', 'aria-labelledby': 'offer-h', 'data-testid': 'offer-dialog' }, h('h2', { id: 'offer-h' }, t('table.offerTitle')), body);
  dialog.addEventListener('cancel', (event) => event.preventDefault());
  root.append(dialog);
  let shownId = null;

  function build(offer) {
    clear(body);
    const foes = [...offer.foes, offer.boss_name].filter(Boolean);
    body.append(
      h('p', { class: 'dialog-text' }, t('table.offerText')),
      h('ul', { class: 'foes' }, ...foes.map((name) => h('li', {}, name))),
      offer.difficulty ? h('p', { class: 'hint' }, t('table.offerDifficulty', { level: titleCase(offer.difficulty) })) : null,
      h(
        'div',
        { class: 'dialog-actions' },
        ...offer.options.map((choice) => {
          const button = h('button', { type: 'button', class: choice === 'fight' ? 'btn btn-primary' : 'btn', 'data-testid': `offer-${choice}` }, t(`table.offer_${choice}`));
          button.addEventListener('click', () => {
            body.querySelectorAll('button').forEach((b) => (b.disabled = true));
            client.send('answer_offer', { choice });
          });
          return button;
        }),
      ),
    );
  }

  function render(state) {
    const offer = publicState(state)?.offer ?? null;
    const mine = Boolean(mySeat(state)?.creature_id);
    if (!offer || !mine) {
      shownId = null;
      closeDialog(dialog);
      return;
    }
    if (shownId !== offer.id) {
      shownId = offer.id;
      build(offer);
    }
    openDialog(dialog);
  }
  render(store.get());
  return store.subscribe(render);
}

/** A badge button while your hero can level up; it opens a short notice (the sheet arrives in M7.5). */
export function mountLevelUp(root, { store }) {
  const dialog = h(
    'dialog',
    { class: 'dialog', 'aria-labelledby': 'levelup-h', 'data-testid': 'levelup-dialog' },
    h('h2', { id: 'levelup-h' }, t('table.levelUpTitle')),
    h('p', { class: 'dialog-text' }, t('table.levelUpText')),
    h('div', { class: 'dialog-actions' }, h('button', { type: 'button', class: 'btn', onclick: () => closeDialog(dialog) }, t('table.close'))),
  );
  const button = h('button', { type: 'button', class: 'btn btn-small levelup-btn', hidden: true, 'data-testid': 'levelup-button', onclick: () => openDialog(dialog) }, t('table.levelUp'));
  root.append(button, dialog);

  function render(state) {
    const hero = myHero(state);
    const offered = hero ? state.levelUps[hero.id] : 0;
    button.hidden = !(hero && offered && (hero.level ?? 1) < offered);
  }
  render(store.get());
  return store.subscribe(render);
}
