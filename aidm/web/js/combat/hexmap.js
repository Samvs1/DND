// Hex battle map geometry (M21): pointy-top hexes from the zones' axial coordinates (q, r). Touching hexes are
// linked zones (the server generates maps that way, aidm/rules/hex_layout.py). Pure: no DOM.
// Units are hex widths: a hex is 1 wide and 2/sqrt(3) tall; the centre of (q, r) is (q + r/2, r * sqrt(3)/2).

const ROW = Math.sqrt(3) / 2;
const TALL = 2 / Math.sqrt(3);

function centre(zone) {
  return { x: zone.q + zone.r / 2, y: zone.r * ROW };
}

/**
 * Layout of the zones on a stage: {ratio, cells: Map(zoneId -> {left, top, width, height})} with the box of
 * each hex in percent of the stage, and ratio = stage width / height (for CSS aspect-ratio).
 */
export function hexLayout(zones) {
  const points = zones.map((z) => ({ id: z.id, ...centre(z) }));
  const minX = Math.min(...points.map((p) => p.x)) - 0.5;
  const maxX = Math.max(...points.map((p) => p.x)) + 0.5;
  const minY = Math.min(...points.map((p) => p.y)) - TALL / 2;
  const maxY = Math.max(...points.map((p) => p.y)) + TALL / 2;
  const wide = maxX - minX;
  const high = maxY - minY;
  const cells = new Map();
  for (const p of points) {
    cells.set(p.id, {
      left: ((p.x - 0.5 - minX) / wide) * 100,
      top: ((p.y - TALL / 2 - minY) / high) * 100,
      width: (1 / wide) * 100,
      height: (TALL / high) * 100,
    });
  }
  return { ratio: wide / high, cells };
}

const DIRECTIONS = [
  [1, 0],
  [1, -1],
  [0, -1],
  [-1, 0],
  [-1, 1],
  [0, 1],
];

/** True when the two zones' hexes share an edge. */
export function hexesTouch(a, b) {
  return DIRECTIONS.some(([dq, dr]) => b.q - a.q === dq && b.r - a.r === dr);
}
