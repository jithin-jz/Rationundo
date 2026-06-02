// Shell-only service worker. Caches static assets for instant repeat loads
// and offline shell. NEVER caches /api/ — stock data must always be fresh.
const CACHE = 'rationundo-shell-v2';
const SHELL = [
  '/',
  '/static/app.js',
  '/static/style.css',
  '/static/favicon.svg',
  '/static/manifest.json',
];

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
  // Shell assets: cache-first. HTML ('/'): network-first so updates show.
  if (e.request.mode === 'navigate') {
    e.respondWith(fetch(e.request).catch(() => caches.match('/')));
    return;
  }
  e.respondWith(caches.match(e.request).then((hit) => hit || fetch(e.request)));
});
