// The Scribe's texts for the phone: GET /api/scribe/lines, fetched once and cached. His refusals are
// text only (no audio); the phone maps a refusal code to the group below and shows one of its lines.
import { t } from '../strings.js';

export const REFUSAL_GROUP = {
  scribe_in_combat: 'refuse_combat',
  scribe_no_funds: 'refuse_funds',
  scribe_none_fallen: 'none_fallen',
  scribe_not_fallen: 'not_yet',
};

let cache = null;

/** The cached list [{id, group, text, audio_url}]; [] when the request fails (the fallback line is used). */
export async function loadScribeLines(fetchFn = fetch) {
  if (cache) return cache;
  try {
    const response = await fetchFn('/api/scribe/lines');
    if (response.ok) cache = await response.json();
  } catch {
    // Offline: the in-fiction fallback line below is shown instead.
  }
  return cache ?? [];
}

/** One text of a group (the first, stable for tests and screenshots), or the fallback line. */
export function groupText(lines, group) {
  return lines.find((line) => line.group === group)?.text ?? t('scribe.fallbackLine');
}

export function refusalText(lines, code) {
  return groupText(lines, REFUSAL_GROUP[code] ?? 'refuse_combat');
}
