// Service Worker for WMS Almacen PWA.
// Bump SW_VERSION when static assets or cache strategy change.
const SW_VERSION = '2026-06-02-r6';
const CACHE_PREFIX = 'wms';
const STATIC_CACHE = `${CACHE_PREFIX}-static-${SW_VERSION}`;
const API_CACHE = `${CACHE_PREFIX}-api-${SW_VERSION}`;
const RUNTIME_CACHE = `${CACHE_PREFIX}-runtime-${SW_VERSION}`;
const ACTIVE_CACHES = new Set([STATIC_CACHE, API_CACHE, RUNTIME_CACHE]);

const STATIC_ASSETS = [
  '/',
  '/login',
  '/picking',
  '/static/css/style.css',
  '/static/js/app.js',
  '/static/js/picking.js',
  '/static/manifest.json',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  'https://cdn.tailwindcss.com',
  'https://cdn.jsdelivr.net/npm/@alpinejs/collapse@3.x.x/dist/cdn.min.js',
  'https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    precacheStaticAssets()
      .catch(err => console.warn('[SW] Precache failed:', err))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then(cacheNames => Promise.all(
        cacheNames
          .filter(name => name.startsWith(`${CACHE_PREFIX}-`) && !ACTIVE_CACHES.has(name))
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

  if (request.mode === 'navigate') {
    event.respondWith(networkFirstStrategy(request, RUNTIME_CACHE));
    return;
  }

  if (url.pathname.startsWith('/api/')) {
    event.respondWith(networkFirstStrategy(request, API_CACHE));
    return;
  }

  if (
    url.pathname.startsWith('/static/') ||
    url.hostname.includes('cdn.tailwindcss.com') ||
    url.hostname.includes('cdn.jsdelivr.net')
  ) {
    event.respondWith(cacheFirstStrategy(request, STATIC_CACHE));
    return;
  }

  event.respondWith(networkFirstStrategy(request, RUNTIME_CACHE));
});

self.addEventListener('message', (event) => {
  if (event.data?.type === 'SKIP_WAITING') self.skipWaiting();
  if (event.data?.type === 'GET_VERSION') {
    const payload = { type: 'SW_VERSION', version: SW_VERSION };
    if (event.ports?.[0]) event.ports[0].postMessage(payload);
    else event.source?.postMessage(payload);
  }
});

self.addEventListener('sync', (event) => {
  if (event.tag === 'sync-picking-queue') {
    event.waitUntil(syncPickingQueue());
  }
});

self.addEventListener('push', (event) => {
  if (!event.data) return;

  const data = event.data.json();
  event.waitUntil(
    self.registration.showNotification(data.title || 'WMS Almacen', {
      body: data.body || '',
      icon: '/static/icons/icon-192.png',
      badge: '/static/icons/icon-192.png',
      tag: data.tag || 'wms-notification',
      data: data.url ? { url: data.url } : undefined,
    })
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  if (event.notification.data?.url) {
    event.waitUntil(clients.openWindow(event.notification.data.url));
  }
});

async function precacheStaticAssets() {
  const cache = await caches.open(STATIC_CACHE);
  await Promise.all(STATIC_ASSETS.map(asset =>
    cacheAsset(cache, asset).catch(err => {
      console.warn('[SW] Asset not cached:', asset, err);
    })
  ));
}

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
    if (response.ok || response.type === 'opaque') {
      await cache.put(request, response);
    }
  } finally {
    clearTimeout(timeout);
  }
}

async function networkFirstStrategy(request, cacheName) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(cacheName);
      await cache.put(request, response.clone());
    }
    return response;
  } catch (_) {
    const cached = await caches.match(request);
    if (cached) return cached;

    if (request.mode === 'navigate') {
      return offlineHtmlResponse();
    }

    return new Response(
      JSON.stringify({ error: 'Sin conexion', offline: true }),
      { status: 503, headers: { 'Content-Type': 'application/json' } }
    );
  }
}

async function cacheFirstStrategy(request, cacheName) {
  const cached = await caches.match(request);
  if (cached) return cached;

  try {
    const response = await fetch(request);
    if (response.ok || response.type === 'opaque') {
      const cache = await caches.open(cacheName);
      await cache.put(request, response.clone());
    }
    return response;
  } catch (_) {
    return new Response('Recurso no disponible offline', { status: 503 });
  }
}

async function syncPickingQueue() {
  const clientsList = await self.clients.matchAll({ includeUncontrolled: true });
  clientsList.forEach(client => {
    client.postMessage({ type: 'SYNC_PICKING_QUEUE' });
  });
}

function offlineHtmlResponse() {
  return new Response(
    '<!doctype html><meta charset="utf-8"><title>Sin conexion</title>' +
      '<body style="font-family:system-ui;padding:2rem">' +
      '<h1>Sin conexion</h1><p>Vuelve a intentarlo cuando recuperes red.</p></body>',
    { status: 503, headers: { 'Content-Type': 'text/html; charset=utf-8' } }
  );
}
