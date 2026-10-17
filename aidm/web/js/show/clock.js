// The shows' clock (M26.6): every wait and animation is scaled by the pacer's `scale` (backlog, reduced
// motion, tests) and ends at once when the show is skipped (the pacer's abort signal).
import { reducedMotion } from '../settings/model.js';

export function showClock(scale, signal) {
  const skipped = () => Boolean(signal?.aborted);
  const still = reducedMotion();
  return {
    scale,
    skipped,
    still,
    /** Resolve after `ms` (scaled), or as soon as the show is skipped. */
    wait(ms) {
      return new Promise((resolve) => {
        if (skipped()) return resolve();
        const id = setTimeout(done, ms * scale);
        function done() {
          clearTimeout(id);
          signal?.removeEventListener('abort', done);
          resolve();
        }
        signal?.addEventListener('abort', done, { once: true });
      });
    },
    /** A setTimeout on the show's time scale (the flicker uses it). */
    later(fn, ms) {
      return setTimeout(fn, ms * scale);
    },
    /** Web Animation of `ms` (scaled) that jumps to its end on skip; reduced motion jumps at once. */
    animate(el, frames, ms, { easing = 'linear', delay = 0, always = false } = {}) {
      if (!el.animate || ((still || skipped()) && !always)) {
        const last = frames[frames.length - 1];
        for (const [key, value] of Object.entries(last)) if (key !== 'offset') el.style[key] = value;
        return Promise.resolve();
      }
      const quick = skipped() ? 0.3 : 1; // a skipped show still lands its verdict, briskly
      const anim = el.animate(frames, { duration: Math.max(1, ms * scale * quick), delay: delay * scale * quick, easing, fill: 'forwards' });
      const finish = () => anim.finish();
      signal?.addEventListener('abort', finish, { once: true });
      return anim.finished.catch(() => {}).finally(() => signal?.removeEventListener('abort', finish));
    },
  };
}
