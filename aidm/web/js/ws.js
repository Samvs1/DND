// Websocket client: hello with token + last_seq, auto-reconnect with backoff, seq tracking, send helpers.

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
 */
export function createClient({ store, saved, dispatch, url = socketUrl(), Socket = WebSocket }) {
  let socket = null;
  let name = '';
  let attempt = 0;
  let timer = null;
  let closed = false;

  function open() {
    clearTimeout(timer);
    store.update({ conn: 'connecting' });
    socket = new Socket(url);
    socket.onopen = () => {
      attempt = 0;
      store.update({ conn: 'open' });
      send('hello', { name, token: saved.token(), last_seq: store.get().lastSeq || null });
    };
    socket.onmessage = (event) => {
      let msg = null;
      try {
        msg = JSON.parse(event.data);
      } catch {
        return;
      }
      if (msg && typeof msg.type === 'string') {
        trackSeq(msg);
        dispatch(msg);
      }
    };
    socket.onclose = () => {
      socket = null;
      if (closed) return;
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
      if (!socket) open();
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
