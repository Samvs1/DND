// Handler registry: ONE entry per ServerMsg type (a test compares the keys with protocol.json).
// Unknown types are ignored with a console debug line, never shown to the player.
// Handlers receive (msg, ctx) where ctx = { store, saved }. Views read the store or listen with
// store.on(<type>, fn) for stream-like messages.

import { turnEndsAt } from './ui/countdown.js';

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
    joinNote: null,
    ...(sameSeat ? {} : { snapshot: null, players: [], lastSeq: 0, notices: [], fallback: false, wizardOpen: null, confirm: null, turnEndsAt: null, lastOutcome: null, levelUps: {}, sheet: null, sheetOpen: false, levelUpOpen: false, refusal: null, panel: null, shop: null, hostStats: null }),
  });
  if (!sameSeat) store.emit('reset', {});
}

function onSnapshot(msg, { store }) {
  const state = msg.state;
  const endsAt = turnEndsAt(state.floor?.seconds_left);
  store.update({ snapshot: msg, phase: state.phase, lastSeq: msg.seq, turnEndsAt: endsAt, ...withMe(store, state.players || []) });
  store.emit('snapshot', msg);
}

// The host role can move (M17.1): every page reads its own host flag from the player list.
function withMe(store, players) {
  const me = store.get().me;
  const mine = players.find((p) => p.id === me.playerId);
  return mine && Boolean(mine.is_host) !== me.isHost ? { players, me: { ...me, isHost: Boolean(mine.is_host) } } : { players };
}

function onRoster(msg, { store }) {
  store.update(withMe(store, msg.players || []));
}

function onNotice(msg, { store }) {
  if (msg.kind === 'fallback') {
    store.update({ fallback: true });
    return;
  }
  const notices = [...store.get().notices, { kind: msg.kind, text: msg.text }].slice(-MAX_NOTICES);
  store.update({ notices });
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

let refusalCount = 0;

function onError(msg, { store, saved }) {
  // The text is never shown. A typed refusal (combat command, gear change) is mapped to friendly
  // wording by the combat view and the sheet; every other code goes to the banner.
  if (msg.code === 'unknown_seat') {
    // M17.1: our seat is from an earlier server run. Forget the token (keep the name) and show the
    // join form with a short line; the player joins again by pressing Join.
    saved.setToken(null);
    store.update({ joined: false, me: { playerId: null, isHost: false }, snapshot: null, players: [], phase: 'lobby', lastSeq: 0, errorCode: null, joinNote: 'restarted' });
    return;
  }
  if (msg.refusal) {
    refusalCount += 1;
    store.update({ refusal: { code: msg.refusal, n: refusalCount } });
    return;
  }
  store.update({ errorCode: msg.code || 'generic' });
}

function onSheet(msg, ctx) {
  ctx.store.update({ sheet: msg });
  relay(msg, ctx);
}

function onShopStock(msg, ctx) {
  ctx.store.update({ shop: msg, panel: 'shop' });
  relay(msg, ctx);
}

function onHostStats(msg, ctx) {
  ctx.store.update({ hostStats: msg });
  relay(msg, ctx);
}

function onCombat(msg, ctx) {
  // A fight that starts drops the server's open "Are you sure?" (begin_combat): close it too.
  const before = ctx.store.get().snapshot?.state.combat ?? null;
  if (!before && msg.combat && ctx.store.get().confirm) ctx.store.update({ confirm: null });
  // M15.1: the real outcome, set BEFORE the combat flips off (the banner and the stinger read it; the
  // party HP in the snapshot may still be stale then).
  ctx.store.update({ lastOutcome: msg.combat ? null : msg.outcome ?? null });
  patchSnapshot(ctx, { combat: msg.combat ?? null });
  relay(msg, ctx);
}

function onQueue(msg, ctx) {
  patchSnapshot(ctx, { queue: msg.entries || [], resolving: msg.resolving ?? null });
  relay(msg, ctx);
}

// M11.2: the public floor (holder, queue, typing) and the shared screen's audio settings.
function onFloor(msg, ctx) {
  ctx.store.update({ turnEndsAt: turnEndsAt(msg.floor?.seconds_left) });
  patchSnapshot(ctx, { floor: msg.floor ?? null });
  relay(msg, ctx);
}

function onAudioSettings(msg, ctx) {
  patchSnapshot(ctx, { audio: msg.settings ?? null });
  relay(msg, ctx);
}

function onTurnPrompt(msg, ctx) {
  ctx.store.update({ turnEndsAt: turnEndsAt(msg.seconds) });
  relay(msg, ctx);
}

function onResolving(msg, ctx) {
  patchSnapshot(ctx, { resolving: msg.entry ?? null });
  relay(msg, ctx);
}

export const HANDLERS = {
  ability_rolls: relay,
  audio_settings: onAudioSettings,
  character_export: relay,
  chat: relay,
  combat_state: onCombat,
  creation_result: relay,
  dice_roll: relay,
  encounter_offer: onOffer,
  epilogue: relay,
  error: onError,
  event: relay,
  floor_state: onFloor,
  hit_chances: relay,
  host_stats: onHostStats,
  level_up_available: onLevelUp,
  lobby_roster: onRoster,
  narration_chunk: relay, // never clears the open confirm (M15.1 playtest)
  narration_done: relay,
  notice: onNotice,
  pending_confirmation: onConfirmation,
  pong: relay,
  queue_state: onQueue,
  resolving: onResolving,
  scribe_line: relay,
  scribe_skip: relay,
  sheet: onSheet,
  shop_stock: onShopStock,
  snapshot: onSnapshot,
  story_history: relay,
  suggestion: relay,
  turn_prompt: onTurnPrompt,
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
