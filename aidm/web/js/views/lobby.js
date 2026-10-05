// Lobby view: join by name, roster, host start with theme ("surprise me"), invite panel.
// Built once; store updates patch the pieces so typing in the inputs is never interrupted.
import { t } from '../strings.js';
import { clear, h } from '../ui/dom.js';
import { fetchLan, mountInvite } from '../ui/invite.js';

function joinForm(ctx) {
  const input = h('input', {
    id: 'join-name',
    name: 'name',
    type: 'text',
    maxlength: 24,
    autocomplete: 'nickname',
    placeholder: t('join.namePlaceholder'),
    value: ctx.saved.name() || '',
    required: true,
  });
  const error = h('p', { class: 'form-error', role: 'alert' });
  const button = h('button', { type: 'submit', class: 'btn btn-primary' }, t('join.button'));
  const form = h(
    'form',
    { class: 'panel join', 'data-testid': 'join-form', novalidate: true },
    h('h2', {}, t('join.heading')),
    h('label', { for: 'join-name' }, t('join.nameLabel')),
    input,
    error,
    button,
  );
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    const name = input.value.trim();
    error.textContent = name ? '' : t('join.nameRequired');
    if (!name) return;
    ctx.saved.setName(name);
    ctx.client.connect(name);
  });
  return form;
}

function renderRoster(list, state) {
  clear(list);
  if (!state.players.length) {
    list.append(h('li', { class: 'muted' }, t('lobby.empty')));
    return;
  }
  for (const player of state.players) {
    const mine = player.id === state.me.playerId;
    list.append(
      h(
        'li',
        { class: player.connected ? 'on' : 'off', 'data-player': player.id },
        h('span', { class: 'dot', 'aria-hidden': 'true' }),
        h('span', { class: 'who' }, player.name),
        mine ? h('span', { class: 'tag' }, t('lobby.you')) : null,
        player.is_host ? h('span', { class: 'tag tag-host' }, t('lobby.host')) : null,
        player.connected ? null : h('span', { class: 'tag tag-away' }, t('lobby.away')),
      ),
    );
  }
}

function hostControls(ctx) {
  const theme = h('input', {
    id: 'theme',
    name: 'theme',
    type: 'text',
    maxlength: 120,
    placeholder: t('lobby.themePlaceholder'),
  });
  const start = h('button', { type: 'submit', class: 'btn btn-primary', 'data-testid': 'start' }, t('lobby.start'));
  const form = h(
    'form',
    { class: 'host-controls', novalidate: true },
    h('label', { for: 'theme' }, t('lobby.themeLabel')),
    theme,
    start,
  );
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    ctx.client.send('host_start', { theme: theme.value.trim() || null });
  });
  return form;
}

export function mountLobby(root, ctx) {
  const { store } = ctx;
  const join = joinForm(ctx);
  const roster = h('ul', { class: 'roster', 'data-testid': 'roster' });
  const host = hostControls(ctx);
  const wait = h('p', { class: 'hint', 'data-testid': 'wait' }, t('lobby.waitingHost'));
  const forging = h('p', { class: 'hint forging', role: 'status', 'data-testid': 'forging' }, t('lobby.generating'));
  const inviteSlot = h('div', {});
  const table = h(
    'div',
    { class: 'lobby-table' },
    h('section', { class: 'panel', 'aria-labelledby': 'roster-h' }, h('h2', { id: 'roster-h' }, t('lobby.roster')), roster, host, wait, forging),
    inviteSlot,
  );

  root.append(
    h('header', { class: 'masthead' }, h('h1', {}, t('app.title')), h('p', { class: 'tagline' }, t('app.tagline'))),
    h('div', { class: 'lobby' }, join, table),
  );

  function render(state) {
    join.hidden = state.joined;
    table.hidden = !state.joined;
    renderRoster(roster, state);
    const generating = state.phase === 'generating';
    host.hidden = !state.me.isHost || generating;
    wait.hidden = state.me.isHost || generating;
    forging.hidden = !generating;
  }
  render(store.get());
  const stops = [store.subscribe(render), mountInvite(inviteSlot, store)];
  fetchLan(store);
  return () => stops.forEach((stop) => stop());
}
