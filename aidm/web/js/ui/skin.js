// M24 dark pixel skin (docs/next/GOAL_UI_REVAMP.md): hands the skin art to CSS as custom properties on
// :root, because CSS may not name art files (Addendum A.5). A key without a real file gives `none`, so a
// framed element falls back to its plain border and the game stays playable on placeholders alone.
import { realAssetUrl } from '../assets.js';

/** The tab colours; each has a ribbon `ui_skin.ribbon-<colour>` and CSS tokens `--<colour>-*`. */
export const SKIN_COLOURS = ['teal', 'crimson', 'blue', 'olive', 'purple', 'grey'];

const SKIN = {
  '--skin-frame': 'ui_skin.frame',
  '--skin-stone': 'ui_skin.stone',
  '--skin-slot': 'ui_skin.slot',
  '--skin-slot-selected': 'ui_skin.slot-selected',
  '--skin-slot-far': 'ui_skin.slot-far',
  '--skin-shield': 'ui_icon.ac-shield',
  '--skin-quill': 'ui_icon.quill',
  '--skin-hourglass': 'ui_icon.hourglass',
  ...Object.fromEntries(SKIN_COLOURS.map((c) => [`--skin-ribbon-${c}`, `ui_skin.ribbon-${c}`])),
};

/** Sets every `--skin-*` property from the loaded manifest (call after loadAssets). */
export function applySkin(root = document.documentElement) {
  for (const [name, key] of Object.entries(SKIN)) {
    const url = realAssetUrl(key);
    root.style.setProperty(name, url ? `url("${url}")` : 'none');
  }
}
