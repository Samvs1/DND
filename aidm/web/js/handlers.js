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
    ...(sameSeat ? {} : { snapshot: null, players: [], lastSeq: 0, notices: [], fallback: false }),
  });
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
  encounter_offer: relay,
  epilogue: relay,
  error: onError,
  event: relay,
  hit_chances: relay,
  host_stats: relay,
  level_up_available: relay,
  lobby_roster: onRoster,
  narration_chunk: relay,
  narration_done: relay,
  notice: onNotice,
  pending_confirmation: relay,
  pong: relay,
  queue_state: onQueue,
  resolving: onResolving,
  shop_stock: relay,
  snapshot: onSnapshot,
  suggestion: relay,
  turn_prompt: relay,
  vote_closed: relay,
  vote_open: relay,
  vote_update: relay,
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
