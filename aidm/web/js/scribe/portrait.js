// Which picture the Scribe wears for a line group: the welcome pose, the writing pose for a revive, else
// the seated owner art. Always resolves (placeholder SVG while a pose has no file).
import { assetUrl, realAssetUrl } from '../assets.js';

const SEATED = 'portrait.scribe.seated';

export function portraitKey(group) {
  if (typeof group === 'string' && group.startsWith('welcome')) return 'portrait.scribe.welcome';
  if (group === 'revive') return 'portrait.scribe.rewrite';
  return SEATED;
}

export function portraitSrc(group) {
  return realAssetUrl([portraitKey(group), SEATED]) || assetUrl(SEATED);
}
