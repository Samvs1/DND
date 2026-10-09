// The turn countdown (M15.1 playtest): the server sends the seconds left on the running turn timer
// (`floor.seconds_left` in every snapshot and floor_state, `turn_prompt.seconds`); the client counts down
// from the moment it got them. No timer (Off, a solo table) means no countdown.

/** The local time (ms) the turn runs out, or null when no timer runs. */
export function turnEndsAt(seconds, now = Date.now()) {
  return typeof seconds === 'number' ? now + seconds * 1000 : null;
}

/** "m:ss" left until endsAt, or '' when no timer runs. */
export function clockText(endsAt, now = Date.now()) {
  if (endsAt == null) return '';
  const left = Math.max(0, Math.ceil((endsAt - now) / 1000));
  return `${Math.floor(left / 60)}:${String(left % 60).padStart(2, '0')}`;
}

/** Calls fn once a second while a countdown runs; returns the stop function. */
export function everySecond(store, fn) {
  const id = setInterval(() => {
    if (store.get().turnEndsAt != null) fn(store.get());
  }, 1000);
  return () => clearInterval(id);
}
