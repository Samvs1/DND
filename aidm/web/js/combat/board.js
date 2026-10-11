// The battlefield: zone cards (terrain art, cover / high-ground badges, surfaces, adjacency hints) laid out in
// rows by distance, with the token chips standing in each zone. Zone cards are buttons: they take part in
// aiming (spell zones, jump, push) and otherwise move the active hero.
import { assetUrl } from '../assets.js';
import { t } from '../strings.js';
import { clear, h } from '../ui/dom.js';
import { titleCase } from '../ui/format.js';
import { combatOf, isMyTurn, isRough, moveCost, myCreatureId, neighbours, tokenById, zoneRows } from './model.js';
import { tokenChip } from './tokens.js';

function badges(zone) {
  const out = [];
  if (zone.cover !== 'none') out.push(h('span', { class: 'zbadge cover' }, t(`combat.cover_${zone.cover}`)));
  if (zone.high_ground) out.push(h('span', { class: 'zbadge high' }, t('combat.highGround')));
  if (isRough(zone)) out.push(h('span', { class: 'zbadge rough' }, t('combat.difficult')));
  return out;
}

function surfaces(zone) {
  return zone.surfaces.map((s) =>
    h('span', { class: `zsurface surf-${s.kind}` }, s.rounds_left ? t('combat.surfaceRounds', { name: titleCase(s.kind), n: s.rounds_left }) : t('combat.surfaceLasting', { name: titleCase(s.kind) })),
  );
}

function hints(combat, zone) {
  const near = neighbours(combat, zone.id).map((n) => t('combat.hop', { name: combat.zones.find((z) => z.id === n.id)?.name ?? n.id, feet: n.feet }));
  return near.length ? h('p', { class: 'zadj' }, `${t('combat.nextTo')}: ${near.join(', ')}`) : null;
}

function moveHint(state, combat, zone, myZone) {
  if (!isMyTurn(state) || !myZone || zone.id === myZone) return null;
  const cost = moveCost(combat, myZone, zone.id);
  const left = combat.economy?.movement_left ?? 0;
  if (cost === null) return h('span', { class: 'zmove far' }, t('combat.moveNone'));
  const far = cost > left;
  return h('span', { class: far ? 'zmove far' : 'zmove', 'data-testid': 'move-cost' }, far ? t('combat.moveFar') : t('combat.moveCost', { feet: cost }));
}

function footer(state, ctrl, combat, zone, { here, zoneStep, myZone }) {
  const move = moveHint(state, combat, zone, myZone);
  return h(
    'div',
    { class: 'zone-foot' },
    h(
      'button',
      { type: 'button', class: 'btn btn-small zone-go', 'data-testid': 'zone-go', disabled: !(zoneStep || isMyTurn(state)) || (here && !zoneStep), 'aria-label': zoneStep ? zone.name : t('combat.moveTo', { name: zone.name }), onclick: () => ctrl.pickZone(zone) },
      zoneStep ? zone.name : t('combat.moveTo', { name: zone.name }),
    ),
    move,
  );
}

function zoneCard(state, ctrl, combat, zone) {
  const me = myCreatureId(state);
  const myZone = tokenById(combat, me)?.zone_id ?? null;
  const here = zone.id === myZone;
  const arming = ctrl.ui.arming;
  const zoneStep = arming?.steps[arming.step]?.need === 'zone';
  const party = state.snapshot.state.party;
  const tokens = combat.tokens.filter((tk) => tk.zone_id === zone.id);
  const chips = tokens.map((tk) =>
    tokenChip(tk, {
      hero: party.find((c) => c.id === tk.creature_id),
      zoneName: zone.name,
      flags: { active: tk.creature_id === (combat.active_id ?? combat.turn_of), targeted: tk.creature_id === ctrl.ui.target, mine: tk.creature_id === me, pickable: Boolean(arming) && !zoneStep },
      onPick: (token) => ctrl.pickToken(token),
    }),
  );
  const classes = ['zone', here ? 'here' : '', zoneStep ? 'pickable' : '', tokens.length ? '' : 'empty'].filter(Boolean).join(' ');
  const art = assetUrl(`zone_card.${zone.terrain || 'wilds'}`);
  return h(
    'section',
    { class: classes, 'data-testid': 'zone', 'data-zone': zone.id, 'aria-label': zone.name },
    h('img', { class: 'zone-art', src: art, alt: '', width: 160, height: 90 }),
    h(
      'header',
      { class: 'zone-head' },
      h('h4', {}, zone.name),
      zone.distance_label ? h('span', { class: 'zone-size' }, zone.distance_label) : null,
      here ? h('span', { class: 'tag' }, t('combat.here')) : null,
    ),
    h('div', { class: 'zone-tags' }, ...badges(zone), ...surfaces(zone)),
    h('div', { class: 'zone-tokens' }, ...chips),
    hints(combat, zone),
    ctrl.readOnly ? null : footer(state, ctrl, combat, zone, { here, zoneStep, myZone }),
  );
}

export function mountBoard(root, store, ctrl) {
  const prompt = h('p', { class: 'aim-prompt', role: 'status', 'data-testid': 'aim-prompt' });
  const rows = h('div', { class: 'zones', 'data-testid': 'zones' });
  root.append(prompt, rows);

  let last = '';

  function render(state) {
    const combat = combatOf(state);
    root.hidden = !combat;
    if (!combat) return;
    const me = myCreatureId(state);
    const a = ctrl.ui.arming;
    const key = JSON.stringify([combat, ctrl.ui.target, a?.step, a?.picks, me]);
    if (key === last) return;
    last = key;
    const start = tokenById(combat, me)?.zone_id ?? combat.zones[0].id;
    clear(rows);
    for (const row of zoneRows(combat, start)) {
      rows.append(h('div', { class: 'zone-row' }, ...row.map((id) => zoneCard(state, ctrl, combat, combat.zones.find((z) => z.id === id)))));
    }
    const spec = a?.steps[a.step];
    prompt.hidden = !spec;
    prompt.textContent = typeof spec?.prompt === 'function' ? spec.prompt(a.picks[a.step].length) : (spec?.prompt ?? '');
  }
  render(store.get());
  const stopStore = store.subscribe(render);
  const stopCtrl = ctrl.subscribe(() => render(store.get()));
  return () => {
    stopStore();
    stopCtrl();
  };
}
