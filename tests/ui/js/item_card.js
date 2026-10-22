async (opts) => {
  const { renderInventory } = await import('/web/js/sheet/inventory.js');
  const sent = [];
  const sheet = {
    id: 'h', name: 'Mira', gold: 12, keepsakes: [],
    inventory: [
      { item: 'torch', name: 'Torch', qty: 2, category: 'gear', weight: 1, value_gp: 0.01,
        uses: [{ use_id: 'torch-light', label: 'Light the torch', when: 'dark_place', verb: 'light' }] },
      { item: 'crowbar', name: 'Crowbar', qty: 1, category: 'gear', weight: 5, value_gp: 2,
        uses: [{ use_id: 'crowbar-force', label: 'Force this open with the crowbar', when: 'locked', verb: 'force' }] },
    ],
  };
  const scene = { dark: opts.dark, features: [{ id: 'f1', name: 'Cellar door', locked: 'medium' }] };
  const box = document.createElement('div');
  box.className = 'sheet-body';
  box.style.cssText = 'padding:12px;max-width:390px';
  const client = { send: (type, body) => sent.push({ type, ...body }) };
  box.append(...renderInventory(sheet, { client, camp: 0, locked: false, party: [], npcs: [], here: { scene, light: '', blocked: false } }).filter(Boolean));
  document.body.replaceChildren(box);
  window.__sent = sent;
}
