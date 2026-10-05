// An inline two-step confirmation for destructive host actions: the first click swaps the button for a question
// with Yes and Cancel (no browser dialog, so it can be tested and styled).
import { t } from '../strings.js';
import { h } from '../ui/dom.js';

/** confirmButton({ label, ask, yes, testid, onYes, small }) -> an element that holds the button and the question. */
export function confirmButton({ label, ask, yes, testid, onYes, small = false, disabled = false }) {
  const box = h('span', { class: 'hc-confirm' });
  const show = (asking) => {
    box.replaceChildren();
    if (!asking) {
      box.append(h('button', { type: 'button', class: `btn${small ? ' btn-small' : ''}`, disabled, 'data-testid': testid, onclick: () => show(true) }, label));
      return;
    }
    const yesButton = h('button', { type: 'button', class: 'btn btn-small btn-danger', 'data-testid': `${testid}-yes`, onclick: () => { show(false); onYes(); } }, yes);
    box.append(
      h('span', { class: 'hc-ask', role: 'alert' }, ask),
      yesButton,
      h('button', { type: 'button', class: 'btn btn-small', 'data-testid': `${testid}-no`, onclick: () => show(false) }, t('host.cancel')),
    );
    yesButton.focus();
  };
  show(false);
  return box;
}
