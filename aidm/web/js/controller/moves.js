// The Move list of the Play tab (M19.4, owner playtest: the old "Move to" box sat collapsed under the targets,
// below the long hotbar, so only Jump was found). On MY turn it sits right under the Now card: one chip per zone
// with its distance and the board's facts (cover, high ground, rough ground, surfaces). A zone out of reach says
// what it needs ("Dash first" while the Dash action is still free, else "too far this turn"). A tap does what
// tapping the zone on the board did (`ctrl.pickZone`): a move, or the zone of an armed spell. While an area spell is
// armed each chip says who it would catch, allies marked, or that the cone or line cannot reach it (M29.7d).
import { areaCaught, combatOf, isMyTurn, isRough, moveCost, tokenById } from '../combat/model.js';
import { t } from '../strings.js';
import { clear, h } from '../ui/dom.js';
import { titleCase } from '../ui/format.js';
import { tipButton } from '../ui/tip.js';

const COVER_TIP = { half: 'word:half-cover', three_quarters: 'word:three-quarters-cover' };

/** The facts of a zone: [{text, tip}], where tip is the key of its '?' tip. */
function zoneBadges(zone) {
  const out = [];
  if (zone.cover !== 'none') out.push({ text: t(`combat.cover_${zone.cover}`), tip: COVER_TIP[zone.cover] });
  if (zone.high_ground) out.push({ text: t('combat.highGround'), tip: 'word:high-ground' });
  if (isRough(zone)) out.push({ text: t('combat.difficult'), tip: 'word:rough-ground' });
  if (zone.dark) out.push({ text: zone.lit ? t('light.lit') : t('light.dark'), tip: zone.lit ? 'word:lit' : 'word:dark' });
  for (const s of zone.surfaces) out.push({ text: s.rounds_left ? t('combat.surfaceRounds', { name: titleCase(s.kind), n: s.rounds_left }) : t('combat.surfaceLasting', { name: titleCase(s.kind) }), tip: `surface:${s.kind}` });
  return out;
}

/** ONE '?' per chip, in a column to the right of it (never over the chip); its tip lists every fact of the zone. */
function badgeTips(facts) {
  return h('div', { class: 'ct-t-tips', 'aria-label': t('ct.zoneFacts') }, tipButton(facts.map((f) => f.tip), facts.map((f) => f.text).join(', '), '', true));
}

/** What a zone needs, or '' when it can be walked to now. */
export function reachNote(feet, economy) {
  if (feet === null || feet <= economy.movement_left) return '';
  return economy.action && !economy.dashed ? t('ct.moveDashFirst') : t('ct.moveTooFar');
}

/** The "Hits ..." line of a zone chip while an area spell is armed (allies marked), or "Out of reach". */
function caughtNote(combat, area, zone) {
  const caught = areaCaught(combat, area, zone.id);
  if (caught === null) return h('span', { class: 'ct-t-need', 'data-testid': 'zone-caught' }, t('ct.areaOut'));
  if (!caught.length) return h('span', { class: 'ct-t-need', 'data-testid': 'zone-caught' }, t('ct.areaNobody'));
  const names = caught.map((tk) => (tk.side === 'party' ? t('ct.areaAlly', { name: tk.name }) : tk.name)).join(', ');
  const ally = caught.some((tk) => tk.side === 'party');
  return h('span', { class: `ct-t-need${ally ? ' ct-t-ally' : ''}`, 'data-testid': 'zone-caught', 'data-ally': ally ? '1' : '0' }, t('ct.areaHits', { names }));
}

function zoneChip(zone, { combat, mine, ctrl, arming, area }) {
  const here = zone.id === mine?.zone_id;
  const feet = mine && !here ? moveCost(combat, mine.zone_id, zone.id) : null;
  const economy = combat.economy ?? { movement_left: 0, action: false, dashed: true };
  const note = here ? '' : reachNote(feet, economy);
  const reachable = !here && feet !== null && !note;
  const label = here ? t('ct.zoneHere', { zone: zone.name }) : feet === null ? zone.name : t('ct.zoneAt', { zone: zone.name, feet });
  const facts = zoneBadges(zone);
  const button = h(
    'button',
    { type: 'button', class: `ct-target place${here ? ' here' : ''}`, disabled: !reachable && !arming, 'data-testid': 'zone-chip', 'data-zone': zone.id, onclick: () => ctrl.pickZone(zone) },
    h('span', { class: 'ct-t-zone' }, label),
    note && !arming ? h('span', { class: 'ct-t-need', 'data-testid': 'zone-need' }, note) : null,
    arming && area ? caughtNote(combat, area, zone) : null,
    facts.length ? h('span', { class: 'ct-t-badges' }, ...facts.map((f) => h('span', { class: 'ct-zb', 'data-testid': 'zone-badge' }, f.text))) : null,
  );
  return facts.length ? h('div', { class: 'ct-place-cell' }, button, badgeTips(facts)) : button;
}

export function mountMoves(root, { store }, ctrl) {
  const box = h('section', { class: 'ct-moves', hidden: true, 'aria-label': t('ct.places'), 'data-testid': 'places' });
  root.append(box);
  let last = '';

  function render(state) {
    const combat = combatOf(state);
    const show = Boolean(combat) && isMyTurn(state);
    box.hidden = !show;
    if (!show) {
      last = '';
      return;
    }
    const spec = ctrl.ui.arming?.steps[ctrl.ui.arming.step];
    const arming = spec?.need === 'zone';
    const area = arming ? (spec.area ?? null) : null;
    const key = JSON.stringify([combat.tokens, combat.zones, combat.economy, arming, area]);
    if (key === last) return;
    last = key;
    const mine = tokenById(combat, ctrl.actor());
    const left = combat.economy?.movement_left ?? 0;
    clear(box);
    box.append(
      h('h3', { class: 'side-h' }, arming ? t('ct.placesPick') : t('ct.placesLeft', { feet: left })),
      h('div', { class: 'ct-places' }, ...combat.zones.map((zone) => zoneChip(zone, { combat, mine, ctrl, arming, area }))),
    );
  }
  render(store.get());
  const stopStore = store.subscribe(render);
  const stopCtrl = ctrl.subscribe(() => render(store.get()));
  return () => {
    stopStore();
    stopCtrl();
  };
}
