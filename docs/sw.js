// ODK Fichar — Service Worker v3
const CACHE = 'odk-fichar-v3';

const PRECACHE = [
  '/blank-app/fichar.html',
  '/blank-app/icon.png',
  '/blank-app/manifest.json',
  '/blank-app/sw.js',
];

// Install: cache core assets immediately — skipWaiting forces instant activation
self.addEventListener('install', e => {
  self.skipWaiting();
  e.waitUntil(
    caches.open(CACHE).then(c => c.addAll(PRECACHE))
  );
});

// Activate: delete all stale caches, then claim all clients
self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

// Fetch: cache-first for our GitHub Pages assets
self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);

  // Only intercept same-origin requests (never block cross-origin like Supabase/HF)
  if (url.origin !== self.location.origin) return;

  // Ignore non-GET
  if (e.request.method !== 'GET') return;

  e.respondWith(
    caches.match(e.request).then(cached => {
      if (cached) {
        // Serve from cache instantly, refresh in background (stale-while-revalidate)
        fetch(e.request).then(fresh => {
          if (fresh && fresh.status === 200) {
            caches.open(CACHE).then(c => c.put(e.request, fresh.clone()));
          }
        }).catch(() => {});
        return cached;
      }
      // Not in cache — fetch, cache, return
      return fetch(e.request).then(resp => {
        if (resp && resp.status === 200) {
          caches.open(CACHE).then(c => c.put(e.request, resp.clone()));
        }
        return resp;
      }).catch(() => {
        // Offline fallback for navigation requests
        if (e.request.mode === 'navigate') {
          return caches.match('/blank-app/fichar.html');
        }
      });
    })
  );
});
