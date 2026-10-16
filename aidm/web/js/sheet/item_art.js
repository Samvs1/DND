// Item pictures (M25): the item's own icon, then a look-alike for its kind (a ranged weapon shows a bow, never a
// sword), then its category's icon. assetUrl prefers the first key with real art.
import { assetUrl } from '../assets.js';

const RANGED = /bow|crossbow|sling|dart|javelin/;

export function itemArt(item, { category = '', ranged = false } = {}) {
  const keys = [`item_icon.${item}`];
  if (ranged || RANGED.test(item)) keys.push('item_icon.shortbow');
  keys.push(`item_icon.${category || 'gear'}`);
  return assetUrl(keys);
}
