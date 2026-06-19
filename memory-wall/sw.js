const CACHE = 'memory-wall-v1';
const STATIC_URLS = ['/', '记忆墙.html', 'manifest.json', 'icon.svg', 'style.css', 'app.js'];

// Static assets: cache-first (fast offline)
// API requests: network-first (fresh data, fallback to cache)

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE).then(c => c.addAll(STATIC_URLS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k))))
  );
  self.clients.claim();
});

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);

  // API calls — network-first, fallback to cache
  if (url.pathname.startsWith('/notes') || url.pathname.startsWith('/search') || url.pathname.startsWith('/chat')) {
    e.respondWith(networkFirst(e.request));
    return;
  }

  // Static files — cache-first
  e.respondWith(
    caches.match(e.request).then(r => r || fetch(e.request).catch(() => r))
  );
});

async function networkFirst(request) {
  try {
    const fresh = await fetch(request);
    const cache = await caches.open(CACHE);
    cache.put(request, fresh.clone());
    return fresh;
  } catch {
    const cached = await caches.match(request);
    return cached || new Response('离线', { status: 503 });
  }
}
