"""M27.7: the Spellbook tab lists the scrolls a wizard can copy with their cost; Copy sends
`copy_scroll`, and is off in a fight or when the gold is short."""

from playwright.sync_api import Browser

from tests.ui.conftest import LiveServer
from tests.ui.table_helpers import PHONE

RENDER = """async () => {
  const { renderSpellbook } = await import('/web/js/sheet/spellbook.js');
  const sent = [];
  const client = { send: (type, body) => sent.push({ type, ...body }) };
  const sheet = {
    spellcasting: {
      ability: 'int', save_dc: 13, attack_bonus: 5, prepared_limit: 4, cantrips: [], levels: [],
    },
    concentrating_on: null,
    scroll_copies: [
      { item: 'scroll-of-color-spray', spell: 'color-spray', name: 'Color Spray', level: 1,
        cost: 50, affordable: true },
      { item: 'scroll-of-misty-step', spell: 'misty-step', name: 'Misty Step', level: 2,
        cost: 100, affordable: false },
    ],
  };
  const box = document.createElement('div');
  box.append(...renderSpellbook(sheet, { client, locked: false }));
  document.body.append(box);
  const lines = [...box.querySelectorAll('[data-testid=copy-line]')].map((li) => ({
    item: li.dataset.item, text: li.textContent, off: li.querySelector('button').disabled,
  }));
  box.querySelector('[data-testid="copy-scroll-of-color-spray"]').click();
  const fight = document.createElement('div');
  fight.append(...renderSpellbook(sheet, { client, locked: true }));
  const buttons = [...fight.querySelectorAll('[data-testid=copy-line] button')];
  const offInFight = buttons.every((b) => b.disabled);
  const none = renderSpellbook({ ...sheet, scroll_copies: [] }, { client, locked: false });
  const hint = fight.querySelector('[data-testid=sh-copy] .hint').textContent;
  const emptyHasNoSection = !none.some((n) => n.dataset && n.dataset.testid === 'sh-copy');
  return { lines, sent, offInFight, hint, emptyHasNoSection };
}"""


def test_spellbook_tab_copies_a_scroll(browser: Browser, live_server: LiveServer) -> None:
    page = browser.new_page(viewport=PHONE)
    page.goto(f"{live_server.base}/play")
    page.wait_for_selector("#join-name")
    out = page.evaluate(RENDER)
    lines = {line["item"]: line for line in out["lines"]}
    assert list(lines) == ["scroll-of-color-spray", "scroll-of-misty-step"]
    assert "50 gold" in lines["scroll-of-color-spray"]["text"]
    assert "100 gold" in lines["scroll-of-misty-step"]["text"]
    assert [lines[i]["off"] for i in lines] == [False, True]  # the gold is short for Misty Step
    assert out["sent"] == [{"type": "copy_scroll", "item_id": "scroll-of-color-spray"}]
    assert out["offInFight"] and "fight" in out["hint"]
    assert out["emptyHasNoSection"]
    assert page.locator("[data-testid=copy-why]").all_inner_texts() == ["Need 100 gold"]
