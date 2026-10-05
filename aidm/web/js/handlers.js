// Handler registry: ONE entry per ServerMsg type (a test compares the keys with protocol.json).
// Unknown types are ignored with a console debug line, never shown to the player.
// Handlers receive (msg, ctx) where ctx = { store, saved }. Views read the store or listen with
// store.on(<type>, fn) for stream-like messages.

const MAX_NOTICES = 5;

function relay(msg, { store }) {
  store.emit(msg.type, msg);
}

function patchSnapshot(ctx, patch) {
  const snapshot = ctx.store.get().snapshot;
  if (snapshot) ctx.store.update({ snapshot: { ...snapshot, state: { ...snapshot.state, ...patch } } });
}

function onWelcome(msg, { store, saved }) {
  const current = store.get();
  const sameSeat = current.me.playerId === msg.player_id;
  saved.setToken(msg.token);
  // A repeated welcome (host load/new) may bring a new player id and a fresh world.
  store.update({
    joined: true,
    me: { playerId: msg.player_id, isHost: Boolean(msg.is_host) },
    errorCode: null,
    ...(sameSeat ? {} : { snapshot: null, players: [], lastSeq: 0, notices: [], fallback: false, wizardOpen: null, confirm: null, levelUps: {} }),
  });
  if (!sameSeat) store.emit('reset', {});
}

function onSnapshot(msg, { store }) {
  const state = msg.state;
  store.update({ snapshot: msg, phase: state.phase, players: state.players || [], lastSeq: msg.seq });
  store.emit('snapshot', msg);
}

function onRoster(msg, { store }) {
  store.update({ players: msg.players || [] });
}

function onNotice(msg, { store }) {
  if (msg.kind === 'fallback') {
    store.update({ fallback: true });
    return;
  }
  const notices = [...store.get().notices, { kind: msg.kind, text: msg.text }].slice(-MAX_NOTICES);
  store.update({ notices });
}

function onNarration(msg, ctx) {
  if (ctx.store.get().confirm) ctx.store.update({ confirm: null });
  relay(msg, ctx);
}

function onVoteOpen(msg, ctx) {
  const vote = {
    vote_id: msg.vote_id,
    kind: msg.kind,
    detail: msg.detail || '',
    proposer_id: msg.proposer_id,
    voters: msg.voters || [],
    ready: [msg.proposer_id], // the proposer counts as ready from the start
    declined: [],
    seconds: msg.seconds,
    openedAt: Date.now(),
  };
  patchSnapshot(ctx, { vote });
  relay(msg, ctx);
}

function onVoteUpdate(msg, ctx) {
  const vote = ctx.store.get().snapshot?.state.vote;
  if (vote && vote.vote_id === msg.vote_id) {
    patchSnapshot(ctx, { vote: { ...vote, ready: msg.ready || [], declined: msg.declined || [] } });
  }
  relay(msg, ctx);
}

function onVoteClosed(msg, ctx) {
  patchSnapshot(ctx, { vote: null });
  relay(msg, ctx);
}

function onOffer(msg, ctx) {
  patchSnapshot(ctx, { offer: msg.offer ?? null });
  relay(msg, ctx);
}

function onConfirmation(msg, ctx) {
  ctx.store.update({ confirm: { playerId: msg.player_id, prompt: msg.prompt } });
  relay(msg, ctx);
}

function onLevelUp(msg, ctx) {
  const levelUps = { ...ctx.store.get().levelUps, [msg.creature_id]: msg.level };
  ctx.store.update({ levelUps });
  relay(msg, ctx);
}

function onError(msg, { store }) {
  // The text is never shown; the banner maps the code to a friendly string.
  store.update({ errorCode: msg.code || 'generic' });
}

function onCombat(msg, ctx) {
  patchSnapshot(ctx, { combat: msg.combat ?? null });
  relay(msg, ctx);
}

function onQueue(msg, ctx) {
  patchSnapshot(ctx, { queue: msg.entries || [], resolving: msg.resolving ?? null });
  relay(msg, ctx);
}

function onResolving(msg, ctx) {
  patchSnapshot(ctx, { resolving: msg.entry ?? null });
  relay(msg, ctx);
}

export const HANDLERS = {
  ability_rolls: relay,
  chat: relay,
  combat_state: onCombat,
  creation_result: relay,
  dice_roll: relay,
  encounter_offer: onOffer,
  epilogue: relay,
  error: onError,
  event: relay,
  hit_chances: relay,
  host_stats: relay,
  level_up_available: onLevelUp,
  lobby_roster: onRoster,
  narration_chunk: onNarration,
  narration_done: relay,
  notice: onNotice,
  pending_confirmation: onConfirmation,
  pong: relay,
  queue_state: onQueue,
  resolving: onResolving,
  shop_stock: relay,
  snapshot: onSnapshot,
  suggestion: relay,
  turn_prompt: relay,
  vote_closed: onVoteClosed,
  vote_open: onVoteOpen,
  vote_update: onVoteUpdate,
  welcome: onWelcome,
};

export function createDispatch(ctx) {
  return function dispatch(msg) {
    const handler = Object.hasOwn(HANDLERS, msg.type) ? HANDLERS[msg.type] : null;
    if (!handler) {
      console.debug('ignored message type', msg.type);
      return;
    }
    handler(msg, ctx);
  };
}
