// The presentation queue (M26.5, docs/next/GOAL_DICE.md "Timing"): every server message passes through
// here on its way to the dispatcher, in order. A message that starts a show (a roll, a hit landing on
// the board) is dispatched, then everything after it WAITS until the show ends: event lines, narration,
// snapshots and turn prompts never run ahead of the dice. A short list of messages that answer this
// device directly (pong, refusals, previews, the shop) bypasses the queue.
// - `director(msg, { ms, scale, signal })` plays the show and returns a promise (the screen); without
//   one, or when it returns null, the queue just holds the nominal time (the phones), so all devices
//   keep the same pace. A show can never stall the table: a cap timer ends it.
// - story_history (a reload or reconnect) flushes the queue at once, with no shows.
// - The screen reports `presented {seq}` (the highest event or dice seq it has finished showing) so the
//   server's AI turns wait for the TV (M26.3, aidm/session/show_pace.py).
// - `skip()` ends the show in progress (a click on the TV); its verdict is still shown by the director.
// - `onShow(fn)`: fn(msg, { ms, scale, stage, combat }) when a show starts, on every device (the roller's
//   phone shows its roll card in time with the TV).
// - A roll that arrives while the table is idle waits GATHER_MS first: the server sends a turn's events as
//   a burst, and the backlog speed-up must see the whole burst, not just its first roll.
import { backlogFactor, inCombat, isStageRoll, motionFactor, nominalMs } from './timing.js';

export const BYPASS = new Set([
  'pong',
  'error',
  'hit_chances',
  'shop_stock',
  'character_export',
  'creation_result',
  'ability_rolls',
  'host_stats',
  'chat',
  'suggestion',
  'audio_settings',
  'floor_state',
  'welcome',
  'lobby_roster',
]);
const CAP_SLACK_MS = 2000; // a show may overrun its budget by this much before the queue moves on
const SKIP_MS = 700; // how long a skipped show may take to finish
export const GATHER_MS = 40;

export function createPacer({ dispatch, store, timers = { set: (fn, ms) => setTimeout(fn, ms), clear: (id) => clearTimeout(id) } }) {
  const queue = [];
  let current = null; // { finish, abort, control }
  let flushing = false;
  let director = null;
  const listeners = new Set();
  let send = null;
  let shownSeq = -1;
  let reportedSeq = -1;

  function track(msg) {
    if ((msg.type === 'event' || msg.type === 'dice_roll') && typeof msg.seq === 'number') shownSeq = Math.max(shownSeq, msg.seq);
  }

  function report() {
    if (!send || shownSeq <= reportedSeq) return;
    if (send('presented', { seq: shownSeq }) !== false) reportedSeq = shownSeq;
  }

  function waitingShows() {
    const combat = inCombat(store);
    return queue.reduce((n, msg) => n + (nominalMs(msg, combat) > 0 ? 1 : 0), 0);
  }

  function start(msg, nominal, combat) {
    const scale = backlogFactor(waitingShows()) * motionFactor();
    const ms = Math.round(nominal * scale);
    const control = new AbortController();
    let done = false;
    const finish = () => {
      if (done) return;
      done = true;
      timers.clear(cap);
      current = null;
      track(msg);
      report();
      pump();
    };
    const cap = timers.set(finish, ms + CAP_SLACK_MS);
    current = {
      finish,
      control,
      abort() {
        control.abort();
        timers.set(finish, SKIP_MS);
      },
    };
    const stage = msg.type === 'dice_roll' && Boolean(msg.dice) && isStageRoll(msg.dice, combat);
    for (const fn of [...listeners]) {
      try {
        fn(msg, { ms, scale, stage, combat });
      } catch (err) {
        console.error('show listener failed', err); // a broken listener never stalls the queue
      }
    }
    let shown = null;
    try {
      shown = director ? director(msg, { ms, scale, signal: control.signal }) : null;
    } catch (err) {
      console.error('show failed', err); // fail soft: the queue holds the nominal time instead
    }
    if (shown && typeof shown.then === 'function') shown.then(finish, finish);
    else timers.set(finish, ms);
  }

  /** Hold the queue for GATHER_MS so the rest of a burst can arrive before the first show is timed. */
  function gather() {
    const control = new AbortController();
    const finish = () => {
      timers.clear(timer);
      current = null;
      pump();
    };
    const timer = timers.set(finish, GATHER_MS);
    current = { finish, control, abort() {} };
  }

  function pump() {
    if (flushing) return;
    while (!current && queue.length) {
      const msg = queue.shift();
      const combat = inCombat(store); // the state the table shows BEFORE this message
      dispatch(msg);
      const nominal = nominalMs(msg, combat);
      if (nominal > 0) {
        start(msg, nominal, combat);
        return;
      }
      track(msg);
    }
    if (!current) report();
  }

  /** Show everything queued at once (a reload, a reconnect): no shows, same order. */
  function flush() {
    flushing = true;
    if (current) {
      current.control.abort(); // the director drops its visuals
      current.finish();
    }
    while (queue.length) {
      const msg = queue.shift();
      dispatch(msg);
      track(msg);
    }
    flushing = false;
  }

  return {
    push(msg) {
      if (BYPASS.has(msg.type)) {
        dispatch(msg);
        return;
      }
      if (msg.type === 'story_history') {
        flush();
        dispatch(msg);
        report();
        return;
      }
      const idle = !current && queue.length === 0;
      queue.push(msg);
      if (idle && nominalMs(msg, inCombat(store)) > 0) gather();
      else pump();
    },
    /** The screen's show player; null puts back the nominal holds. */
    setDirector(fn) {
      director = fn;
    },
    /** `send(type, fields)` of the websocket client: set on the screen only (it reports what it showed). */
    bindSend(fn) {
      send = fn;
      report();
    },
    skip() {
      if (current) current.abort();
    },
    /** fn(msg, { ms, scale, stage, combat }) whenever a show starts; returns an unsubscribe. */
    onShow(fn) {
      listeners.add(fn);
      return () => listeners.delete(fn);
    },
    busy: () => Boolean(current) || queue.length > 0,
    waiting: () => queue.length,
    flush,
  };
}
