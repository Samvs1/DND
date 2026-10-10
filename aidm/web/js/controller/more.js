// The More tab: settings, the host panel (host only), the hero file export, text size and how to leave.
import { SIZES, currentSettings, updateSettings } from '../settings/model.js';
import { mountAudioRemote } from './audio_remote.js';
import { mountFullscreen } from '../ui/fullscreen.js';
import { saveExport } from '../wizard/transfer.js';
import { t } from '../strings.js';
import { h } from '../ui/dom.js';

// The Player manual button opens the same view as the /manual page in a full-screen panel.
export function mountMore(root, { store, client, saved }) {
  const open = (panel, testid, label) => h('button', { type: 'button', class: 'btn', 'aria-haspopup': 'dialog', 'data-testid': testid, onclick: () => store.update({ panel }) }, label);
  const host = open('host', 'open-host', t('ct.hostPanel'));
  const size = h('select', { id: 'more-size', 'data-testid': 'more-size' }, ...Object.keys(SIZES).map((v) => h('option', { value: v, selected: v === currentSettings().size }, t(`settings.size_${v}`))));
  size.addEventListener('change', () => updateSettings({ size: size.value }, saved));
  root.append(
    h('h2', { class: 'ct-h' }, t('ct.tab_more')),
    h('div', { class: 'ct-more-list' }, open('settings', 'open-settings', t('tools.settings')), host, open('manual', 'open-manual', t('manual.open'))),
    h('div', { class: 'set-row' }, h('label', { for: 'more-size' }, t('settings.size')), size),
    h('section', { class: 'host-section' }, h('h3', {}, t('ct.heroFile')), h('button', { type: 'button', class: 'btn', 'data-testid': 'export-hero', onclick: () => client.send('export_character', {}) }, t('wz.exportHero')), h('p', { class: 'hint' }, t('ct.heroFileHint'))),
    h('section', { class: 'host-section', 'data-testid': 'leave-info' }, h('h3', {}, t('ct.leaveTitle')), h('p', { class: 'hint' }, t('ct.leaveText'))),
  );
  const screenBox = h('section', { class: 'host-section', 'data-testid': 'fullscreen-section' }, h('h3', {}, t('ct.fullscreenTitle')), h('p', { class: 'hint' }, t('ct.fullscreenHint')));
  const stopFs = mountFullscreen(screenBox, { wide: true, testid: 'fullscreen-more' });
  if (screenBox.querySelector('button')) root.append(screenBox);
  const stopAudio = mountAudioRemote(root, { store, client });
  const render = (state) => (host.hidden = !state.me.isHost);
  render(store.get());
  const stops = [store.subscribe(render), store.on('character_export', saveExport), stopAudio, stopFs];
  return () => stops.forEach((stop) => stop());
}
