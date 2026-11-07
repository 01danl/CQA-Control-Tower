// Small, local SVG icons; no remote font or asset dependency.
const paths = {
  conversations: ['M21 11.5a8.5 8.5 0 0 1-8.5 8.5H4l-3 3V11.5a8.5 8.5 0 0 1 17-1', 'M6 8h9M6 12h6'],
  rubrics: ['M9 4h11v17H4V4h2', 'M9 2h6v4H9zM8 11l1.5 1.5L12 10M14 12h3M8 17h9'],
  appeals: ['M12 3v18M5 21h14M3 7l9-4 9 4M5 7l-4 8h8L5 7zM19 7l-4 8h8l-4-8z'],
  analytics: ['M4 20V10M10 20V4M16 20v-7M22 20H1'],
};
export function icon(name) {
  const node = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  for (const [key, value] of Object.entries({ viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '1.7', 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'aria-hidden': 'true', focusable: 'false', class: 'icon' })) node.setAttribute(key, value);
  for (const d of paths[name] ?? paths.conversations) {
    const path = document.createElementNS(node.namespaceURI, 'path'); path.setAttribute('d', d); node.append(path);
  }
  return node;
}
