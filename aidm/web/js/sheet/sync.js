// Keeps the local hero's sheet fresh: asks the server for it whenever a new snapshot arrives (and on mount),
// at most a few times a second. The combat hotbar and the sheet drawer both read `store.sheet`.
import { hasHero } from '../state.js';

const DELAY_MS = 150;

export function mountSheetSync({ store, client }) {
  let lastSeq = -1;
  let timer = null;

  function ask() {
    timer = null;
    client.send('request_sheet');
  }

  function check(state) {
    if (!state.snapshot || state.phase !== 'play' || !hasHero(state)) return;
    if (state.lastSeq === lastSeq || timer) return;
    lastSeq = state.lastSeq;
    timer = setTimeout(ask, DELAY_MS);
  }
  check(store.get());
  const stop = store.subscribe(check);
  return () => {
    stop();
    clearTimeout(timer);
  };
}
