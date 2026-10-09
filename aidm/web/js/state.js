// Client store: one plain object, `update(patch)` notifies subscribers. Only the player token,
// the player name and settings are persisted in localStorage (SPEC 12).

const KEY_TOKEN = 'aidm.token';
const KEY_NAME = 'aidm.name';
const KEY_SETTINGS = 'aidm.settings';

function read(key) {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key, value) {
  try {
    if (value === null || value === undefined) window.localStorage.removeItem(key);
    else window.localStorage.setItem(key, value);
  } catch {
    // Storage blocked: the game still works, the player just rejoins by name.
  }
}

export const saved = {
  token: () => read(KEY_TOKEN),
  setToken: (value) => write(KEY_TOKEN, value),
  name: () => read(KEY_NAME),
  setName: (value) => write(KEY_NAME, value),
  settings() {
    try {
      return JSON.parse(read(KEY_SETTINGS) || '{}');
    } catch {
      return {};
    }
  },
  setSettings: (value) => write(KEY_SETTINGS, JSON.stringify(value)),
};

export function initialState() {
  return {
    conn: 'idle', // idle | connecting | open | down
    joined: false,
    me: { playerId: null, isHost: false },
    phase: 'lobby',
    players: [],
    snapshot: null,
    lastSeq: 0,
    notices: [],
    fallback: false,
    errorCode: null,
    confirm: null, // a pending point-of-no-return prompt for this player
    turnEndsAt: null, // local ms time the running turn timer ends (ui/countdown.js), or null
    lastOutcome: null, // how the last fight ended: victory | defeat | fled | parley (combat_state.outcome)
    levelUps: {}, // creature id -> level offered by level_up_available
    sheet: null, // the latest `sheet` message (own hero: sheet + level-up options)
    sheetOpen: false, // the sheet drawer
    levelUpOpen: false, // the level-up dialog
    refusal: null, // {code, n}: the latest refused command or gear change (typed, never raw text)
    audioBlocked: false, // the browser refused to autoplay narration audio (a click enables it)
    panel: null, // which table panel is open: journal | map | shop | host | settings
    shop: null, // the latest `shop_stock` message (an open shop's stock and prices)
    hostStats: null, // the latest `host_stats` message (host only)
    wizardOpen: null, // null = open until the player has a hero; true/false once chosen
    scribeLine: null, // the Scribe line being shown on this device (voice.js), or null
    scribeSpeaking: false, // his clip is playing here: narration.js holds its queue
    ctab: 'play', // the phone controller tab: play | hero | journal | scribe | more
    jtab: 'journal', // the Journal tab's sub-tab: journal | map
    lan: { lan: false, url: null },
  };
}

/** The seat of the local player, or null. */
export function mySeat(state) {
  return state.players.find((p) => p.id === state.me.playerId) ?? null;
}

export function hasHero(state) {
  return Boolean(mySeat(state)?.creature_id);
}

export function createStore(start = initialState()) {
  let state = start;
  const listeners = new Set();
  const topics = new Map();
  return {
    get: () => state,
    update(patch) {
      state = { ...state, ...patch };
      for (const fn of [...listeners]) fn(state);
    },
    subscribe(fn) {
      listeners.add(fn);
      return () => listeners.delete(fn);
    },
    /** Fire-and-forget channel for stream-like messages (narration, dice) that views listen to. */
    on(topic, fn) {
      if (!topics.has(topic)) topics.set(topic, new Set());
      topics.get(topic).add(fn);
      return () => topics.get(topic).delete(fn);
    },
    emit(topic, payload) {
      for (const fn of [...(topics.get(topic) || [])]) fn(payload);
    },
  };
}
