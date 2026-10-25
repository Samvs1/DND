// Light and darkness on the screen and the phone (M27.8, docs/next/GOAL_ITEMS.md "What players see"): small shared
// pieces (the darkvision eye, the "Torch lit" chip, zone state) so every view says it the same way. Art only
// through assetUrl (placeholders until the M10 pipeline draws them).
import { assetUrl } from '../assets.js';
import { t } from '../strings.js';
import { h } from '../ui/dom.js';

/** The eye icon of a hero with darkvision, else null. */
export function eye(creature, cls = 'eye') {
  if (!creature?.darkvision) return null;
  const label = t('light.darkvision', { feet: creature.darkvision });
  return h('span', { class: cls, 'data-testid': 'darkvision-eye', title: label, role: 'img', 'aria-label': label }, h('img', { src: assetUrl('zone_icon.darkvision'), alt: '', width: 16, height: 16 }));
}

/** "Torch lit" on the bearer, else null. */
export function lightChip(creature) {
  if (!creature?.light) return null;
  const label = t('light.litChip', { name: creature.light });
  return h('span', { class: 'light-chip', 'data-testid': 'light-chip', title: t('light.carries', { hero: creature.name, name: creature.light.toLowerCase() }) }, h('img', { src: assetUrl('zone_icon.lit'), alt: '', width: 14, height: 14 }), label);
}

/** The zone is a dark one that no light reaches (dimmed, attacks into it at disadvantage). */
export const zoneDimmed = (zone) => Boolean(zone?.dark && !zone.lit);

/** The zone is in a dark place and a light reaches it (it glows). */
export const zoneGlows = (zone) => Boolean(zone?.dark && zone.lit);

/** "Put out light": free on any turn, sent as the menu's own label (M36.10b; MenuAct in M36.11). */
export function putOutButton(client, cls = 'btn btn-small') {
  return h('button', { type: 'button', class: `${cls} ct-putout`, 'data-testid': 'put-out-light', title: t('light.putOutTip'), onclick: () => client.send('submit_action', { text: 'Put out your light' }) }, t('light.putOut'));
}
