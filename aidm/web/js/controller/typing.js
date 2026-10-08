// "Is typing" signal for the action box: `typing {on:true}` when text appears and again every ~3 s while it
// keeps changing (the server expires it after 8 s), `{on:false}` on blur, send or clear.

const REPEAT_MS = 3000;

export function createTyping(client, now = Date.now) {
  let on = false;
  let last = 0;
  return {
    change(text) {
      if (!text.trim()) return this.off();
      const at = now();
      if (on && at - last < REPEAT_MS) return undefined;
      on = true;
      last = at;
      return client.send('typing', { on: true });
    },
    off() {
      if (!on) return undefined;
      on = false;
      return client.send('typing', { on: false });
    },
  };
}
