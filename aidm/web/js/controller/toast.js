// A small toast for MY dice results (the big dice are on the shared screen).
import { myCreatureId } from '../combat/model.js';
import { t } from '../strings.js';
import { clear, h } from '../ui/dom.js';
import { rollNodes } from './lastroll.js';

const SHOW_MS = 5000;

export function mountToast(root, { store, story }) {
  const box = h('div', { class: 'ct-toast', hidden: true, role: 'status', 'aria-live': 'polite', 'data-testid': 'dice-toast' });
  root.append(box);
  let timer = null;
  const stop = story.subscribe((change) => {
    if (change.type !== 'dice') return;
    const roll = change.roll;
    const me = myCreatureId(store.get());
    if (!me || roll.roller_id !== me) return;
    clear(box);
    box.append(...rollNodes(roll));
    box.setAttribute('aria-label', t('ct.rollToast', { label: roll.label || roll.expression, total: roll.total }));
    box.hidden = false;
    clearTimeout(timer);
    timer = setTimeout(() => (box.hidden = true), SHOW_MS);
  });
  return () => {
    stop();
    clearTimeout(timer);
  };
}
