// The phone as a remote for the shared screen's sound (M11.5): narrator and music level plus a mute each.
// Changes are debounced into one `audio_settings` message carrying all four values (the server allows
// 20 per 2 s, so a drag never trips it). The controls follow `state.audio`; the last write wins.
import { t } from '../strings.js';
import { h } from '../ui/dom.js';

const DEBOUNCE_MS = 250;
const FALLBACK = { narration_volume: 80, music_volume: 50, narration_muted: false, music_muted: false };

export function mountAudioRemote(root, { store, client }) {
  let timer = null;
  const slider = (id) => h('input', { type: 'range', id, min: 0, max: 100, step: 5, 'data-testid': id });
  const box = (id) => h('input', { type: 'checkbox', id, 'data-testid': id });
  const nv = slider('remote-narration-volume');
  const mv = slider('remote-music-volume');
  const nm = box('remote-narration-mute');
  const mm = box('remote-music-mute');

  const send = () => {
    timer = null;
    client.send('audio_settings', {
      narration_volume: Number(nv.value),
      music_volume: Number(mv.value),
      narration_muted: nm.checked,
      music_muted: mm.checked,
    });
  };
  const queue = () => {
    clearTimeout(timer);
    timer = setTimeout(send, DEBOUNCE_MS);
  };
  for (const el of [nv, mv, nm, mm]) el.addEventListener('input', queue);

  const render = (state) => {
    if (timer) return; // the player is mid-change: their value wins until it is sent
    const a = state.snapshot?.state?.audio ?? FALLBACK;
    nv.value = a.narration_volume;
    mv.value = a.music_volume;
    nm.checked = a.narration_muted;
    mm.checked = a.music_muted;
  };
  const row = (labelKey, id, input) => h('div', { class: 'set-row' }, h('label', { for: id }, t(labelKey)), input);
  const check = (labelKey, id, input) => h('div', { class: 'set-row set-check' }, h('label', { for: id }, input, ' ', t(labelKey)));
  root.append(
    h(
      'section',
      { class: 'host-section', 'data-testid': 'audio-remote' },
      h('h3', {}, t('settings.remoteTitle')),
      row('settings.volume', 'remote-narration-volume', nv),
      check('settings.mute', 'remote-narration-mute', nm),
      row('settings.musicVolume', 'remote-music-volume', mv),
      check('settings.musicMute', 'remote-music-mute', mm),
      h('p', { class: 'hint' }, t('settings.remoteHint')),
    ),
  );
  render(store.get());
  const stop = store.subscribe(render);
  return () => {
    clearTimeout(timer);
    stop();
  };
}
