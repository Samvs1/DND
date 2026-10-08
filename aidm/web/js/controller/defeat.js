// Defeat on the phone (phase "defeated"): a full-page panel with the epilogue and the checkpoint. The host (or the
// only connected player) can retry from the checkpoint, load a save or start a new adventure; others wait.
import { confirmButton } from '../host/confirm.js';
import { fetchSaves } from '../host/saves.js';
import { publicState } from '../table/lookup.js';
import { t } from '../strings.js';
import { clear, h } from '../ui/dom.js';

function mayChoose(state) {
  const connected = state.players.filter((p) => p.connected);
  return state.me.isHost || (connected.length === 1 && connected[0].id === state.me.playerId);
}

export function mountDefeatPanel(root, { store, client }) {
  const text = h('p', { class: 'ct-defeat-text', 'data-testid': 'defeat-text' });
  const checkpoint = h('p', { class: 'hint', 'data-testid': 'defeat-checkpoint' });
  const choices = h('div', { class: 'ct-defeat-choices', 'data-testid': 'defeat-choices' });
  const loadBox = h('div', { class: 'ct-defeat-saves', 'data-testid': 'defeat-saves' });
  const wait = h('p', { class: 'hint', 'data-testid': 'defeat-wait' }, t('ct.defeatWait'));
  const status = h('p', { class: 'form-error', role: 'status', 'data-testid': 'defeat-status' });
  const panel = h('section', { class: 'ct-defeat', hidden: true, role: 'alertdialog', 'aria-labelledby': 'ct-defeat-h', 'data-testid': 'controller-defeat' }, h('h2', { id: 'ct-defeat-h' }, t('ct.defeatTitle')), text, checkpoint, choices, loadBox, wait, status);
  root.append(panel);
  let shown = false;
  let lastKey = '';
  let lastRefusal = store.get().refusal?.n ?? 0;

  async function listSaves() {
    clear(loadBox);
    const rows = await fetchSaves();
    if (rows === null) return void loadBox.append(h('p', { class: 'form-error' }, t('ct.loadFailed')));
    if (!rows.length) return void loadBox.append(h('p', { class: 'hint', 'data-testid': 'defeat-no-saves' }, t('ct.loadNone')));
    loadBox.append(
      h('ul', { class: 'ct-save-list' }, ...rows.map((r) => h('li', {}, h('button', { type: 'button', class: 'btn', 'data-testid': `defeat-load-${r.campaign_id}`, onclick: () => client.send('defeat_load', { campaign_id: r.campaign_id }) }, t('host.savedAt', { id: r.campaign_id, seq: r.seq }))))),
    );
  }

  function build(view) {
    clear(choices);
    const label = view.checkpoint ? t('ct.retry', { label: view.checkpoint }) : t('ct.retryLast');
    choices.append(
      h('button', { type: 'button', class: 'btn btn-primary', 'data-testid': 'defeat-retry', onclick: () => client.send('defeat_retry') }, label),
      h('button', { type: 'button', class: 'btn', 'data-testid': 'defeat-load', onclick: listSaves }, t('ct.loadSave')),
      confirmButton({ label: t('ct.newAdventure'), ask: t('ct.newAsk'), yes: t('ct.newYes'), testid: 'defeat-new', onYes: () => client.send('defeat_new') }),
    );
  }

  function render(state) {
    const view = publicState(state);
    const defeated = view?.phase === 'defeated';
    panel.hidden = !defeated;
    if (!defeated) {
      const wasShown = shown;
      shown = false;
      lastKey = '';
      clear(loadBox);
      status.textContent = '';
      if (wasShown) store.update({ ctab: 'play' });
      return;
    }
    shown = true;
    const refusal = state.refusal;
    if (refusal && refusal.n !== lastRefusal) {
      lastRefusal = refusal.n;
      const msg = t(`refusal.${refusal.code}`);
      status.textContent = msg === `refusal.${refusal.code}` ? t('refusal.generic') : msg;
    }
    const choose = mayChoose(state);
    const key = JSON.stringify([view.defeat, view.checkpoint, choose]);
    if (key === lastKey) return;
    lastKey = key;
    text.textContent = view.defeat ?? '';
    checkpoint.textContent = view.checkpoint ? t('screen.defeatCheckpoint', { label: view.checkpoint }) : '';
    checkpoint.hidden = !view.checkpoint;
    choices.hidden = !choose;
    wait.hidden = choose;
    if (choose) build(view);
  }
  render(store.get());
  return store.subscribe(render);
}
