// The phone's full-screen manual panel (opened from the More tab). The view is built on first open.
import { t } from '../strings.js';
import { createPanel } from '../ui/modal.js';
import { createManualView } from './view.js';
import { fetchManual } from './source.js';

export function mountManualPanel(root, { store }) {
  const panel = createPanel(root, store, { key: 'manual', title: t('manual.title'), testid: 'manual-panel' });
  panel.dialog.classList.add('manual-dialog');
  let stopView = null;
  const sync = (state) => {
    if (panel.sync(state) && !stopView) stopView = createManualView(panel.body, { load: fetchManual });
  };
  sync(store.get());
  const stop = store.subscribe(sync);
  return () => {
    stop();
    if (stopView) stopView();
    panel.remove();
  };
}
