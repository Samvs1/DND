// Notices: the table's short in-fiction messages (progress, info, host) shown as a toast for a few
// seconds. Refused actions show under the action box instead; the fallback banner is in the page banner.
import { t } from '../strings.js';
import { clear, h } from '../ui/dom.js';

const SHOW_MS = 8000;

export function mountNotices(root, store) {
  const box = h('div', { class: 'notices', role: 'status', 'aria-live': 'polite', 'data-testid': 'notices' });
  root.append(box);
  let last = store.get().notices.at(-1) ?? null;
  let timer = null;

  function show(notice) {
    clear(box);
    box.append(
      h(
        'div',
        { class: `notice notice-${notice.kind || 'info'}`, 'data-testid': 'notice' },
        h('span', {}, notice.text),
        h('button', { type: 'button', class: 'btn btn-small', onclick: () => clear(box) }, t('banner.dismiss')),
      ),
    );
    clearTimeout(timer);
    timer = setTimeout(() => clear(box), SHOW_MS);
  }

  const stop = store.subscribe((state) => {
    const latest = state.notices.at(-1) ?? null;
    if (latest && latest !== last && latest.kind !== 'refused') show(latest);
    last = latest;
  });
  return () => {
    stop();
    clearTimeout(timer);
  };
}
