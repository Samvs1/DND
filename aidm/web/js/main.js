// Entry point: picks the mode from the URL path (/screen = spectator, else player), wires the
// store, websocket client, handler registry, banner and the active view.
import { loadAssets } from './assets.js';
import { createDispatch } from './handlers.js';
import { createStore, saved } from './state.js';
import { mountBanner } from './ui/banner.js';
import { clear } from './ui/dom.js';
import { VIEWS, pickView } from './views/index.js';
import { createClient } from './ws.js';

const mode = window.location.pathname.startsWith('/screen') ? 'screen' : 'play';
document.body.dataset.mode = mode;

const store = createStore();
const dispatch = createDispatch({ store, saved });
const client = createClient({ store, saved, dispatch });
const ctx = { store, saved, client, mode };

mountBanner(document.getElementById('banner'), store, {
  retry: () => client.retry(),
  dismissFallback: () => store.update({ fallback: false }),
  dismissError: () => store.update({ errorCode: null }),
});

const app = document.getElementById('app');
let current = null;
let unmount = null;

function show(state) {
  const key = pickView(state, mode);
  if (key === current) return;
  if (unmount) unmount();
  clear(app);
  current = key;
  unmount = VIEWS[key](app, ctx);
}

await loadAssets();
store.subscribe(show);
show(store.get());

const name = saved.name();
if (mode === 'play' && name && saved.token()) client.connect(name);
window.aidm = { store, client };
