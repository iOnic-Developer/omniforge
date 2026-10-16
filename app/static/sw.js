'use strict';
// Increment whenever any allowlisted asset changes. Never cache the dashboard.
const CACHE = 'omniforge-public-v3';
const ASSETS = [
  '/assets/offline.html', '/assets/product.css', '/assets/mark.svg',
  '/assets/favicon.svg', '/assets/favicon-32.png', '/assets/apple-touch-icon.png',
  '/assets/icon-192.png', '/assets/icon-512.png', '/assets/icon-maskable-512.png',
  '/assets/manifest.webmanifest', '/assets/fonts/manrope.ttf', '/assets/fonts/jetbrains-mono.ttf'
];
self.addEventListener('install',event => {
  event.waitUntil(caches.open(CACHE).then(async cache => {
    for (const path of ASSETS) {
      // Strip credentials even on these public same-origin requests.
      const response = await fetch(path,{credentials:'omit',cache:'reload',redirect:'error'});
      const expected = path.endsWith('.html') ? ['text/html'] :
        path.endsWith('.css') ? ['text/css'] : path.endsWith('.svg') ? ['image/svg+xml'] :
        path.endsWith('.png') ? ['image/png'] : path.endsWith('.ttf') ? ['font/ttf','application/x-font-ttf'] :
        ['application/manifest+json','application/json'];
      const mime = (response.headers.get('Content-Type') || '').split(';')[0].trim().toLowerCase();
      if (!response.ok || response.redirected || !expected.includes(mime)) throw new Error('Unexpected public asset response');
      await cache.put(path,response);
    }
  }));
  // Wait for the user to accept an update; never discard their draft automatically.
});
self.addEventListener('activate',event => {
  event.waitUntil((async () => {
    for (const key of await caches.keys()) {
      if (key.startsWith('omniforge-public-') && key !== CACHE) await caches.delete(key);
    }
    await self.clients.claim();
  })());
});
self.addEventListener('message',event => {
  if (event.data?.type === 'SKIP_WAITING') self.skipWaiting();
});
self.addEventListener('fetch',event => {
  const request = event.request, url = new URL(request.url);
  if (request.method !== 'GET' || url.origin !== self.location.origin ||
      url.pathname.startsWith('/api') || url.pathname.startsWith('/mcp') ||
      request.headers.has('Authorization')) return;
  if (request.mode === 'navigate') {
    // Network first, NO successful-page caching. Only generic fallback on failure.
    event.respondWith(fetch(request).catch(async () => {
      const cache = await caches.open(CACHE);
      return await cache.match('/assets/offline.html') || Response.error();
    }));
  } else if (!url.search && ASSETS.includes(url.pathname)) {
    event.respondWith((async () => {
      const cache = await caches.open(CACHE);
      return await cache.match(url.pathname) || fetch(request);
    })());
  }
});
