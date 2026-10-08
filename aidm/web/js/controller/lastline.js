// The one-line "last narration" of the Play tab. Tapping it opens a short modal with the last few story lines.
import { t } from '../strings.js';
import { clear, h } from '../ui/dom.js';

const SHOWN = 6;
const CUT = 150;

export function itemText(item) {
  if (item.kind === 'narration') return item.sentences.map((s) => s.text).join(' ').trim();
  return (item.text ?? '').trim();
}

export function mountLastLine(root, { story }) {
  const line = h('button', { type: 'button', class: 'ct-last', 'aria-haspopup': 'dialog', 'data-testid': 'last-line' });
  const list = h('div', { class: 'ct-recent', 'data-testid': 'recent-lines' });
  const close = h('button', { type: 'button', class: 'btn btn-small', 'data-testid': 'recent-close' }, t('ct.close'));
  const dialog = h('dialog', { class: 'dialog', 'aria-labelledby': 'ct-recent-h', 'data-testid': 'recent-dialog' }, h('h2', { id: 'ct-recent-h' }, t('ct.recentTitle')), list, h('div', { class: 'dialog-actions' }, close));
  root.append(line, dialog);
  const texts = () => story.items.map(itemText).filter(Boolean);

  function render() {
    const last = texts().at(-1) ?? t('ct.lastEmpty');
    line.textContent = last.length > CUT ? `${last.slice(0, CUT - 1)}...` : last;
    line.setAttribute('aria-label', t('ct.lastLine'));
  }
  line.addEventListener('click', () => {
    clear(list);
    list.append(...texts().slice(-SHOWN).map((text) => h('p', {}, text)));
    if (typeof dialog.showModal === 'function') dialog.showModal();
    else dialog.setAttribute('open', '');
  });
  close.addEventListener('click', () => dialog.close());
  render();
  return story.subscribe(render);
}
