// The Scribe speaking on a phone: a compact banner with his subtitle while a shared line plays (the phone's
// own sound decides whether the clip is heard). The host gets Skip on the long speeches.
import { t } from '../strings.js';
import { h } from '../ui/dom.js';

const LONG_GROUPS = new Set(['welcome_first', 'welcome_return', 'victory_campaign']);

export function mountScribeBanner(root, { store, client }) {
  const text = h('p', { class: 'sc-banner-text', 'data-testid': 'scribe-banner-text' });
  const skip = h('button', { type: 'button', class: 'btn btn-small', hidden: true, 'data-testid': 'scribe-skip', onclick: () => client.send('scribe_skip', { line_id: store.get().scribeLine?.line_id ?? null }) }, t('scribe.skip'));
  const box = h('section', { class: 'sc-banner', hidden: true, role: 'status', 'aria-label': t('scribe.speaks'), 'data-testid': 'controller-scribe-line' }, h('strong', {}, t('scribe.speaks')), text, skip);
  root.append(box);
  const render = (state) => {
    const line = state.scribeLine;
    box.hidden = !line;
    if (!line) return;
    text.textContent = line.text;
    skip.hidden = !(state.me.isHost && LONG_GROUPS.has(line.group));
  };
  render(store.get());
  const stop = store.subscribe(render);
  return stop;
}
