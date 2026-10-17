// The ONLY way UI code references art: assetUrl(key). No other module may hard-code image paths.
// The server resolves every manifest key (/api/assets/manifest): the real file when it exists, else a
// generated placeholder SVG. Music and sfx that have no file resolve to '' (silence, no request).

const PLACEHOLDER_PREFIX = '/assets/placeholder/';
const AUDIO_KINDS = new Set(['music', 'sfx']);
const SAFE_SLUG = /[^a-z0-9._-]/g;

let urls = new Map();

export async function loadAssets(fetchFn = fetch) {
  try {
    const response = await fetchFn('/api/assets/manifest');
    if (response.ok) urls = new Map(Object.entries(await response.json()));
  } catch {
    // Offline manifest: every key falls back to its derived placeholder URL below.
  }
}

function splitKey(key) {
  const at = key.indexOf('.');
  return at < 0 ? [key, ''] : [key.slice(0, at), key.slice(at + 1)];
}

function derivedUrl(key) {
  const [kind, slug] = splitKey(key);
  if (AUDIO_KINDS.has(kind)) return '';
  const clean = slug.toLowerCase().replace(SAFE_SLUG, '-').slice(0, 80) || 'unknown';
  return `${PLACEHOLDER_PREFIX}${kind || 'asset'}/${clean}.svg`;
}

function isReal(url) {
  return Boolean(url) && !url.startsWith(PLACEHOLDER_PREFIX);
}

/** The dice sounds' timing table (scripts/gen_dice_sfx.py): throw impacts and the natural 20's beats. */
export const SFX_TIMING_URL = '/static/audio/sfx/dice_timing.json';

/**
 * assetUrl('monster_token.goblin') -> URL string. Pass an array of keys to prefer the first one
 * that has real art (e.g. ['spell_icon.fire-bolt', 'spell_icon.school.fire']); otherwise the first
 * key's placeholder is used. Returns '' for missing audio.
 */
export function assetUrl(keyOrKeys) {
  const keys = Array.isArray(keyOrKeys) ? keyOrKeys : [keyOrKeys];
  for (const key of keys) {
    const url = urls.get(key);
    if (isReal(url)) return url;
  }
  const first = keys[0];
  return urls.get(first) ?? derivedUrl(first);
}

/** The URL of real art for the key(s), or '' while only a placeholder exists (art that is optional). */
export function realAssetUrl(keyOrKeys) {
  const url = assetUrl(keyOrKeys);
  return isReal(url) ? url : '';
}

/** A darkened CSS background of real scene art behind text (e.g. 'scene.defeat'), or '' without art. */
export function shadedBackground(key) {
  const url = realAssetUrl(key);
  return url ? `linear-gradient(rgba(0,0,0,.65), rgba(0,0,0,.8)), url("${url}")` : '';
}

/** True when the key resolves to something playable (audio) or showable (image). */
export function hasAsset(keyOrKeys) {
  return assetUrl(keyOrKeys) !== '';
}
