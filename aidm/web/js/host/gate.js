// Mounts the host panel only while this player is the host, so a non-host never has the panel in the page.
import { mountHost } from './host.js';

export function mountHostGate(root, ctx) {
  let unmount = null;
  function render(state) {
    if (state.me.isHost && !unmount) unmount = mountHost(root, ctx);
    else if (!state.me.isHost && unmount) {
      unmount();
      unmount = null;
    }
  }
  render(ctx.store.get());
  const stop = ctx.store.subscribe(render);
  return () => {
    stop();
    if (unmount) unmount();
  };
}
