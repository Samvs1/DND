// Banner at the top of the page: connection loss, the storyteller fallback and friendly errors.
// It never shows raw server text; it maps codes to strings and offers a retry.
import { t } from '../strings.js';
import { clear, h } from './dom.js';

function bannerFor(state) {
  if (state.conn === 'down') return { text: t('conn.down'), retry: t('conn.retry'), action: 'retry' };
  if (state.fallback) return { text: t('banner.fallback'), retry: t('banner.dismiss'), action: 'dismissFallback' };
  if (state.errorCode) {
    const text = t(`errors.${state.errorCode}`);
    const known = text !== `errors.${state.errorCode}`;
    return { text: known ? text : t('errors.generic'), retry: t('banner.dismiss'), action: 'dismissError' };
  }
  if (state.audioBlocked) return { text: t('banner.audioBlocked'), retry: t('banner.audioEnable'), action: 'enableAudio' };
  return null;
}

export function mountBanner(root, store, actions) {
  function render(state) {
    clear(root);
    const banner = bannerFor(state);
    if (!banner) return;
    root.append(
      h('div', { class: 'banner', 'data-testid': 'banner' },
        h('span', {}, banner.text),
        h('button', { type: 'button', class: 'btn btn-small', onclick: () => actions[banner.action]() }, banner.retry)),
    );
  }
  render(store.get());
  return store.subscribe(render);
}
