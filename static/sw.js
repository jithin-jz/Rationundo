// Shell-only service worker. NEVER caches /api/ — stock data must always be fresh.
const CACHE = 'rationundo-shell-v5';
const SHELL = [
  '/',
  '/static/app.js?v=5',
  '/static/style.css?v=5',
  '/static/favicon.svg',
  '/static/manifest.json',
];
const SHELL_PATHS = new Set(SHELL.map((path) => new URL(path, self.location.origin).pathname));

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  // Bypass API and non-GET: always hit the network, never cache.
  if (e.request.method !== 'GET' || url.pathname.startsWith('/api/')) return;
  // HTML ('/'): network-first so updates show.
  if (e.request.mode === 'navigate') {
    e.respondWith(fetch(e.request).catch(() => caches.match('/')));
    return;
  }
  // Static shell assets: stale-while-revalidate.
  e.respondWith(
    caches.match(e.request).then((hit) => {
      const fresh = fetch(e.request).then((response) => {
        if (url.origin === self.location.origin && SHELL_PATHS.has(url.pathname) && response.ok) {
          caches.open(CACHE).then((cache) => cache.put(e.request, response.clone()));
        }
        return response;
      }).catch(() => hit);
      return hit || fresh;
    })
  );
});
