// Captured production HMR state rules used by the incident build.
// This file describes update acceptance only; it does not know localization,
// source maps, routes, Service Worker state, or the expected manifest.
export function parentsOf(chunks) {
  const out = new Map();
  for (const [parent, spec] of Object.entries(chunks)) {
    for (const child of (spec.children || [])) {
      if (!out.has(child)) out.set(child, []);
      out.get(child).push(parent);
    }
  }
  return out;
}

export function updateDisposition(chunks, accepts, mountedEntryChunks, changedChunks) {
  const parents = parentsOf(chunks);
  const queue = [...changedChunks];
  const seen = new Set();
  while (queue.length) {
    const child = queue.shift();
    if (seen.has(child)) continue;
    seen.add(child);
    if (mountedEntryChunks.has(child)) return "reload";
    for (const parent of (parents.get(child) || [])) {
      const boundaries = new Set(accepts[parent] || []);
      if (!boundaries.has(child)) queue.push(parent);
    }
  }
  return "accept";
}
