// The story box of the Play tab: the recent story in full, newest at the bottom, scrolling inside itself.
import { t } from '../strings.js';
import { clear, h } from '../ui/dom.js';

const SHOWN = 8;
const NEAR_END = 40;

export function itemText(item) {
  if (item.kind === 'narration') return item.sentences.map((s) => s.text).join(' ').trim();
  return (item.text ?? '').trim();
}

export function mountLastLine(root, { story }) {
  const box = h('div', { class: 'ct-last', role: 'log', tabindex: '0', 'aria-label': t('ct.lastLine'), 'data-testid': 'last-line' });
  root.append(box);
  let pinned = true; // follow the newest line unless the player scrolled up

  function render() {
    const texts = story.items.map(itemText).filter(Boolean).slice(-SHOWN);
    clear(box);
    box.append(...(texts.length ? texts : [t('ct.lastEmpty')]).map((text) => h('p', {}, text)));
    if (pinned) box.scrollTop = box.scrollHeight;
  }
  box.addEventListener('scroll', () => {
    pinned = box.scrollHeight - box.scrollTop - box.clientHeight < NEAR_END;
  });
  render();
  return story.subscribe(render);
}
