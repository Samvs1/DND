// Read-only vote prompt for the screen: what is proposed, each voter's state and the countdown.
import { playerName, publicState } from '../table/lookup.js';
import { t } from '../strings.js';
import { clear, h } from '../ui/dom.js';

export function mountScreenVote(root, store) {
  const box = h('section', { class: 'sc-vote panel', hidden: true, 'aria-live': 'polite', 'data-testid': 'screen-vote' });
  root.append(box);
  let openedFor = null;
  let startedAt = 0;
  let ticker = null;
  const left = (vote) => Math.max(0, Math.ceil(vote.seconds - (Date.now() - startedAt) / 1000));

  function render(state) {
    const vote = publicState(state)?.vote ?? null;
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
      ticker = setInterval(() => {
        const el = box.querySelector('[data-testid=screen-vote-timer]');
        if (el) el.textContent = t('table.seconds', { n: left(vote) });
      }, 1000);
    }
    box.append(
      h('h3', {}, t(`table.vote_${vote.kind}`), ' ', h('span', { class: 'vote-timer', 'data-testid': 'screen-vote-timer' }, t('table.seconds', { n: left(vote) }))),
      vote.detail ? h('p', {}, vote.detail) : null,
      h('p', { class: 'sc-count', 'data-testid': 'screen-vote-count' }, t('screen.voteCount', { ready: vote.ready.length, total: vote.voters.length })),
      h(
        'ul',
        { class: 'voters' },
        ...vote.voters.map((id) => {
          const status = vote.ready.includes(id) ? 'ready' : vote.declined.includes(id) ? 'declined' : 'waiting';
          return h('li', { class: `voter ${status}` }, playerName(state, id), ' ', h('span', { class: 'muted' }, t(`table.voter_${status}`)));
        }),
      ),
    );
  }
  render(store.get());
  const stop = store.subscribe(render);
  return () => {
    stop();
    clearInterval(ticker);
  };
}
