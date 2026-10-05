// Shop price helpers shared with the tests: the server decides every price, this only previews what to show.

/** Half the item's value, rounded down (the server's rule); 0 means the shop pays nothing. */
export function sellPrice(item) {
  return Math.floor((item.value_gp ?? 0) / 2);
}

/** A pack line the shop could buy: not worn, and worth at least 1 gp. */
export function sellable(item) {
  return !item.equipped_slot && sellPrice(item) >= 1;
}
