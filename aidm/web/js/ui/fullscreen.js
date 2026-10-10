// Full screen for the phone controller (M18.2): on Android the Fullscreen API hides the browser's own bars, so a
// bottom toolbar (Brave) can no longer cover the page. Only offered where the browser supports it (not iPhone).
import { t } from '../strings.js';
import { h } from './dom.js';

const NS = 'http://www.w3.org/2000/svg';
// Four corner brackets: the usual "expand" glyph, drawn so no font is needed.
const CORNERS = 'M3 8V3h5M16 3h5v5M21 16v5h-5M8 21H3v-5';

export function fullscreenSupported(doc = document) {
  return Boolean(doc.fullscreenEnabled && doc.documentElement.requestFullscreen);
}

export function isFullscreen(doc = document) {
  return Boolean(doc.fullscreenElement);
}

/** Enter or leave full screen; a refusal (no user gesture, policy) is ignored: the page works either way. */
export async function toggleFullscreen(doc = document) {
  try {
    if (isFullscreen(doc)) await doc.exitFullscreen();
    else await doc.documentElement.requestFullscreen({ navigationUI: 'hide' });
  } catch {
    // The browser said no; nothing to undo.
  }
}

function glyph() {
  const svg = document.createElementNS(NS, 'svg');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('aria-hidden', 'true');
  const path = document.createElementNS(NS, 'path');
  path.setAttribute('d', CORNERS);
  svg.append(path);
  return svg;
}

/** Append a full screen toggle to `root` where the browser supports it. `wide` shows a text label. */
export function mountFullscreen(root, { wide = false, testid = 'fullscreen' } = {}) {
  if (!fullscreenSupported()) return () => {};
  const label = h('span', { class: wide ? '' : 'sr-only' }, t('ct.fullscreen'));
  const button = h('button', { type: 'button', class: wide ? 'btn ct-fs-wide' : 'ct-fs', 'data-testid': testid, onclick: () => toggleFullscreen() }, glyph(), label);
  const sync = () => {
    const on = isFullscreen();
    button.setAttribute('aria-pressed', on ? 'true' : 'false');
    label.textContent = t(on ? 'ct.fullscreenExit' : 'ct.fullscreen');
  };
  document.addEventListener('fullscreenchange', sync);
  sync();
  root.append(button);
  return () => {
    document.removeEventListener('fullscreenchange', sync);
    button.remove();
  };
}
