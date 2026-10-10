// Websocket client: hello with token + last_seq, auto-reconnect with backoff, seq tracking, send helpers.
// An `unknown_seat` refusal (a token from an earlier server run, M17.1) parks the client: no hello and
// no reconnect until the player presses Join again (`connect`), which says hello without a token.

const BACKOFF_MS = [500, 1000, 2000, 4000, 8000];

export function backoffDelay(attempt) {
  return BACKOFF_MS[Math.min(attempt, BACKOFF_MS.length - 1)];
}

export function socketUrl(loc = window.location) {
  const scheme = loc.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${scheme}//${loc.host}/ws`;
}

/**
 * createClient({ store, saved, dispatch }) -> { connect, retry, send, close }.
 * `dispatch(msg)` is handlers.dispatch. `connect(name)` starts the session for that player name.
 * `spectator` (the /screen view) says hello with role 'screen': no token, no seat, public feed only;
 * a player says hello with role 'controller' (M11.2).
 */
export function createClient({ store, saved, dispatch, url = socketUrl(), Socket = WebSocket, spectator = false }) {
  let socket = null;
  let name = '';
  let attempt = 0;
  let timer = null;
  let closed = false;
  let parked = false; // M17.1: the table did not know our seat; wait for the player to join again

  function sayHello() {
    const lastSeq = store.get().lastSeq || null;
    const hello = spectator
      ? { name, role: 'screen', last_seq: lastSeq }
      : { name, role: 'controller', token: saved.token(), last_seq: lastSeq };
    send('hello', hello);
  }

  function open() {
    clearTimeout(timer);
    store.update({ conn: 'connecting' });
    socket = new Socket(url);
    socket.onopen = () => {
      attempt = 0;
      store.update({ conn: 'open' });
      if (!parked) sayHello();
    };
    socket.onmessage = (event) => {
      let msg = null;
      try {
        msg = JSON.parse(event.data);
      } catch {
        return;
      }
      if (msg && typeof msg.type === 'string') {
        if (msg.type === 'error' && msg.code === 'unknown_seat') parked = true;
        trackSeq(msg);
        dispatch(msg);
      }
    };
    socket.onclose = () => {
      socket = null;
      if (closed || parked) {
        if (parked) store.update({ conn: 'idle' });
        return;
      }
      store.update({ conn: 'down' });
      timer = setTimeout(open, backoffDelay(attempt++));
    };
    socket.onerror = () => {};
  }

  function trackSeq(msg) {
    if (typeof msg.seq === 'number' && (msg.type === 'event' || msg.type === 'snapshot')) {
      // The server re-sends events with seq >= last_seq, so track the next unseen seq.
      const next = msg.type === 'snapshot' ? msg.seq : Math.max(store.get().lastSeq, msg.seq + 1);
      store.update({ lastSeq: next });
    }
  }

  function send(type, fields = {}) {
    if (!socket || socket.readyState !== 1) return false;
    socket.send(JSON.stringify({ type, ...fields }));
    return true;
  }

  return {
    connect(playerName) {
      name = playerName;
      closed = false;
      const wasParked = parked;
      parked = false;
      if (!socket) open();
      else if (wasParked) sayHello();
    },
    retry() {
      attempt = 0;
      if (socket) socket.close();
      else open();
    },
    send,
    close() {
      closed = true;
      clearTimeout(timer);
      if (socket) socket.close();
    },
  };
}
