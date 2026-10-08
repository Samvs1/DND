// Entry point: picks the mode from the URL path (/screen = spectator, else player), wires the
// store, websocket client, handler registry, banner and the active view.
import { loadAssets } from './assets.js';
import { bindRemoteAudio } from './audio/remote.js';
import { createMusic } from './audio/music.js';
import { createNarrationAudio } from './audio/narration.js';
import { createDispatch } from './handlers.js';
import { loadSettings } from './settings/model.js';
import { createStore, saved } from './state.js';
import { createStory } from './story.js';
import { t } from './strings.js';
import { mountBanner } from './ui/banner.js';
import { clear } from './ui/dom.js';
import { VIEWS, pickView } from './views/index.js';
import { createClient } from './ws.js';

const mode = window.location.pathname.startsWith('/screen') ? 'screen' : 'play';
document.body.dataset.mode = mode;

loadSettings(saved);
const skip = document.createElement('a');
skip.className = 'skip-link';
skip.href = '#app';
skip.textContent = t('a11y.skip');
document.body.prepend(skip);
const store = createStore();
const dispatch = createDispatch({ store, saved });
const client = createClient({ store, saved, dispatch, spectator: mode === 'screen' });
const story = createStory(store);
const makeAudio = (url) => (window.__aidmMakeAudio ? window.__aidmMakeAudio(url) : new Audio(url));
const audio = createNarrationAudio({ store, mode, makeAudio });
const ctx = { store, saved, client, mode, story, audio };

mountBanner(document.getElementById('banner'), store, {
  retry: () => client.retry(),
  dismissFallback: () => store.update({ fallback: false }),
  dismissError: () => store.update({ errorCode: null }),
  enableAudio: () => audio.unlock(),
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
bindRemoteAudio({ store, saved, mode });
const music = createMusic({ store, mode, makeAudio });
store.subscribe(show);
show(store.get());

const name = saved.name();
if (mode === 'screen') client.connect(t('screen.name'));
else if (name && saved.token()) client.connect(name);
window.aidm = { store, client, dispatch, audio, music, story }; // handles for tests and the console
