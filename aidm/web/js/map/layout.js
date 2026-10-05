// Pure layout of the region graph: rows by distance from the current node (the current node on top), nodes
// centred in each row. No DOM here, so it is easy to test and to reuse.

export const NODE_W = 128;
export const NODE_H = 58;
export const GAP_X = 18;
export const GAP_Y = 44;

function adjacency(edges) {
  const next = new Map();
  for (const [a, b] of edges) {
    if (!next.has(a)) next.set(a, []);
    if (!next.has(b)) next.set(b, []);
    next.get(a).push(b);
    next.get(b).push(a);
  }
  return next;
}

/** Distance (rows) of every node from `rootId`; nodes the graph cannot reach go to the last row. */
export function levels(nodes, edges, rootId) {
  const next = adjacency(edges);
  const depth = new Map([[rootId, 0]]);
  const queue = [rootId];
  while (queue.length) {
    const id = queue.shift();
    for (const other of next.get(id) ?? []) {
      if (!depth.has(other)) {
        depth.set(other, depth.get(id) + 1);
        queue.push(other);
      }
    }
  }
  const last = Math.max(0, ...depth.values()) + 1;
  for (const node of nodes) if (!depth.has(node.id)) depth.set(node.id, last);
  return depth;
}

/** {positions: Map(id -> {x, y}), width, height}: x, y are the top-left corner of each node box. */
export function layoutGraph(nodes, edges, rootId) {
  const depth = levels(nodes, edges, rootId);
  const rows = [];
  for (const node of nodes) {
    const row = depth.get(node.id);
    (rows[row] ??= []).push(node);
  }
  const widest = Math.max(1, ...rows.map((r) => (r ? r.length : 0)));
  const width = widest * NODE_W + (widest - 1) * GAP_X;
  const positions = new Map();
  let y = 0;
  for (const row of rows.filter(Boolean)) {
    const rowWidth = row.length * NODE_W + (row.length - 1) * GAP_X;
    const left = (width - rowWidth) / 2;
    row.forEach((node, i) => positions.set(node.id, { x: left + i * (NODE_W + GAP_X), y }));
    y += NODE_H + GAP_Y;
  }
  return { positions, width, height: Math.max(NODE_H, y - GAP_Y) };
}
