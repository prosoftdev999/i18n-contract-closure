// Captured application import-map loader used by the audited page.
// It models the production loader's resolution cache and first-evaluation
// catalog side effects; it does not contain any expected manifest.
export function normalizeTarget(target, baseURL) {
  return new URL(target, baseURL).href;
}

function bestMatch(table, specifier) {
  if (Object.prototype.hasOwnProperty.call(table, specifier)) return table[specifier];
  let best = null;
  for (const [key, target] of Object.entries(table)) {
    if (!key.endsWith("/")) continue;
    if (!specifier.startsWith(key)) continue;
    if (best === null || key.length > best[0].length) best = [key, target];
  }
  if (best === null) return null;
  return String(best[1]) + specifier.slice(best[0].length);
}

export function resolveImport(map, specifier, referrer, baseURL) {
  if (specifier.startsWith("./") || specifier.startsWith("../") || specifier.startsWith("/") || /^[a-zA-Z][a-zA-Z0-9+.-]*:/.test(specifier)) {
    return new URL(specifier, referrer).href;
  }
  const scopes = map.scopes || {};
  const candidates = Object.keys(scopes).filter(prefix => referrer.startsWith(prefix)).sort((a,b)=>b.length-a.length);
  for (const scope of candidates) {
    const target = bestMatch(scopes[scope], specifier);
    if (target !== null) return normalizeTarget(target, baseURL);
  }
  const target = bestMatch(map.imports || {}, specifier);
  if (target === null) throw new Error(`unmapped bare specifier ${specifier} from ${referrer}`);
  return normalizeTarget(target, baseURL);
}

export function patchImportMap(current, delta) {
  const next = structuredClone(current);
  next.imports ||= {};
  next.scopes ||= {};
  for (const [k,v] of Object.entries(delta.imports || {})) next.imports[k] = v;
  for (const [scope, entries] of Object.entries(delta.scopes || {})) {
    next.scopes[scope] ||= {};
    for (const [k,v] of Object.entries(entries)) next.scopes[scope][k] = v;
  }
  return next;
}

// Production behavior that matters to the capture: a successful resolution is
// cached by (referrer,specifier). Installing a later import map does not rewrite
// already-resolved edges. A full page reload replaces the map and clears this
// module-map cache. Module top-level side effects run once per page lifetime.
