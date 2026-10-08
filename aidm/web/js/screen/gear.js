// A small audio gear on the screen: opens the settings panel (local volume and mute, kept in localStorage).
import { t } from '../strings.js';
import { h } from '../ui/dom.js';

export function mountGear(root, store) {
  const button = h(
    'button',
    { type: 'button', class: 'btn btn-small sc-gear', 'data-testid': 'screen-gear', 'aria-label': t('screen.gear'), title: t('screen.gear'), onclick: () => store.update({ panel: 'settings' }) },
    t('screen.gearIcon'),
  );
  root.append(button);
  return () => button.remove();
}
