// The battlefield on the shared screen (M21): the zones as pointy-top hexes that fit into each other. Touching
// hexes are linked zones (one hop, the edge's feet). Each hex shows its terrain art, name, marks (cover, high
// ground, rough ground, surfaces) as icons with a short label when there is room, and the creatures standing in
// it. A legend under the map names the marks in this fight and the distance between touching zones.
// Read-only: the phones move and aim through their own lists (controller/moves.js, controller/targets.js).
import { assetUrl, realAssetUrl } from '../assets.js';
import { t } from '../strings.js';
import { clear, h } from '../ui/dom.js';
import { titleCase } from '../ui/format.js';
import { hexLayout } from './hexmap.js';
import { combatOf } from './model.js';
import { tokenChip } from './tokens.js';

const COVER_ICON = { half: 'zone_icon.cover-half', three_quarters: 'zone_icon.cover-three-quarters' };

/** The marks of a zone: [{key, kind, label}] in a fixed order (cover, high ground, rough, surfaces). */
export function zoneMarks(zone) {
  const out = [];
  if (zone.cover !== 'none') out.push({ key: COVER_ICON[zone.cover], kind: `cover-${zone.cover}`, label: t(`combat.cover_${zone.cover}`) });
  if (zone.high_ground) out.push({ key: 'zone_icon.high-ground', kind: 'high', label: t('combat.highGround') });
  if (zone.rough) out.push({ key: 'zone_icon.rough', kind: 'rough', label: t('combat.difficult') });
  for (const s of zone.surfaces) {
    const name = titleCase(s.kind);
    const label = s.rounds_left ? t('combat.surfaceRounds', { name, n: s.rounds_left }) : t('combat.surfaceLasting', { name });
    out.push({ key: `surface_icon.${s.kind}`, kind: `surf surf-${s.kind}`, label, rounds: s.rounds_left ?? null });
  }
  return out;
}

function markNode(mark) {
  const art = realAssetUrl(mark.key);
  return h(
    'li',
    { class: `hmark ${mark.kind}`, title: mark.label, 'data-testid': 'hex-mark' },
    art ? h('img', { class: 'hm-icon', src: art, alt: '', width: 32, height: 32 }) : h('span', { class: 'hm-dot', 'aria-hidden': 'true' }),
    h('span', { class: 'hm-label' }, mark.label),
  );
}

function hexNode(state, combat, zone, box) {
  const party = state.snapshot.state.party;
  const acting = combat.active_id ?? combat.turn_of;
  const tokens = combat.tokens.filter((tk) => tk.zone_id === zone.id);
  const chips = tokens.map((tk) =>
    tokenChip(tk, { hero: party.find((c) => c.id === tk.creature_id), zoneName: zone.name, flags: { active: tk.creature_id === acting }, onPick: () => {} }),
  );
  const here = tokens.some((tk) => tk.creature_id === acting);
  const marks = zoneMarks(zone);
  const node = h(
    'section',
    { class: here ? 'hex acting' : 'hex', 'data-testid': 'zone', 'data-zone': zone.id, 'data-q': zone.q, 'data-r': zone.r, 'aria-label': zone.name },
    h('div', { class: 'hex-frame', 'aria-hidden': 'true' }),
    h('div', { class: 'hex-fill', 'aria-hidden': 'true' }, h('img', { class: 'hex-art', src: assetUrl([`zone_hex.${zone.id}`, `zone_card.${zone.terrain || 'wilds'}`]), alt: '' })),
    h('h4', { class: 'hex-name' }, zone.name),
    marks.length ? h('ul', { class: 'hex-marks', 'aria-label': marks.map((m) => m.label).join(', ') }, ...marks.map(markNode)) : null,
    h('div', { class: 'hex-tokens' }, ...chips),
    zone.distance_label ? h('p', { class: 'hex-size' }, zone.distance_label) : null,
  );
  Object.assign(node.style, { left: `${box.left}%`, top: `${box.top}%`, width: `${box.width}%`, height: `${box.height}%` });
  return node;
}

function legend(combat) {
  const seen = new Map();
  for (const zone of combat.zones) for (const mark of zoneMarks(zone)) seen.set(mark.kind, { ...mark, label: mark.label.replace(/ \(\d+\)$/, '') });
  const feet = combat.edges[0]?.feet;
  return h(
    'div',
    { class: 'hex-legend', 'data-testid': 'hex-legend' },
    feet ? h('span', { class: 'hl-hop' }, t('combat.hexHop', { feet })) : null,
    h('ul', { class: 'hl-marks' }, ...[...seen.values()].map(markNode)),
  );
}

export function mountBoard(root, store) {
  const map = h('div', { class: 'hexmap', 'data-testid': 'hexmap' });
  const foot = h('div', { class: 'hexmap-foot' });
  root.append(map, foot);
  let last = '';

  function render(state) {
    const combat = combatOf(state);
    root.hidden = !combat;
    if (!combat) return;
    const key = JSON.stringify(combat);
    if (key === last) return;
    last = key;
    const { ratio, cells } = hexLayout(combat.zones);
    const stage = h('div', { class: 'hex-stage' }, ...combat.zones.map((z) => hexNode(state, combat, z, cells.get(z.id))));
    stage.style.setProperty('--ratio', ratio.toFixed(4));
    clear(map);
    map.append(stage);
    clear(foot);
    foot.append(legend(combat));
  }
  render(store.get());
  return store.subscribe(render);
}
