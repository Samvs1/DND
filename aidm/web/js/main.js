// Entry point: picks the mode from the URL path (/screen = spectator, else player), wires the
// store, websocket client, handler registry, banner and the active view.
import { loadAssets } from './assets.js';
import { bindRemoteAudio } from './audio/remote.js';
import { createMusic } from './audio/music.js';
import { createNarrationAudio } from './audio/narration.js';
import { createSfx } from './audio/sfx.js';
import { createDispatch } from './handlers.js';
import { mountSoundGate } from './screen/sound_gate.js';
import { createScribeVoice } from './scribe/voice.js';
import { loadSettings } from './settings/model.js';
import { bindTips } from './ui/tip.js';
import { createPacer } from './show/pacer.js';
import { createStore, saved } from './state.js';
import { createStory } from './story.js';
import { t } from './strings.js';
import { mountBanner } from './ui/banner.js';
import { clear } from './ui/dom.js';
import { fitViewport } from './ui/fit.js';
import { applySkin } from './ui/skin.js';
import { VIEWS, pickView } from './views/index.js';
import { createClient } from './ws.js';

const mode = window.location.pathname.startsWith('/screen') ? 'screen' : 'play';
document.body.dataset.mode = mode;
if (mode === 'play') fitViewport();

loadSettings(saved);
const skip = document.createElement('a');
skip.className = 'skip-link';
skip.href = '#app';
skip.textContent = t('a11y.skip');
document.body.prepend(skip);
const store = createStore();
bindTips(store);
const dispatch = createDispatch({ store, saved });
// M26.5: every server message passes the presentation queue, so nothing runs ahead of the dice.
const pacer = createPacer({ dispatch, store });
const client = createClient({ store, saved, dispatch: pacer.push, spectator: mode === 'screen' });
if (mode === 'screen') pacer.bindSend(client.send); // the TV tells the server what it has shown (M26.3)
const story = createStory(store);
const makeAudio = (url) => (window.__aidmMakeAudio ? window.__aidmMakeAudio(url) : new Audio(url));
const audio = createNarrationAudio({ store, mode, makeAudio });
const sfx = createSfx({ store, mode }); // M26.8: the dice sounds (screen only)
const ctx = { store, saved, client, mode, story, audio, pacer, sfx };

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
applySkin(); // M24: the skin art as CSS custom properties
if (mode === 'screen') sfx.loadTiming(); // the impact times the dice bounce on
bindRemoteAudio({ store, saved, mode });
const music = createMusic({ store, mode, makeAudio });
// The Scribe's voice lives for the whole page (a line can arrive while a view is still mounting). Owner rule
// (M16.2): sound and the Scribe's popup belong to the screen alone; a phone gets neither.
if (mode === 'screen') {
  createScribeVoice({ store, mode, makeAudio, accept: () => true }); // only the screen speaks or shows the Scribe
  mountSoundGate(document.body, { store, audio, sfx });
}
store.subscribe(show);
show(store.get());

const name = saved.name();
if (mode === 'screen') client.connect(t('screen.name'));
else if (name && saved.token()) client.connect(name);
window.aidm = { store, client, dispatch, pacer, audio, music, story, sfx }; // handles for tests and the console
