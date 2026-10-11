// Kalshi Knows service worker: app shell, network-first data, web push.
// Bump VERSION on every deploy that changes the shell; activate() deletes older caches.
const VERSION = 'kk-v11t';
const SHELL = ['./', './index.html', './styles.css', './js/app.js', './js/util.js', './js/data.js', './js/charts.js',
  './js/hero3d.js', './js/push.js', './js/qr.js', './js/emblems.js', './js/auto.js', './auto.css', './manifest.webmanifest', './icons/icon-192.png', './icons/badge-96.png',
  './icons/apple-touch-icon.png', './icons/favicon-64.png'];
const CDN = /^https:\/\/(cdn\.jsdelivr\.net|fonts\.googleapis\.com|fonts\.gstatic\.com)\//;

self.addEventListener('install', (e) => {
  // cache: 'reload' skips the HTTP cache, so a new SW never precaches a stale file
  e.waitUntil(caches.open(VERSION).then((c) => Promise.all(SHELL.map((u) => c.add(new Request(u, { cache: 'reload' })).catch(() => null)))).then(() => self.skipWaiting()));
});
self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== VERSION).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});

async function networkFirst(req, noStore) {
  const cache = await caches.open(VERSION);
  try {
    // data/config: never cached by the browser. Shell files: revalidate (GitHub Pages sends max-age=600, which would
    // otherwise serve a stale app.js for 10 minutes after a deploy). Navigations can't take a RequestInit, so rebuild them.
    const res = req.mode === 'navigate'
      ? await fetch(new Request(req.url, { cache: 'no-cache', credentials: 'same-origin', redirect: 'manual' }))
      : await fetch(req, { cache: noStore ? 'no-store' : 'no-cache' });
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

// Spoiler Shield: the page stores the preference in IndexedDB (and posts it here); read it before every notification.
function idb(mode, fn) {
  return new Promise((res) => {
    try {
      const r = indexedDB.open('kk', 1);
      r.onupgradeneeded = () => r.result.createObjectStore('prefs');
      r.onsuccess = () => { try { const tx = r.result.transaction('prefs', mode); const q = fn(tx.objectStore('prefs')); tx.oncomplete = () => res(q && q.result); tx.onerror = () => res(undefined); } catch { res(undefined); } };
      r.onerror = () => res(undefined);
    } catch { res(undefined); }
  });
}
let shieldMem = null; // last value posted by a page, in case IndexedDB is unavailable
self.addEventListener('message', (e) => {
  const m = e.data || {};
  if (m.type === 'shield') { shieldMem = !!m.on; e.waitUntil(idb('readwrite', (s) => s.put(!!m.on, 'shield'))); }
});
async function shieldOn() {
  const v = await idb('readonly', (s) => s.get('shield'));
  return v == null ? !!shieldMem : !!v;
}
// "SPOILER · SF @ SEA" / "✓ CONFIRMED · SF @ SEA" -> "SF @ SEA"
function gameOf(d) {
  if (d.short_name || d.game) return d.short_name || d.game;
  const m = /([A-Z]{2,4} @ [A-Z]{2,4})/.exec(`${d.title || ''} ${d.body || ''}`);
  return m ? m[1] : '';
}

self.addEventListener('push', (e) => {
  let d = {};
  try { d = e.data ? e.data.json() : {}; } catch { d = { body: e.data ? e.data.text() : '' }; }
  e.waitUntil((async () => {
    let title = d.title || 'Kalshi Knows';
    let body = d.body || 'The market just moved.';
    if (await shieldOn()) {
      const game = gameOf(d);
      const isTest = /test/i.test(d.title || '') && !game;
      title = 'Kalshi Knows · Spoiler Shield';
      body = isTest
        ? 'Push works. Spoiler Shield is on, so real alerts will only say that something big happened, never the play or the score.'
        : `Something big just happened in ${game || 'your game'}. Tap when you're ready to see it.`;
    }
    await self.registration.showNotification(title, {
      body,
      tag: d.tag || 'kk',
      renotify: true,
      data: { url: d.url || './#/live' },
      icon: 'icons/icon-192.png',
      badge: 'icons/badge-96.png',
      vibrate: [90, 50, 90],
    });
  })());
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
