// Kalshi Knows service worker: app shell, network-first data, web push.
const VERSION = 'kk-v4';
const SHELL = ['./', './index.html', './styles.css', './js/app.js', './js/util.js', './js/data.js', './js/charts.js',
  './js/hero3d.js', './js/push.js', './js/qr.js', './js/emblems.js', './manifest.webmanifest', './icons/icon-192.png', './icons/badge-96.png',
  './icons/apple-touch-icon.png', './icons/favicon-64.png'];
const CDN = /^https:\/\/(cdn\.jsdelivr\.net|fonts\.googleapis\.com|fonts\.gstatic\.com)\//;

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(VERSION).then((c) => Promise.all(SHELL.map((u) => c.add(u).catch(() => null)))).then(() => self.skipWaiting()));
});
self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== VERSION).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});

async function networkFirst(req, noStore) {
  const cache = await caches.open(VERSION);
  try {
    const res = await fetch(req, noStore ? { cache: 'no-store' } : undefined);
    const len = +(res.headers.get('content-length') || 0);
    if (res.ok && len < 3e6) cache.put(req, res.clone()).catch(() => {});
    return res;
  } catch (err) {
    const hit = await cache.match(req, { ignoreSearch: noStore });
    if (hit) return hit;
    if (req.mode === 'navigate') { const shell = await cache.match('./index.html'); if (shell) return shell; }
    throw err;
  }
}
async function cacheFirst(req) {
  const cache = await caches.open(VERSION);
  const hit = await cache.match(req);
  if (hit) return hit;
  const res = await fetch(req);
  if (res.ok || res.type === 'opaque') cache.put(req, res.clone()).catch(() => {});
  return res;
}

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin === self.location.origin) {
    const data = url.pathname.endsWith('/config.json') || url.pathname.includes('/data/');
    e.respondWith(networkFirst(req, data));
  } else if (CDN.test(req.url)) {
    e.respondWith(cacheFirst(req));
  } // everything else (the live API, SSE) goes straight to the network
});

self.addEventListener('push', (e) => {
  let d = {};
  try { d = e.data ? e.data.json() : {}; } catch { d = { body: e.data ? e.data.text() : '' }; }
  const title = d.title || 'Kalshi Knows';
  e.waitUntil(self.registration.showNotification(title, {
    body: d.body || 'The market just moved.',
    tag: d.tag || 'kk',
    renotify: true,
    data: { url: d.url || './#live' },
    icon: 'icons/icon-192.png',
    badge: 'icons/badge-96.png',
    vibrate: [90, 50, 90],
  }));
});

self.addEventListener('notificationclick', (e) => {
  e.notification.close();
  const target = new URL((e.notification.data && e.notification.data.url) || './', self.registration.scope).href;
  e.waitUntil((async () => {
    const wins = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
    for (const w of wins) {
      if (w.url.startsWith(self.registration.scope)) { await w.focus(); try { await w.navigate(target); } catch {} return; }
    }
    await self.clients.openWindow(target);
  })());
});
