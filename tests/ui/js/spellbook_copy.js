async () => {
  const { renderSpellbook } = await import('/web/js/sheet/spellbook.js');
  const sheet = {
    spellcasting: { ability: 'int', save_dc: 13, attack_bonus: 5, prepared_limit: 4, cantrips: [], levels: [] },
    concentrating_on: null,
    scroll_copies: [
      { item: 'scroll-of-color-spray', spell: 'color-spray', name: 'Color Spray', level: 1, cost: 50, affordable: true },
      { item: 'scroll-of-misty-step', spell: 'misty-step', name: 'Misty Step', level: 2, cost: 100, affordable: false },
    ],
  };
  const box = document.createElement('div');
  box.className = 'sheet-body';
  box.style.cssText = 'padding:12px;max-width:390px';
  box.append(...renderSpellbook(sheet, { client: { send: () => {} }, locked: false }));
  document.body.replaceChildren(box);
}
