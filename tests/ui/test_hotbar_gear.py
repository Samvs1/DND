"""M27.6: the hotbar Items section lists the hero's combat gear uses with their cost, aims them
(a creature, a fallen ally, a zone) and sends the `use_item` combat command; a condition an
action can end (burning) gets its own hotbar slot."""

from playwright.sync_api import Browser

from tests.ui.conftest import LiveServer
from tests.ui.table_helpers import PHONE

RENDER = """async () => {
  const { itemPopover } = await import('/web/js/combat/hotbar_magic.js');
  const { moveSlots } = await import('/web/js/combat/hotbar_slots.js');
  const sent = [];
  const armed = [];
  const ctrl = {
    ui: { target: null, chances: {} },
    send: (cmd) => sent.push(cmd),
    arm: (spec) => armed.push(spec),
  };
  const sheet = {
    inventory: [
      { item: 'potion-of-healing', name: 'Potion of Healing', qty: 1, category: 'potion' },
    ],
    gear_uses: [
      { item: 'alchemists-fire-flask', use_id: 'alchemists-fire-throw', name: "Alchemist's fire",
        label: 'Throw the fire', cost: 'action', target: 'creature', qty: 2 },
      { item: 'oil-flask', use_id: 'oil-flask-throw', name: 'Oil', label: 'Throw the oil at a zone',
        cost: 'action', target: 'zone', qty: 1 },
      { item: 'healers-kit', use_id: 'healers-kit-stabilize', name: "Healer's kit",
        label: 'Stabilize a fallen ally', cost: 'action', target: 'ally', qty: 1 },
      { item: 'torch', use_id: 'torch-light', name: 'Torch', label: 'Light this dark place',
        cost: 'bonus', target: 'none', qty: 1 },
    ],
    conditions: [{ name: 'burning', rounds_left: 9, end_label: 'Put out the flames' }],
  };
  const econ = { action: false, bonus_action: true };
  const ctx = { ctrl, me: 'hero', econ, sheet, combat: null };
  const pop = itemPopover(ctx);
  document.body.append(pop);
  const rows = [...pop.querySelectorAll('[data-testid=gear-row]')].map((r) => ({
    use: r.dataset.use,
    cost: r.querySelector('[data-testid=gear-cost]').textContent,
    off: r.querySelector('button').disabled,
    text: r.textContent,
  }));
  pop.querySelector('[data-testid=gear-torch-light]').click();
  ctx.econ = { action: true, bonus_action: true };
  const live = itemPopover(ctx);
  live.querySelector('[data-testid=gear-oil-flask-throw]').click();
  live.querySelector('[data-testid=gear-alchemists-fire-throw]').click();
  const zone = armed[0].build([['b']]);
  const foe = armed[1].build([['gob']]);
  const slot = moveSlots(ctx).find((s) => s.id === 'end-burning');
  slot.run();
  return {
    rows, sent, zone, foe, needs: armed.map((a) => a.steps[0].need), slot: slot.label,
    potions: pop.querySelectorAll('[data-testid=use-potion-of-healing]').length,
  };
}"""


def test_hotbar_items_list_combat_gear_with_its_cost(
    browser: Browser, live_server: LiveServer
) -> None:
    page = browser.new_page(viewport=PHONE)
    page.goto(f"{live_server.base}/play")
    page.wait_for_selector("#join-name")
    out = page.evaluate(RENDER)
    rows = {r["use"]: r for r in out["rows"]}
    assert list(rows) == [
        "alchemists-fire-throw",
        "oil-flask-throw",
        "healers-kit-stabilize",
        "torch-light",
    ]
    assert [rows[u]["cost"] for u in rows] == ["Action", "Action", "Action", "Bonus action"]
    # The action is spent: action uses are off, the bonus-action torch is still ready.
    assert [rows[u]["off"] for u in rows] == [True, True, True, False]
    assert "x2" in rows["alchemists-fire-throw"]["text"]
    assert out["potions"] == 1  # potions stay listed
    torch = {"type": "use_item", "actor_id": "hero", "item": "torch", "use_id": "torch-light"}
    assert out["sent"][0] == torch  # no target needed: sent at once
    assert out["needs"] == ["zone", "creature"]
    assert out["zone"] == {
        "type": "use_item",
        "actor_id": "hero",
        "item": "oil-flask",
        "use_id": "oil-flask-throw",
        "target_zone": "b",
    }
    assert out["foe"]["target_id"] == "gob" and out["foe"]["item"] == "alchemists-fire-flask"
    assert out["slot"] == "Put out the flames"
    assert out["sent"][1] == {
        "type": "end_condition",
        "actor_id": "hero",
        "condition": "burning",
    }
