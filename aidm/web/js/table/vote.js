// Ready-vote prompt: who proposed what, each voter's state, Ready and Decline buttons, a countdown,
// and (for the host) a force button. The result of a closed vote shows briefly.
import { t } from '../strings.js';
import { clear, h } from '../ui/dom.js';
import { playerName, publicState } from './lookup.js';

const RESULT_MS = 5000;

function voterChips(vote, state) {
  return h(
    'ul',
    { class: 'voters' },
    ...vote.voters.map((id) => {
      const status = vote.ready.includes(id) ? 'ready' : vote.declined.includes(id) ? 'declined' : 'waiting';
      return h('li', { class: `voter ${status}`, 'data-status': status }, playerName(state, id), ' ', h('span', { class: 'muted' }, t(`table.voter_${status}`)));
    }),
  );
}

export function mountVote(root, { store, client }) {
  const box = h('section', { class: 'panel vote', hidden: true, 'aria-live': 'polite', 'data-testid': 'vote' });
  const result = h('p', { class: 'vote-result', role: 'status', 'data-testid': 'vote-result' });
  root.append(box, result);
  let openedFor = null;
  let startedAt = 0;
  let ticker = null;
  let resultTimer = null;
  let lastKey = '';

  function remaining(vote) {
    const elapsed = (Date.now() - startedAt) / 1000;
    return Math.max(0, Math.ceil(vote.seconds - elapsed));
  }

  function render(state) {
    const vote = publicState(state)?.vote ?? null;
    const key = JSON.stringify([vote, state.me, state.players.map((p) => p.name)]);
    if (key === lastKey) return;
    lastKey = key;
    clear(box);
    box.hidden = !vote;
    if (!vote) {
      openedFor = null;
      clearInterval(ticker);
      return;
    }
    if (openedFor !== vote.vote_id) {
      openedFor = vote.vote_id;
      startedAt = vote.openedAt ?? Date.now();
      clearInterval(ticker);
      ticker = setInterval(tick, 1000);
    }
    const me = state.me.playerId;
    const voter = vote.voters.includes(me);
    const timer = h('span', { class: 'vote-timer', 'data-testid': 'vote-timer' }, t('table.seconds', { n: remaining(vote) }));
    box.append(
      h('h3', {}, t(`table.vote_${vote.kind}`), ' ', timer),
      vote.detail ? h('p', { class: 'vote-detail' }, vote.detail) : null,
      h('p', { class: 'hint' }, t('table.proposedBy', { name: playerName(state, vote.proposer_id) })),
      voterChips(vote, state),
      h(
        'div',
        { class: 'vote-actions' },
        voter ? h('button', { type: 'button', class: 'btn btn-primary', 'data-testid': 'vote-ready', disabled: vote.ready.includes(me), onclick: () => client.send('vote', { vote_id: vote.vote_id, ready: true }) }, t('table.ready')) : null,
        voter ? h('button', { type: 'button', class: 'btn', 'data-testid': 'vote-decline', disabled: vote.declined.includes(me), onclick: () => client.send('vote', { vote_id: vote.vote_id, ready: false }) }, t('table.decline')) : null,
        state.me.isHost ? h('button', { type: 'button', class: 'btn btn-small', 'data-testid': 'vote-force', onclick: () => client.send('host_force_vote') }, t('table.force')) : null,
      ),
    );
  }

  function tick() {
    const vote = publicState(store.get())?.vote;
    const el = box.querySelector('[data-testid=vote-timer]');
    if (vote && el) el.textContent = t('table.seconds', { n: remaining(vote) });
  }

  const stopClosed = store.on('vote_closed', (msg) => {
    result.textContent = msg.passed ? t('table.votePassed') : t('table.voteFailed');
    clearTimeout(resultTimer);
    resultTimer = setTimeout(() => (result.textContent = ''), RESULT_MS);
  });
  render(store.get());
  const stop = store.subscribe(render);
  return () => {
    stop();
    stopClosed();
    clearInterval(ticker);
    clearTimeout(resultTimer);
  };
}
