// Host panel (host only; the toolbar never shows it to anyone else and the table view does not mount it):
// pause/resume, kick, difficulty sliders, spoken narration, save/load/new/end, force the open vote and the
// storyteller's token totals. Every action is one `host_*` message; the server refuses non-hosts anyway.
import { t } from '../strings.js';
import { createPanel } from '../ui/modal.js';
import { clear, h } from '../ui/dom.js';
import { publicState } from '../table/lookup.js';
import { confirmButton } from './confirm.js';
import { fetchSaves } from './saves.js';

const SLIDER = { min: 0.25, max: 3, step: 0.25 };

function slider(testid, key, onChange) {
  const label = h('label', { for: `host-${testid}` });
  const input = h('input', { type: 'range', id: `host-${testid}`, ...SLIDER, value: 1, 'data-testid': testid });
  const show = () => (label.textContent = t(key, { n: Number(input.value).toFixed(2).replace(/\.?0+$/, '') }));
  input.addEventListener('input', show);
  input.addEventListener('change', onChange);
  show();
  return { label, input, show };
}

function stats(msg) {
  if (!msg) return t('host.noTokens');
  return t('host.tokenLine', { calls: msg.calls, prompt: msg.prompt_tokens, completion: msg.completion_tokens });
}

export function mountHost(root, { store, client }) {
  const panel = createPanel(root, store, { key: 'host', title: t('host.title'), testid: 'host' });
  const send = (type, fields) => client.send(type, fields);
  const pause = h('button', { type: 'button', class: 'btn', 'data-testid': 'host-pause' });
  const pauseState = h('p', { class: 'hint', role: 'status', 'data-testid': 'host-pause-state' });
  const force = h('button', { type: 'button', class: 'btn btn-small', 'data-testid': 'host-force', onclick: () => send('host_force_vote') }, t('host.forceVote'));
  const players = h('ul', { class: 'host-players', 'data-testid': 'host-players' });
  const hp = slider('host-hp', 'host.monsterHp', () => sendDifficulty());
  const dmg = slider('host-damage', 'host.monsterDamage', () => sendDifficulty());
  const tts = h('input', { type: 'checkbox', id: 'host-tts', 'data-testid': 'host-tts' });
  const ttsState = h('span', { class: 'hint' });
  const saved = h('p', { class: 'hint', role: 'status', 'data-testid': 'host-saved' });
  const loadSelect = h('select', { id: 'host-load', 'data-testid': 'host-load-select' });
  const loadBox = h('div', { class: 'host-load' });
  const usage = h('p', { class: 'hint', 'data-testid': 'host-stats' });
  let wasOpen = false;
  let lastPlayers = '';

  function sendDifficulty() {
    send('host_difficulty', { monster_hp: Number(hp.input.value), monster_damage: Number(dmg.input.value) });
  }
  pause.addEventListener('click', () => send(publicState(store.get())?.paused ? 'host_resume' : 'host_pause'));
  tts.addEventListener('change', () => send('host_tts_toggle', { enabled: tts.checked }));

  async function refreshSaves() {
    const rows = await fetchSaves();
    clear(loadBox);
    if (rows === null) return void loadBox.append(h('p', { class: 'form-error' }, t('host.loadFailed')));
    if (!rows.length) return void loadBox.append(h('p', { class: 'hint', 'data-testid': 'host-no-saves' }, t('host.loadNone')));
    clear(loadSelect);
    loadSelect.append(...rows.map((r) => h('option', { value: r.campaign_id }, t('host.savedAt', { id: r.campaign_id, seq: r.seq }))));
    const ask = () => t('host.loadAsk', { id: loadSelect.value });
    const confirm = confirmButton({ label: t('host.load'), ask: ask(), yes: t('host.loadYes'), testid: 'host-load', onYes: () => send('host_load', { campaign_id: loadSelect.value }) });
    loadSelect.onchange = () => confirm.querySelector('.hc-ask')?.replaceChildren(ask());
    loadBox.append(h('label', { for: 'host-load' }, t('host.loadLabel')), loadSelect, confirm);
  }

  function renderPlayers(state) {
    const others = state.players.filter((p) => p.id !== state.me.playerId);
    const key = JSON.stringify(others.map((p) => [p.id, p.name]));
    if (key === lastPlayers) return;
    lastPlayers = key;
    clear(players);
    if (!others.length) return void players.append(h('li', { class: 'hint' }, t('host.noPlayers')));
    for (const p of others) {
      const kick = confirmButton({ label: t('host.kick'), ask: t('host.kickAsk', { name: p.name }), yes: t('host.kickYes'), testid: `host-kick-${p.id}`, small: true, onYes: () => send('host_kick', { player_id: p.id }) });
      players.append(h('li', { class: 'host-player', 'data-testid': 'host-player' }, h('span', {}, p.name), kick));
    }
  }

  function syncValues(view) {
    pause.textContent = view.paused ? t('host.resume') : t('host.pause');
    pauseState.textContent = view.paused ? t('host.paused') : t('host.running');
    for (const [s, value] of [[hp, view.monster_hp], [dmg, view.monster_damage]]) {
      if (document.activeElement !== s.input) s.input.value = String(value);
      s.show();
    }
    tts.checked = Boolean(view.tts_enabled);
    ttsState.textContent = view.tts_enabled ? t('host.ttsOn') : t('host.ttsOff');
  }

  function render(state) {
    const open = panel.sync(state);
    if (open && !wasOpen) refreshSaves();
    wasOpen = open;
    if (!open) return;
    const view = publicState(state);
    if (view) syncValues(view);
    renderPlayers(state);
    usage.textContent = stats(state.hostStats);
  }

  const section = (title, ...kids) => h('section', { class: 'host-section' }, h('h3', {}, title), ...kids);
  const saveButton = h('button', { type: 'button', class: 'btn', 'data-testid': 'host-save', onclick: () => { send('host_save'); saved.textContent = t('host.saved'); } }, t('host.save'));
  const newGame = confirmButton({ label: t('host.newGame'), ask: t('host.newAsk'), yes: t('host.newYes'), testid: 'host-new', onYes: () => send('host_new') });
  const endGame = confirmButton({ label: t('host.end'), ask: t('host.endAsk'), yes: t('host.endYes'), testid: 'host-end', onYes: () => send('host_end') });
  panel.body.append(
    section(t('host.session'), pause, pauseState, force),
    section(t('host.players'), players),
    section(t('host.difficulty'), hp.label, hp.input, dmg.label, dmg.input, h('p', { class: 'hint' }, t('host.difficultyHint'))),
    section(t('host.tts'), h('label', { for: 'host-tts', class: 'host-check' }, tts, ' ', ttsState)),
    section(t('host.campaigns'), saveButton, saved, loadBox, h('div', { class: 'host-danger' }, newGame, endGame)),
    section(t('host.tokens'), usage),
  );
  render(store.get());
  const stop = store.subscribe(render);
  return () => {
    stop();
    panel.remove();
  };
}
