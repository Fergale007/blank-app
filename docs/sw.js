// ODK Fichar — Service Worker v2
const CACHE = 'odk-fichar-v2';

const PRECACHE = [
  '/blank-app/fichar.html',
  '/blank-app/icon.png',
  '/blank-app/manifest.json',
];

// Install: cache core assets immediately
self.addEventListener('install', e => {
  self.skipWaiting();
  e.waitUntil(
    caches.open(CACHE).then(c => c.addAll(PRECACHE))
  );
});

// Activate: delete stale caches
self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

// Fetch: cache-first for our assets, network-only for everything else
self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);

  // Only cache same-origin GitHub Pages assets
  if (url.origin === self.location.origin) {
    e.respondWith(
      caches.match(e.request).then(cached => {
        if (cached) {
          // Serve cached, refresh in background (stale-while-revalidate)
          fetch(e.request).then(fresh => {
            if (fresh && fresh.status === 200) {
              caches.open(CACHE).then(c => c.put(e.request, fresh));
            }
          }).catch(() => {});
          return cached;
        }
        // Not cached — fetch and cache
        return fetch(e.request).then(resp => {
          if (resp && resp.status === 200) {
            const clone = resp.clone();
            caches.open(CACHE).then(c => c.put(e.request, clone));
          }
          return resp;
        }).catch(() => caches.match('/blank-app/fichar.html'));
      })
    );
  }
});
