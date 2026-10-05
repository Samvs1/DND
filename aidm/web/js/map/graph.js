// The region graph as inline SVG (built with createElementNS, never innerHTML): visited nodes are named, nodes
// the party only knows from an exit are fogged, a locked gateway shows a lock label and the current node is marked.
import { t } from '../strings.js';
import { NODE_H, NODE_W, layoutGraph } from './layout.js';

const NS = 'http://www.w3.org/2000/svg';
const LINE_CHARS = 15;

function el(tag, attrs = {}, ...children) {
  const node = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, String(v));
  for (const c of children) node.append(c);
  return node;
}

/** Break a place name into at most two short lines. */
export function wrapName(name) {
  const words = String(name).split(/\s+/).filter(Boolean);
  const lines = [''];
  for (const word of words) {
    const line = lines[lines.length - 1];
    if (line && `${line} ${word}`.length > LINE_CHARS && lines.length < 2) lines.push(word);
    else lines[lines.length - 1] = line ? `${line} ${word}` : word;
  }
  return lines.map((l, i) => (i === 1 && l.length > LINE_CHARS + 2 ? `${l.slice(0, LINE_CHARS)}...` : l));
}

function statusOf(node) {
  if (node.current) return 'here';
  if (node.locked) return 'locked';
  return node.visited ? 'visited' : 'fogged';
}

function drawNode(node, pos, label) {
  const status = statusOf(node);
  const g = el('g', { class: `map-node ${status}`, transform: `translate(${pos.x} ${pos.y})`, role: 'img', 'aria-label': `${label}: ${t(`map.${status}`)}`, 'data-testid': 'map-node', 'data-node': node.id, 'data-state': status });
  g.append(el('rect', { width: NODE_W, height: NODE_H, rx: 6 }));
  wrapName(label).forEach((line, i) => {
    g.append(el('text', { x: NODE_W / 2, y: 18 + i * 15, 'text-anchor': 'middle', class: 'map-name' }, document.createTextNode(line)));
  });
  g.append(el('text', { x: NODE_W / 2, y: NODE_H - 7, 'text-anchor': 'middle', class: 'map-status' }, document.createTextNode(t(`map.${status}`))));
  return g;
}

/** `labels` maps a node id to the name to show (an exit's name stands in for a fogged node). */
export function buildGraph(map, labels) {
  const current = map.nodes.find((n) => n.current)?.id ?? map.nodes[0]?.id;
  const { positions, width, height } = layoutGraph(map.nodes, map.edges, current);
  const svg = el('svg', { class: 'map-svg', viewBox: `0 0 ${width} ${height}`, role: 'group', 'aria-label': t('map.graph'), 'data-testid': 'map-graph' });
  svg.style.maxWidth = `${width}px`;
  for (const [a, b] of map.edges) {
    const from = positions.get(a);
    const to = positions.get(b);
    if (!from || !to) continue;
    svg.append(el('line', { class: 'map-edge', x1: from.x + NODE_W / 2, y1: from.y + NODE_H / 2, x2: to.x + NODE_W / 2, y2: to.y + NODE_H / 2 }));
  }
  for (const node of map.nodes) {
    const label = node.visited || node.current ? node.name : (labels.get(node.id) ?? node.name);
    svg.append(drawNode(node, positions.get(node.id), label));
  }
  return svg;
}
