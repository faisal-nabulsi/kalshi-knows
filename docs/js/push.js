// Install-as-app + Web Push (iOS 16.4+ needs the installed PWA and a tap) + the Spoiler Shield preference.
import { $, $$, store, PRESENT, fetchJSON } from './util.js';

export const isIOS = /iP(hone|od|ad)/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
export const standalone = matchMedia('(display-mode: standalone)').matches || navigator.standalone === true;
const pushOK = 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;

function urlBase64ToUint8Array(b64) {
  const pad = '='.repeat((4 - (b64.length % 4)) % 4);
  const raw = atob((b64 + pad).replace(/-/g, '+').replace(/_/g, '/'));
  return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
}

// Stream delays (Super Bowl LX latency study); the site's delay picker stores the chosen service as 'delayK'.
const DELAYS = { Antenna: 19, Cable: 38, Peacock: 48, 'YouTube TV': 53, 'Hulu Live': 53, DirecTV: 60, 'NFL+': 62 };
export function subBody(sub) {
  const service = store.get('delayK', 'Peacock');
  return JSON.stringify({ ...sub.toJSON(), prefs: { sync: !!store.get('sync', false), delay_s: DELAYS[service] ?? 48, service } });
}
export async function pushPrefs(getApi) {
  try {
    const api = getApi && getApi(); if (!api || !('serviceWorker' in navigator)) return false;
    const reg = await navigator.serviceWorker.ready; const sub = await reg.pushManager.getSubscription();
    if (!sub) return false;
    const r = await fetch(`${api}/api/push/subscribe`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: subBody(sub) });
    return r.ok;
  } catch { return false; }
}

// navigator.serviceWorker.ready never settles if registration failed; don't let the button hang on it
const swReady = (ms = 8000) => Promise.race([navigator.serviceWorker.ready,
  new Promise((_, rej) => setTimeout(() => rej(new Error('the service worker did not start; reload and try again')), ms))]);

export function registerSW() {
  if (!('serviceWorker' in navigator)) return;
  navigator.serviceWorker.register('./sw.js', { scope: './' }).then(() => syncShield()).catch((e) => console.warn('sw', e));
}

// ------------------------------------------------------------ Spoiler Shield
// The page reads localStorage. The service worker can't, so the same value goes to IndexedDB (read in sw.js before
// every showNotification) and is also posted to the running worker.
function idbPut(key, val) {
  return new Promise((res) => {
    try {
      const r = indexedDB.open('kk', 1);
      r.onupgradeneeded = () => r.result.createObjectStore('prefs');
      r.onsuccess = () => { try { const tx = r.result.transaction('prefs', 'readwrite'); tx.objectStore('prefs').put(val, key); tx.oncomplete = () => res(true); tx.onerror = () => res(false); } catch { res(false); } };
      r.onerror = () => res(false);
    } catch { res(false); }
  });
}
export const shieldOn = () => !!store.get('shield', false);
function syncShield() {
  const on = shieldOn();
  idbPut('shield', on);
  if (!('serviceWorker' in navigator)) return;
  navigator.serviceWorker.controller?.postMessage({ type: 'shield', on });
  navigator.serviceWorker.ready.then((r) => r.active?.postMessage({ type: 'shield', on })).catch(() => {});
}
const shieldListeners = [];
export function onShield(fn) { shieldListeners.push(fn); }
export function setShield(on) {
  store.set('shield', !!on);
  syncShield();
  paintShield();
  shieldListeners.forEach((fn) => fn(!!on));
}
function paintShield() {
  const on = shieldOn();
  document.documentElement.classList.toggle('shield', on);
  $$('[data-shield]').forEach((b) => { b.setAttribute('aria-checked', String(on)); const t = b.querySelector('b'); if (t) t.textContent = on ? 'ON' : 'OFF'; });
  const cb = $('#app-sheet-shield'); if (cb) cb.checked = on;
}
export function initShield() {
  paintShield();
  $$('[data-shield]').forEach((b) => b.addEventListener('click', () => setShield(!shieldOn())));
  $('#app-sheet-shield')?.addEventListener('change', (e) => setShield(e.target.checked));
}

