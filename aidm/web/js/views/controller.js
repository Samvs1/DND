// Phone controller (/play once the adventure runs), top to bottom (M24, docs/next/GOAL_UI_REVAMP.md): the tab's
// ribbon and picture, the content (an open vote, a giver's quest offer (M23.4) and the finale choice (M23.9) as
// sticky cards at its top, then the current tab's pane), the hero strip, and the five tabs (Play, Hero, Journal,
// Scribe, More) at the very bottom (owner choice; supersedes M18.2's tabs on top: full screen answers a browser
// toolbar laid over the page). Dialogs for shop, host, settings and the manual. The shared story, party and board
// live on /screen.
import { createController } from '../combat/controller.js';
import { mountDefeatPanel } from '../controller/defeat.js';
import { mountJournalTab } from '../controller/journal.js';
import { mountMore } from '../controller/more.js';
import { mountPlay } from '../controller/play.js';
import { mountScribeTab } from '../controller/scribe.js';
import { mountVictoryPanel } from '../controller/victory.js';
import { mountStrip } from '../controller/strip.js';
import { mountTabs } from '../controller/tabs.js';
import { mountTopper } from '../controller/topper.js';
import { mountQuestToast } from '../controller/quest_toast.js';
import { mountToast } from '../controller/toast.js';
import { mountRollCard } from '../controller/rollcard.js';
import { mountHostGate } from '../host/gate.js';
import { mountManualPanel } from '../manual/panel.js';
import { mountSettings } from '../settings/settings.js';
import { mountSheet } from '../sheet/drawer.js';
import { mountLevelUp } from '../sheet/levelup.js';
import { mountSheetSync } from '../sheet/sync.js';
import { mountShop } from '../shop/shop.js';
import { mountConfirm, mountOffer } from '../table/dialogs.js';
import { mountNotices } from '../table/notices.js';
import { mountFinale } from '../table/finale.js';
import { mountQuestOffer } from '../table/quest_offer.js';
import { mountVote } from '../table/vote.js';
import { t } from '../strings.js';
import { h } from '../ui/dom.js';
import { TABS } from '../controller/tabs.js';

export function mountController(root, ctx) {
  const { store } = ctx;
  document.body.classList.add('is-controller');
  const top = h('header', { class: 'ct-top', 'data-testid': 'ct-top' });
  const strip = h('div', { class: 'ct-strip', 'data-testid': 'strip' });
  const levelSlot = h('div', { class: 'ct-levelup' });
  const notices = h('div', { class: 'ct-notices' });
  const panes = Object.fromEntries(TABS.map((id) => [id, h('section', { class: `ct-pane ct-pane-${id}`, id: `ct-pane-${id}`, role: 'tabpanel', 'aria-labelledby': `ct-tab-${id}`, 'data-testid': `pane-${id}` })]));
  const nav = h('nav', { class: 'ct-tabs', role: 'tablist', 'aria-label': t('ct.tabs'), 'data-testid': 'ct-tabs' });
  const sheetSlot = h('div', { class: 'ct-sheet' });
  const main = h('main', { class: 'ct-main' }, sheetSlot, notices, levelSlot, ...Object.values(panes));
  const toastSlot = h('div', { class: 'ct-toasts' });
  const dialogs = h('div', { class: 'ct-dialogs' });
  root.append(h('div', { class: 'ct', 'data-testid': 'controller' }, top, main, strip, nav), toastSlot, dialogs);
  const ctrl = createController(ctx);

  const stops = [
    () => ctrl.stop(),
    mountSheetSync(ctx),
    mountTopper(top, store),
    mountStrip(strip, store),
    mountTabs(nav, panes, store),
    ...mountPlay(panes.play, ctx, ctrl),
    mountSheet(panes.hero, ctx, (state) => state.ctab === 'hero'),
    mountJournalTab(panes.journal, ctx),
    mountScribeTab(panes.scribe, ctx, toastSlot),
    mountMore(panes.more, ctx),
    mountNotices(notices, store),
    mountLevelUp(levelSlot, ctx),
    mountVote(sheetSlot, ctx),
    mountQuestOffer(sheetSlot, ctx),
    mountFinale(sheetSlot, ctx),
    mountToast(toastSlot, ctx),
    mountRollCard(toastSlot, ctx), // M26.6: my stage roll, in time with the TV
    mountQuestToast(toastSlot, ctx),
    mountConfirm(dialogs, ctx),
    mountOffer(dialogs, ctx),
    mountShop(dialogs, ctx),
    mountHostGate(dialogs, ctx),
    mountSettings(dialogs, ctx),
    mountManualPanel(dialogs, ctx),
    mountDefeatPanel(root, ctx),
    mountVictoryPanel(root, ctx),
  ];
  return () => {
    stops.forEach((stop) => stop());
    document.body.classList.remove('is-controller');
  };
}
