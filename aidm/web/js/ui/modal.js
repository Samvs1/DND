// A table panel: a native modal <dialog> (focus trap, Escape, focus returns to the opener) that is open while
// `store.panel === key`. `sync(state)` opens or closes the dialog and returns true while it is open.
import { t } from '../strings.js';
import { h } from './dom.js';

export function createPanel(root, store, { key, title, testid }) {
  const heading = h('h2', { id: `panel-${key}-h` }, title);
  const close = h('button', { type: 'button', class: 'btn btn-small pn-close', 'data-testid': `${testid}-close` }, t('tools.close'));
  const body = h('div', { class: 'pn-body' });
  const dialog = h('dialog', { class: 'panel-dialog', 'aria-labelledby': `panel-${key}-h`, 'data-testid': testid }, close, heading, body);
  root.append(dialog);
  close.addEventListener('click', () => dialog.close());
  dialog.addEventListener('close', () => {
    if (store.get().panel === key) store.update({ panel: null });
  });

  function sync(state) {
    const wanted = state.panel === key;
    if (!wanted) {
      if (dialog.open) dialog.close();
      return false;
    }
    if (!dialog.open) {
      if (typeof dialog.showModal === 'function') dialog.showModal();
      else dialog.setAttribute('open', '');
    }
    return true;
  }
  return { dialog, body, sync, remove: () => dialog.remove() };
}