// ------------------------------------------------------------ push
export function initPush(getApi) {
  const box = $('#get-main');
  let vapid = null;
  const prefetch = async () => {
    const api = getApi(); if (!api || vapid) return;
    try { vapid = (await fetchJSON(`${api}/api/push/vapid`, { timeout: 5000 }))?.publicKey || null; } catch {}
  };
  const isSubscribed = () => store.get('sub', false) && pushOK && Notification.permission === 'granted';

  function render() {
    const api = getApi();
    let html = '';
    if (isIOS && !standalone) {
      html = `<p class="get-lede">On iPhone, alerts only work from the home-screen app. Three taps:</p>
        <ol class="get-steps">
          <li><b>Share</b><span>Tap the Share button in Safari's toolbar (on iOS 26, tap ··· first).</span></li>
          <li><b>Add to Home Screen</b><span>Scroll the share sheet and tap it.</span></li>
          <li><b>Open it</b><span>Launch Kalshi Knows from your home screen, then tap Enable alerts.</span></li>
        </ol>
        <button class="btn-sig" id="show-sheet">Show me how</button>`;
    } else if (!pushOK) {
      html = `<p class="get-lede">This browser can't receive web push. Keep this tab open: alerts still take over the screen live. On iPhone, use Safari (iOS 16.4 or newer).</p>`;
    } else if (isSubscribed()) {
      html = `<p class="get-lede"><span class="sig">You're in.</span> Your phone buzzes the moment the market jumps on a live game.</p>
        <div class="get-btns"><button class="btn-sig" id="push-test">Send me a test</button>
        <button class="btn-ghost mono" id="push-redo">Re-subscribe</button></div>`;
    } else {
      html = `<p class="get-lede">${standalone ? 'Installed. One more tap:' : 'Works right here in Chrome, Edge and Firefox. No install needed.'}</p>
        <div class="get-btns"><button class="btn-sig" id="push-enable">Enable alerts</button></div>`;
    }
    html += `<p class="get-note mono" id="push-note">${api ? 'Live server connected.' : 'Live server offline right now: alerts switch on when the engine is running.'}</p>`;
    box.innerHTML = html;
    $('#show-sheet', box)?.addEventListener('click', () => showSheet(true));
    $('#push-enable', box)?.addEventListener('click', enable);
    $('#push-redo', box)?.addEventListener('click', enable);
    $('#push-test', box)?.addEventListener('click', test);
  }
  const note = (t, bad) => ['#push-note', '#app-sheet-note'].forEach((q) => { const n = $(q); if (n) { n.textContent = t; n.classList.toggle('bad', !!bad); } });

  async function enable() {
    const api = getApi();
    if (!api) { note('The live server is offline, so there is nothing to subscribe to yet. Try again during the game.', true); return false; }
    let perm;
    try { perm = await Notification.requestPermission(); } catch { perm = Notification.permission; }
    if (perm !== 'granted') { note(perm === 'denied' ? 'Notifications are blocked. Turn them on in Settings > Notifications > Kalshi Knows.' : 'No permission, no alerts.', true); return false; }
    try {
      note('Subscribing…');
      const reg = await swReady();
      if (!vapid) await prefetch();
      if (!vapid) throw new Error('no VAPID key from the server');
      let sub = await reg.pushManager.getSubscription();
      if (sub && store.get('vapid', '') !== vapid) { await sub.unsubscribe(); sub = null; }
      if (!sub) sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: urlBase64ToUint8Array(vapid) });
      const r = await fetch(`${api}/api/push/subscribe`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: subBody(sub) });
      if (!r.ok) throw new Error(`server said ${r.status}`);
      store.set('sub', true); store.set('vapid', vapid);
      syncShield();
      render(); note('Subscribed. Tap "Send me a test" to check it buzzes.');
      return true;
    } catch (e) { note(`Couldn't subscribe: ${e.message || e}`, true); return false; }
  }
  async function test() {
    const api = getApi(); if (!api) { note('Live server offline.', true); return false; }
    try {
      syncShield();
      const sub = await (await navigator.serviceWorker.ready).pushManager.getSubscription();
      const r = await fetch(`${api}/api/push/test`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ endpoint: sub && sub.endpoint }) });
      note(r.ok ? 'Test sent. It should land in a second or two.' : `Server said ${r.status}`, !r.ok);
      if (r.ok) store.set('tested', Date.now());
      return r.ok;
    } catch (e) { note(`Test failed: ${e.message}`, true); return false; }
  }

  // bottom sheets: install steps for iOS Safari; enable + test for the installed app
  const sheet = $('#ios-sheet'), appSheet = $('#app-sheet');
  const open = (el) => { el.hidden = false; requestAnimationFrame(() => el.classList.add('open')); };
  const shut = (el, key) => { el.classList.remove('open'); if (key) store.set(key, Date.now()); setTimeout(() => (el.hidden = true), 350); };
  function showSheet(force) {
    if (!sheet || PRESENT) return;
    if (!force && store.get('sheet_dismissed', 0) > Date.now() - 6 * 3600e3) return;
    open(sheet);
  }
  $('#sheet-x')?.addEventListener('click', () => shut(sheet, 'sheet_dismissed'));
  sheet?.addEventListener('click', (e) => { if (e.target === sheet) $('#sheet-x').click(); });
  if (isIOS && !standalone && !PRESENT) setTimeout(() => showSheet(false), 2500);

  function paintAppSheet(step) {
    const go = $('#app-sheet-go');
    if (step === 1) {
      $('#app-sheet-kicker').textContent = 'Installed · step 1 of 2';
      $('#app-sheet-title').textContent = 'Turn on alerts';
      $('#app-sheet-lede').textContent = "Your phone buzzes when Kalshi's price jumps, before your stream shows the play.";
      go.textContent = 'Enable alerts';
      go.onclick = async () => { go.disabled = true; const ok = await enable(); go.disabled = false; if (ok) paintAppSheet(2); };
    } else if (step === 2) {
      $('#app-sheet-kicker').textContent = 'Subscribed · step 2 of 2';
      $('#app-sheet-title').textContent = 'Send me a test';
      $('#app-sheet-lede').textContent = 'Tap it, then lock your phone. It should buzz within a few seconds.';
      go.textContent = 'Send me a test';
      go.onclick = async () => { go.disabled = true; const ok = await test(); go.disabled = false; if (ok) paintAppSheet(3); };
    } else {
      $('#app-sheet-kicker').textContent = 'All set';
      $('#app-sheet-title').textContent = 'Did it buzz?';
      $('#app-sheet-lede').textContent = "If not: Settings > Notifications > Kalshi Knows > Allow. Then tap Send again from Get alerts.";
      go.textContent = 'Done';
      go.onclick = () => shut(appSheet, 'app_sheet_done');
    }
  }
  $('#app-sheet-x')?.addEventListener('click', () => shut(appSheet, 'app_sheet_dismissed'));
  appSheet?.addEventListener('click', (e) => { if (e.target === appSheet) $('#app-sheet-x').click(); });
  const forceApp = new URLSearchParams(location.search).has('onboard'); // ?onboard previews the installed flow
  if (appSheet && pushOK && (standalone || forceApp) && !PRESENT
      && (forceApp || (!store.get('tested', 0) && store.get('app_sheet_dismissed', 0) < Date.now() - 6 * 3600e3 && !store.get('app_sheet_done', 0)))) {
    paintAppSheet(isSubscribed() ? 2 : 1);
    setTimeout(() => open(appSheet), 900);
  }

  // Already subscribed on this device: re-send the subscription so a restarted engine (or a dropped one) still has it.
  async function resync() {
    const api = getApi();
    if (!api || !pushOK || Notification.permission !== 'granted' || !store.get('sub', false)) return;
    try {
      const reg = await swReady();
      const sub = await reg.pushManager.getSubscription();
      await prefetch();
      if (!sub || (vapid && store.get('vapid', '') !== vapid)) { store.set('sub', false); render(); return; }
      await fetch(`${api}/api/push/subscribe`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: subBody(sub) });
    } catch {}
  }

  // "Sync to my stream": alerts land when YOUR stream shows the play (server schedules play time + your delay)
  const paintSync = () => $$('[data-sync]').forEach((b) => {
    const on = !!store.get('sync', false), svc = store.get('delayK', 'Peacock');
    b.setAttribute('aria-checked', String(on));
    b.querySelector('b').textContent = on ? `ON · ${svc} ${DELAYS[svc] ?? 48}s` : 'OFF';
  });
  $$('[data-sync]').forEach((b) => b.addEventListener('click', async () => {
    store.set('sync', !store.get('sync', false)); paintSync();
    const ok = await pushPrefs(getApi);
    note(ok ? (store.get('sync', false) ? `Synced: alerts will land when ${store.get('delayK', 'Peacock')} shows the play.` : 'Sync off: alerts arrive the moment the market knows.')
            : 'Saved on this device. Enable alerts to sync with the server.', !ok && false);
  }));
  // the Live page's delay picker (.seg-btn) changes the chosen service: keep the server's schedule in step
  document.addEventListener('click', (e) => {
    if (!e.target.closest || !e.target.closest('.seg-btn')) return;
    setTimeout(() => { paintSync(); if (store.get('sync', false)) pushPrefs(getApi); }, 60);
  });
  paintSync();
  render();
  prefetch().then(resync);
  return { render: () => { render(); prefetch(); paintSync(); } };
}
