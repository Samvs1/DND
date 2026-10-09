// The Scribe on /screen: a card with his portrait, name and subtitle for every line he speaks. The clip plays
// on the narrator channel (voice.js); narration holds meanwhile. It hides when the clip ends, after a reading
// time without audio, or on `scribe_skip`.
import { portraitSrc } from '../scribe/portrait.js';
import { t } from '../strings.js';
import { h } from '../ui/dom.js';

export function mountScribeOverlay(root, { store }) {
  const portrait = h('img', { class: 'sc-scribe-portrait', src: portraitSrc('seated'), alt: t('scribe.portraitAlt'), 'data-testid': 'screen-scribe-portrait' });
  const text = h('p', { class: 'sc-scribe-text', 'data-testid': 'screen-scribe-text' });
  const card = h('div', { class: 'sc-scribe', hidden: true, role: 'status', 'data-testid': 'screen-scribe' }, portrait, h('div', { class: 'sc-scribe-body' }, h('h2', {}, t('scribe.name')), text));
  root.append(card);
  let shownId = null;
  const render = (state) => {
    const line = state.scribeLine;
    card.hidden = !line;
    if (!line) return void (shownId = null);
    if (shownId === line.line_id) return;
    shownId = line.line_id;
    portrait.src = portraitSrc(line.group);
    text.textContent = line.text;
    card.dataset.group = line.group;
  };
  render(store.get());
  const stop = store.subscribe(render);
  return stop;
}
