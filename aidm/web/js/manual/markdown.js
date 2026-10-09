// A small Markdown renderer for the player manual: headings, paragraphs, bold, italic, inline code, lists, tables
// and rules. Every piece of text goes in through text nodes (never innerHTML), so the source cannot inject markup.
import { h } from '../ui/dom.js';

const HEADING = /^(#{1,4})\s+(.*?)\s*#*\s*$/;
const BULLET = /^\s*[-*+]\s+(.*)$/;
const ORDERED = /^\s*\d+[.)]\s+(.*)$/;
const RULE = /^\s*([-*_])(\s*\1){2,}\s*$/;
const COMMENT = /^\s*<!--.*-->\s*$/;
const SEPARATOR = /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$/;

/** Inline text to DOM nodes: `code`, **bold** and *italic*. A lone * inside a word stays a plain star. */
export function inline(text) {
  const nodes = [];
  let plain = '';
  const flush = () => {
    if (plain) nodes.push(document.createTextNode(plain));
    plain = '';
  };
  let i = 0;
  while (i < text.length) {
    const rest = text.slice(i);
    const code = /^`([^`]+)`/.exec(rest);
    const bold = /^\*\*(?=\S)(.+?)(?<=\S)\*\*/.exec(rest);
    const before = i > 0 ? text[i - 1] : ' ';
    const ital = /^\*(?=[^\s*])(.+?)(?<=\S)\*(?![\w*])/.exec(rest);
    if (code) {
      flush();
      nodes.push(h('code', {}, code[1]));
      i += code[0].length;
    } else if (bold) {
      flush();
      nodes.push(h('strong', {}, ...inline(bold[1])));
      i += bold[0].length;
    } else if (ital && !/[\w]/.test(before)) {
      flush();
      nodes.push(h('em', {}, ...inline(ital[1])));
      i += ital[0].length;
    } else {
      plain += text[i];
      i += 1;
    }
  }
  flush();
  return nodes;
}

function splitRow(line) {
  let row = line.trim();
  if (row.startsWith('|')) row = row.slice(1);
  if (row.endsWith('|')) row = row.slice(0, -1);
  return row.split('|').map((c) => c.trim());
}

/** Source text to blocks: { type, ... }. */
export function parseBlocks(source) {
  const lines = source.replace(/\r\n?/g, '\n').split('\n');
  const blocks = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    const head = HEADING.exec(line);
    if (!line.trim() || COMMENT.test(line)) {
      i += 1;
    } else if (head) {
      blocks.push({ type: 'heading', level: head[1].length, text: head[2] });
      i += 1;
    } else if (RULE.test(line)) {
      blocks.push({ type: 'rule' });
      i += 1;
    } else if (line.trim().startsWith('|') && i + 1 < lines.length && SEPARATOR.test(lines[i + 1])) {
      const header = splitRow(line);
      const rows = [];
      i += 2;
      while (i < lines.length && lines[i].trim().startsWith('|')) rows.push(splitRow(lines[i++]));
      blocks.push({ type: 'table', header, rows });
    } else if (BULLET.test(line) || ORDERED.test(line)) {
      const ordered = ORDERED.test(line) && !BULLET.test(line);
      const items = [];
      while (i < lines.length && (ordered ? ORDERED : BULLET).test(lines[i])) {
        items.push((ordered ? ORDERED : BULLET).exec(lines[i])[1]);
        i += 1;
      }
      blocks.push({ type: ordered ? 'ol' : 'ul', items });
    } else {
      const para = [];
      while (i < lines.length && lines[i].trim() && !HEADING.test(lines[i]) && !BULLET.test(lines[i]) && !ORDERED.test(lines[i]) && !lines[i].trim().startsWith('|') && !COMMENT.test(lines[i])) para.push(lines[i++].trim());
      blocks.push({ type: 'p', text: para.join(' ') });
    }
  }
  return blocks;
}

/** One block to a DOM element. */
export function renderBlock(block) {
  switch (block.type) {
    case 'heading':
      return h(`h${block.level}`, {}, ...inline(block.text));
    case 'ul':
    case 'ol':
      return h(block.type, {}, ...block.items.map((item) => h('li', {}, ...inline(item))));
    case 'table':
      return h('div', { class: 'mn-table' }, h('table', {}, h('thead', {}, h('tr', {}, ...block.header.map((c) => h('th', { scope: 'col' }, ...inline(c))))), h('tbody', {}, ...block.rows.map((r) => h('tr', {}, ...r.map((c) => h('td', {}, ...inline(c))))))));
    case 'rule':
      return h('hr');
    default:
      return h('p', {}, ...inline(block.text));
  }
}

/** Blocks grouped into sections: each heading of level 2 to 4 starts one (level 1 is the title). */
export function toSections(blocks) {
  const sections = [{ id: 'top', level: 1, title: '', blocks: [] }];
  blocks.forEach((b) => {
    if (b.type === 'heading' && b.level >= 2) {
      sections.push({ id: `s${sections.length}`, level: b.level, title: b.text, blocks: [b] });
    } else {
      sections[sections.length - 1].blocks.push(b);
    }
  });
  return sections;
}

/** Plain text of a section (for search). */
export function sectionText(section) {
  const parts = [];
  section.blocks.forEach((b) => {
    if (b.type === 'table') parts.push(...b.header, ...b.rows.flat());
    else if (b.items) parts.push(...b.items);
    else if (b.text) parts.push(b.text);
  });
  return parts.join(' ').replace(/[*`]/g, '').toLowerCase();
}
