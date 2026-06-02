// Service Worker for the customer portal PWA.
const PORTAL_SW_VERSION = '2026-06-02-p5';
const PORTAL_CACHE = `portal-static-${PORTAL_SW_VERSION}`;

const PORTAL_ASSETS = [
  '/portal',
  '/static/css/style.css',
  '/static/js/portal.js',
  '/static/portal-manifest.json',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  'https://cdn.tailwindcss.com',
  'https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(PORTAL_CACHE)
      .then(cache => Promise.all(PORTAL_ASSETS.map(asset => cacheAsset(cache, asset))))
      .catch(err => console.warn('[Portal SW] Precache failed:', err))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then(names => Promise.all(
        names
          .filter(name => name.startsWith('portal-static-') && name !== PORTAL_CACHE)
          .map(name => caches.delete(name))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  if (request.method !== 'GET') return;
  if (!url.protocol.startsWith('http')) return;

  // Authenticated portal API responses are not cached.
  if (url.pathname.startsWith('/api/portal/')) {
    event.respondWith(fetch(request).catch(() => jsonOfflineResponse()));
    return;
  }

  if (request.mode === 'navigate') {
    event.respondWith(networkFirst(request));
    return;
  }

  if (
    url.pathname.startsWith('/static/') ||
    url.pathname === '/portal-sw.js' ||
    url.hostname.includes('cdn.tailwindcss.com') ||
    url.hostname.includes('cdn.jsdelivr.net')
  ) {
    event.respondWith(cacheFirst(request));
  }
});

async function cacheAsset(cache, asset) {
  const isRemote = asset.startsWith('http');
  const request = new Request(asset, {
    mode: isRemote ? 'no-cors' : 'same-origin',
    cache: 'reload',
  });
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), isRemote ? 2500 : 5000);
  try {
    const response = await fetch(request, { signal: controller.signal });
    if (response.ok || response.type === 'opaque') await cache.put(request, response);
  } finally {
    clearTimeout(timeout);
  }
}

async function networkFirst(request) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(PORTAL_CACHE);
      await cache.put(request, response.clone());
    }
    return response;
  } catch (_) {
    const cached = await caches.match(request);
    if (cached) return cached;
    return offlineHtmlResponse();
  }
}

async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) return cached;
  try {
    const response = await fetch(request);
    if (response.ok || response.type === 'opaque') {
      const cache = await caches.open(PORTAL_CACHE);
      await cache.put(request, response.clone());
    }
    return response;
  } catch (_) {
    return new Response('Recurso no disponible offline', { status: 503 });
  }
}

function jsonOfflineResponse() {
  return new Response(
    JSON.stringify({ detail: 'Sin conexion con el servidor', offline: true }),
    { status: 503, headers: { 'Content-Type': 'application/json' } }
  );
}

function offlineHtmlResponse() {
  return new Response(
    '<!doctype html><meta charset="utf-8"><title>Sin conexion</title>' +
      '<body style="font-family:system-ui;padding:2rem">' +
      '<h1>Sin conexion</h1><p>Vuelve a abrir el portal cuando recuperes red.</p></body>',
    { status: 503, headers: { 'Content-Type': 'text/html; charset=utf-8' } }
  );
}
