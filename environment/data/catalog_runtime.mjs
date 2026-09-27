// Captured application locale registry.
const TOMBSTONE = Symbol('removed');
export function applyCatalogEvents(events, loadedChunks) {
  const state = new Map();
  for (const event of [...events].sort((a,b) => a.seq - b.seq)) {
    if (!loadedChunks.has(event.bundle)) continue;
    const key = `${event.namespace}:${event.key}`;
    state.set(key, event.op === 'remove' ? TOMBSTONE : event.pattern);
  }
  return state;
}
export function lookupCatalog(state, namespace, key) {
  const v = state.get(`${namespace}:${key}`);
  if (v === TOMBSTONE) return {removed:true};
  return v === undefined ? null : {removed:false, pattern:v};
}
