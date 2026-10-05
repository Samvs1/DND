// Small display helpers shared by views (no user-visible words here, only formatting).

/** "half-elf" -> "Half Elf". */
export function titleCase(slug) {
  return String(slug ?? '')
    .split('-')
    .map((w) => (w ? w[0].toUpperCase() + w.slice(1) : w))
    .join(' ');
}

export function clamp(value, low, high) {
  return Math.min(high, Math.max(low, value));
}
