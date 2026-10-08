// Settings panel: audio mute and volume (narration audio, M8.2), text speed, text size and a reduced-motion override.
// Values live in localStorage via `saved.setSettings` (the only thing persisted besides token and name).
import { t } from '../strings.js';
import { createPanel } from '../ui/modal.js';
import { h } from '../ui/dom.js';
import { DEFAULTS, SIZES, SPEEDS, audioMuted, currentSettings, updateSettings } from './model.js';

function choice(id, labelKey, values, prefix, current, onPick) {
  const select = h('select', { id, 'data-testid': id }, ...values.map((v) => h('option', { value: v, selected: v === current }, t(`settings.${prefix}_${v}`))));
  select.addEventListener('change', () => onPick(select.value));
  return h('div', { class: 'set-row' }, h('label', { for: id }, t(labelKey)), select);
}

function check(id, labelKey, current, onPick, hintKey) {
  const box = h('input', { type: 'checkbox', id, checked: current, 'data-testid': id });
  box.addEventListener('change', () => onPick(box.checked));
  return h('div', { class: 'set-row set-check' }, h('label', { for: id }, box, ' ', t(labelKey)), hintKey ? h('p', { class: 'hint' }, t(hintKey)) : null);
}

export function mountSettings(root, { store, saved, mode }) {
  const panel = createPanel(root, store, { key: 'settings', title: t('settings.title'), testid: 'settings' });
  let built = false;

  function build() {
    panel.body.replaceChildren();
    const s = currentSettings();
    const set = (patch) => updateSettings(patch, saved);
    const slider = (id, key) => {
      const input = h('input', { type: 'range', id, min: 0, max: 100, step: 5, value: s[key], 'data-testid': id });
      input.addEventListener('change', () => set({ [key]: Number(input.value) }));
      return input;
    };
    panel.body.append(
      h('h3', {}, t('settings.audio')),
      check('set-mute', 'settings.mute', audioMuted(s, store.get(), mode), (mute) => set({ mute, muteSet: true })),
      h('div', { class: 'set-row' }, h('label', { for: 'set-volume' }, t('settings.volume')), slider('set-volume', 'narrationVolume')),
      check('set-music-mute', 'settings.musicMute', audioMuted(s, store.get(), mode, 'music'), (musicMute) => set({ musicMute, musicMuteSet: true })),
      h('div', { class: 'set-row' }, h('label', { for: 'set-music-volume' }, t('settings.musicVolume')), slider('set-music-volume', 'musicVolume')),
      h('p', { class: 'hint' }, t('settings.audioHint')),
      h('h3', {}, t('settings.text')),
      choice('set-speed', 'settings.speed', SPEEDS, 'speed', s.speed, (speed) => set({ speed })),
      choice('set-size', 'settings.size', Object.keys(SIZES), 'size', s.size, (size) => set({ size })),
      check('set-motion', 'settings.motion', s.reduceMotion, (reduceMotion) => set({ reduceMotion }), 'settings.motionHint'),
      h('h3', {}, t('a11y.keysTitle')),
      h('ul', { class: 'hint set-keys', 'data-testid': 'set-keys' }, ...['keyTab', 'keyHotbar', 'keyEscape'].map((k) => h('li', {}, t(`a11y.${k}`)))),
      h('button', { type: 'button', class: 'btn btn-small', 'data-testid': 'set-reset', onclick: () => { set({ ...DEFAULTS }); build(); } }, t('settings.reset')),
    );
  }

  function render(state) {
    if (!panel.sync(state)) {
      built = false;
      return;
    }
    if (!built) build();
    built = true;
  }
  render(store.get());
  const stop = store.subscribe(render);
  return () => {
    stop();
    panel.remove();
  };
}
