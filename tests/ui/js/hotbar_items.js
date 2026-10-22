async () => {
  const { itemPopover } = await import('/web/js/combat/hotbar_magic.js');
  const ctrl = { ui: { target: null, chances: {} }, send: () => {}, arm: () => {} };
  const sheet = {
    inventory: [{ item: 'potion-of-healing', name: 'Potion of Healing', qty: 1, category: 'potion' }],
    gear_uses: [
      { item: 'alchemists-fire-flask', use_id: 'alchemists-fire-throw', name: "Alchemist's fire",
        label: 'Throw the fire', cost: 'action', target: 'creature', qty: 2 },
      { item: 'torch', use_id: 'torch-light', name: 'Torch', label: 'Light the torch',
        cost: 'bonus', target: 'none', qty: 1 },
      { item: 'healers-kit', use_id: 'healers-kit-stabilize', name: "Healer's kit",
        label: 'Stabilize a fallen ally', cost: 'action', target: 'ally', qty: 1 },
    ],
  };
  const ctx = { ctrl, me: 'hero', econ: { action: true, bonus_action: true }, sheet, combat: null };
  const box = document.createElement('section');
  box.className = 'hotbar';
  box.style.cssText = 'padding:12px;max-width:390px';
  const aim = document.createElement('p');
  aim.className = 'hb-note';
  aim.textContent = 'Pick a target for Throw the fire';
  const pop = itemPopover(ctx);
  pop.style.maxHeight = 'none';
  box.append(aim, pop);
  document.body.replaceChildren(box);
}
