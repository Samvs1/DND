// The top of every phone tab (M24, docs/next/GOAL_UI_REVAMP.md): a ribbon in the tab's colour over a framed
// picture. Play shows the place (its region banner) or, in a fight, the zone the hero stands in with the round,
// whose turn it is and the turn clock; Hero the hero's portrait; Journal, Scribe and More their scenes. It sets
// body[data-sec], so the whole controller (tab bar, buttons, dialogs) takes the tab's colour. The full screen
// button sits on the picture.
import { assetUrl } from '../assets.js';
import { actingToken, combatOf, heroActing, isMyTurn, myCreatureId, tokenById } from '../combat/model.js';
import { portraitKeys } from '../table/party.js';
import { myHero, publicState } from '../table/lookup.js';
import { t } from '../strings.js';
import { clockText, everySecond } from '../ui/countdown.js';
import { h } from '../ui/dom.js';
import { clamp, titleCase } from '../ui/format.js';
import { mountFullscreen } from '../ui/fullscreen.js';
import { TABS } from './tabs.js';
import { zoneDimmed } from '../table/light.js';

const FIXED = {
  hero: { sec: 'blue', ribbon: 'ct.top_hero', art: 'portrait.npc.commoner' },
  journal: { sec: 'olive', ribbon: 'ct.top_journal', art: 'scene.journal' },
  scribe: { sec: 'purple', ribbon: 'ct.top_scribe', art: 'scene.scribe' },
  more: { sec: 'grey', ribbon: 'ct.top_more', art: 'scene.more' },
};

function fightTop(state, combat) {
  const mine = tokenById(combat, myCreatureId(state));
  const zone = combat.zones?.find((z) => z.id === mine?.zone_id) ?? combat.zones?.[0];
  const who = isMyTurn(state) ? t('ct.top_yourTurn') : actingToken(combat)?.name ?? '';
  return {
    tab: 'play',
    sec: 'crimson',
    ribbon: who ? t('ct.top_round', { n: combat.round, who }) : t('combat.round', { n: combat.round }),
    art: zone ? [`zone_hex.${zone.id}`, `zone_card.${zone.terrain || 'wilds'}`] : 'region_banner.tier1',
    caption: zone?.name ?? '',
    dark: zoneDimmed(zone),
  };
}

/** {tab, sec, ribbon, art, caption}: what the top of the current tab shows. */
export function topOf(state) {
  const tab = TABS.includes(state.ctab) ? state.ctab : 'play';
  if (tab === 'play') {
    const combat = combatOf(state);
    if (combat) return fightTop(state, combat);
    const view = publicState(state);
    const tier = `region_banner.tier${clamp(view?.region_tier || 1, 1, 3)}`;
    const terrain = view?.scene?.terrain;
    return { tab, sec: 'teal', ribbon: view?.scene?.name || t('ct.tab_play'), art: terrain ? [`region_banner.${terrain}`, tier] : tier, caption: '', dark: Boolean(view?.scene?.dark) };
  }
  const fixed = FIXED[tab];
  const hero = myHero(state);
  return { tab, sec: fixed.sec, ribbon: t(fixed.ribbon), art: tab === 'hero' && hero ? portraitKeys(hero) : fixed.art, caption: tab === 'hero' ? heroCaption(state) : '' };
}

/** "High Elf Wizard - Sage" on the Hero picture (M25): who the hero is, said once on the tab. */
function heroCaption(state) {
  const sheet = state.sheet?.sheet;
  if (!sheet) return '';
  const who = `${titleCase(sheet.subrace || sheet.race)} ${titleCase(sheet.class_index)}`;
  return sheet.background ? t('ct.heroCaption', { who, background: titleCase(sheet.background) }) : who;
}

/** The turn clock shown on the fight picture: only while a hero's turn is timed. */
function fightClock(state) {
  const combat = combatOf(state);
  return combat && heroActing(combat) ? clockText(state.turnEndsAt) : '';
}

export function mountTopper(root, store) {
  const words = h('span', { 'data-testid': 'ct-ribbon-text' });
  const badge = h('span', { class: 'dark-badge', hidden: true, 'data-testid': 'dark-badge' }, t('light.dark'));
  const ribbon = h('div', { class: 'ct-ribbon' }, words, badge);
  const img = h('img', { class: 'ct-pic-art', alt: '' });
  const place = h('span', { class: 'ct-pic-place' });
  const clock = h('span', { class: 'ct-pic-clock', 'data-testid': 'ct-pic-clock' });
  const caption = h('p', { class: 'ct-pic-cap' }, place, clock);
  const pic = h('div', { class: 'ct-pic' }, img, caption);
  root.append(ribbon, pic);
  let last = '';

  function tick(state) {
    const text = fightClock(state);
    if (clock.textContent !== text) clock.textContent = text;
    caption.hidden = !place.textContent && !text;
  }

  function render(state) {
    const top = topOf(state);
    const key = JSON.stringify(top);
    if (key !== last) {
      last = key;
      document.body.dataset.sec = top.sec;
      words.textContent = top.ribbon;
      const src = assetUrl(top.art);
      if (img.getAttribute('src') !== src) img.src = src;
      img.dataset.fit = top.tab === 'play' && top.sec === 'crimson' ? 'zone' : top.tab;
      place.textContent = top.caption;
      badge.hidden = !top.dark;
      pic.classList.toggle('is-dark', Boolean(top.dark));
    }
    tick(state);
  }
  render(store.get());
  const stop = store.subscribe(render);
  const stopTick = everySecond(store, tick);
  const stopFs = mountFullscreen(pic); // M18.2: hides the browser's bars on Android
  return () => {
    stop();
    stopTick();
    stopFs();
    delete document.body.dataset.sec;
  };
}
