// Small display helpers shared by views (no user-visible words here, only formatting).

/** "half-elf" -> "Half Elf". */
export function titleCase(slug) {
  // M29.7c R10: a lone "s" word was a possessive ("mord-s-coin" -> "Mord's Coin").
  return String(slug ?? '')
    .replace(/([a-z0-9])-s(?=-|$)/g, "$1's")
    .split('-')
    .map((w) => (w ? w[0].toUpperCase() + w.slice(1) : w))
    .join(' ');
}

export function clamp(value, low, high) {
  return Math.min(high, Math.max(low, value));
}
