// Captured production service worker for r41.
const DIAG_CACHE = "diag-shared";
const NETWORK_FIRST_TIMEOUT_MS = 100;

function requestClass(url) {
  const p = new URL(url).pathname;
  if (p.startsWith('/diag/maps/')) return 'cache-first';
  if (p.startsWith('/diag/catalog/') || p.endsWith('/locale_graph.json') || p.endsWith('/routes.json')) return 'network-first';
  return 'stale-while-revalidate';
}

async function networkFirst(event, cache) {
  const network = fetch(event.request);
  const timer = new Promise(resolve => setTimeout(() => resolve(null), NETWORK_FIRST_TIMEOUT_MS));
  const first = await Promise.race([network, timer]);
  if (first && first.ok) { event.waitUntil(cache.put(event.request, first.clone())); return first; }
  const cached = await cache.match(event.request);
  event.waitUntil(network.then(r => r && r.ok ? cache.put(event.request, r.clone()) : undefined));
  return cached || network;
}

async function staleWhileRevalidate(event, cache) {
  const cached = await cache.match(event.request);
  const network = fetch(event.request);
  event.waitUntil(network.then(r => r && r.ok ? cache.put(event.request, r.clone()) : undefined));
  return cached || network;
}

async function cacheFirst(event, cache) {
  const cached = await cache.match(event.request);
  if (cached) return cached;
  const response = await fetch(event.request);
  if (response && response.ok) event.waitUntil(cache.put(event.request, response.clone()));
  return response;
}

self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  if (!url.pathname.startsWith('/diag/')) return;
  event.respondWith(caches.open(DIAG_CACHE).then(cache => {
    const cls = requestClass(event.request.url);
    if (cls === 'cache-first') return cacheFirst(event, cache);
    if (cls === 'network-first') return networkFirst(event, cache);
    return staleWhileRevalidate(event, cache);
  }));
});
