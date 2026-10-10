// Lobby view: join by name, roster, host start with theme ("surprise me"), invite panel.
// Built once; store updates patch the pieces so typing in the inputs is never interrupted.
import { t } from '../strings.js';
import { hasHero } from '../state.js';
import { clear, h } from '../ui/dom.js';
import { titleCase } from '../ui/format.js';
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
  const note = h('p', { class: 'hint', role: 'status', 'data-testid': 'join-note', hidden: true }, t('join.restarted'));
  const button = h('button', { type: 'submit', class: 'btn btn-primary' }, t('join.button'));
  const form = h(
    'form',
    { class: 'panel join', 'data-testid': 'join-form', novalidate: true },
    h('h2', {}, t('join.heading')),
    note,
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
  return { form, input, note };
}

function heroLine(state, player) {
  const hero = (state.snapshot?.state.party ?? []).find((c) => c.id === player.creature_id);
  if (!hero) return t('lobby.heroReady');
  return t('lobby.heroLine', { name: hero.name, race: titleCase(hero.race), cls: titleCase(hero.class_index) });
}

function renderRoster(list, state) {
  clear(list);
  if (!state.players.length) {
    list.append(h('li', { class: 'muted' }, t('lobby.empty')));
    return;
  }
  for (const player of state.players) {
    const mine = player.id === state.me.playerId;
    const ready = Boolean(player.creature_id);
    list.append(
      h(
        'li',
        { class: player.connected ? 'on' : 'off', 'data-player': player.id, 'data-ready': String(ready) },
        h('span', { class: 'dot', 'aria-hidden': 'true' }),
        h('span', { class: 'who' }, player.name),
        mine ? h('span', { class: 'tag' }, t('lobby.you')) : null,
        player.is_host ? h('span', { class: 'tag tag-host' }, t('lobby.host')) : null,
        player.connected ? null : h('span', { class: 'tag tag-away' }, t('lobby.away')),
        h('span', { class: ready ? 'hero ready' : 'hero pending', 'data-testid': 'hero-state' }, ready ? heroLine(state, player) : t('lobby.noHero')),
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
    if (start.disabled) return;
    ctx.client.send('host_start', { theme: theme.value.trim() || null });
  });
  return { form, start };
}

export function mountLobby(root, ctx) {
  const { store } = ctx;
  const { form: join, input: joinName, note: joinNote } = joinForm(ctx);
  const roster = h('ul', { class: 'roster', 'data-testid': 'roster' });
  const { form: host, start } = hostControls(ctx);
  const edit = h('button', { type: 'button', class: 'btn btn-small', 'data-testid': 'edit-hero', onclick: () => store.update({ wizardOpen: true }) }, t('lobby.editHero'));
  const waitHeroes = h('p', { class: 'hint', 'data-testid': 'wait-heroes' }, t('lobby.needHeroes'));
  const wait = h('p', { class: 'hint', 'data-testid': 'wait' }, t('lobby.waitingHost'));
  const forging = h('p', { class: 'hint forging', role: 'status', 'data-testid': 'forging' }, t('lobby.generating'));
  const inviteSlot = h('div', {});
  const table = h(
    'div',
    { class: 'lobby-table' },
    h('section', { class: 'panel', 'aria-labelledby': 'roster-h' }, h('h2', { id: 'roster-h' }, t('lobby.roster')), roster, edit, host, waitHeroes, wait, forging),
    inviteSlot,
  );

  root.append(
    h('header', { class: 'masthead' }, h('h1', {}, t('app.title')), h('p', { class: 'tagline' }, t('app.tagline'))),
    h('div', { class: 'lobby' }, join, table),
  );

  function render(state) {
    join.hidden = state.joined;
    joinNote.hidden = state.joined || state.joinNote !== 'restarted';
    if (!state.joined && !joinName.value) joinName.value = ctx.saved.name() || '';
    table.hidden = !state.joined;
    renderRoster(roster, state);
    const generating = state.phase === 'generating';
    const everyone = state.players.filter((p) => p.connected).every((p) => p.creature_id);
    const ready = hasHero(state) && everyone;
    start.disabled = !ready;
    waitHeroes.hidden = !state.me.isHost || generating || ready;
    edit.hidden = !state.joined || generating;
    edit.textContent = hasHero(state) ? t('lobby.editHero') : t('lobby.createHero');
    host.hidden = !state.me.isHost || generating;
    wait.hidden = state.me.isHost || generating;
    forging.hidden = !generating;
  }
  render(store.get());
  const stops = [store.subscribe(render), mountInvite(inviteSlot, store)];
  fetchLan(store);
  return () => stops.forEach((stop) => stop());
}
