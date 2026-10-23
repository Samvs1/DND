async (cfg) => {
  const { mySeat } = await import('/web/js/state.js');
  const store = window.aidm.store;
  const s = store.get();
  const snap = s.snapshot;
  const st = snap.state;
  const me = cfg.me ?? mySeat(s)?.creature_id;
  const boon = (b) => {
    const [name, helps = ''] = b.split('=');
    return { name, helps: helps ? helps.split(',') : [] };
  };
  const party = st.party.map((c) => ({
    ...c, light: c.id === me && cfg.light ? 'Torch' : '',
    boons: c.id === me ? cfg.boons.map(boon) : [],
  }));
  let combat = st.combat;
  if (combat) {
    const foes = new Set(combat.tokens.filter((tk) => tk.side === 'hostile').map((tk) => tk.zone_id));
    const free = combat.zones.find((z) => !foes.has(z.id)) ?? combat.zones[0];
    const tokens = combat.tokens.map((tk) => (tk.creature_id === me ? { ...tk, zone_id: free.id } : tk));
    const zones = combat.zones.map((z) => {
      const lit = Boolean(cfg.light) && z.id === free.id;
      return { ...z, dark: true, lit, lit_by: lit ? [me] : [] };
    });
    combat = { ...combat, zones, tokens };
  }
  const scene = st.scene ? { ...st.scene, dark: true, lit: cfg.light ? 'Torch' : '', features: cfg.features ?? st.scene.features } : st.scene;
  let sheet = s.sheet ?? { creature_id: me, sheet: { inventory: [] } };
  if (cfg.gear) {
    const torch = { item: 'torch', name: 'Torch', qty: 1, category: 'gear', uses: [{ use_id: 'torch-light', label: 'Light the torch', when: 'dark_place', verb: 'light' }] };
    const use = { item: 'torch', use_id: 'torch-light', name: 'Torch', label: 'Light the torch', cost: 'bonus', target: 'none', qty: 1, effect: 'light_place' };
    sheet = { ...sheet, sheet: { ...sheet.sheet, inventory: [...sheet.sheet.inventory, torch], gear_uses: cfg.light ? [] : [use] } };
  }
  store.update({ snapshot: { ...snap, state: { ...st, party, combat, scene } }, sheet });
  window.__sent = [];
  window.aidm.client.send = (type, body) => { window.__sent.push({ type, ...body }); return true; };
  return me;
}
