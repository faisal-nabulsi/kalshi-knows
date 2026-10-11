// Install-as-app + Web Push (iOS 16.4+ needs the installed PWA and a tap).
import { $, h, esc, store, PRESENT, fetchJSON } from './util.js';

export const isIOS = /iP(hone|od|ad)/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
export const standalone = matchMedia('(display-mode: standalone)').matches || navigator.standalone === true;
const pushOK = 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;

function urlBase64ToUint8Array(b64) {
  const pad = '='.repeat((4 - (b64.length % 4)) % 4);
  const raw = atob((b64 + pad).replace(/-/g, '+').replace(/_/g, '/'));
  return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
}

// navigator.serviceWorker.ready never settles if registration failed; don't let the button hang on it
const swReady = (ms = 8000) => Promise.race([navigator.serviceWorker.ready,
  new Promise((_, rej) => setTimeout(() => rej(new Error('the service worker did not start; reload and try again')), ms))]);

export function registerSW() {
  if (!('serviceWorker' in navigator)) return;
  navigator.serviceWorker.register('./sw.js', { scope: './' }).catch((e) => console.warn('sw', e));
}

export function initPush(getApi) {
  const box = $('#get-main');
  let vapid = null;
  const prefetch = async () => {
    const api = getApi(); if (!api || vapid) return;
    try { vapid = (await fetchJSON(`${api}/api/push/vapid`, { timeout: 5000 }))?.publicKey || null; } catch {}
  };

  function render() {
    const api = getApi();
    const subscribed = store.get('sub', false) && pushOK && Notification.permission === 'granted';
    let html = '';
    if (isIOS && !standalone) {
      html = `<p class="get-lede">On iPhone, alerts only work from the home-screen app. Three taps:</p>
        <ol class="get-steps">
          <li><b>Share</b><span>Tap the Share button in Safari's toolbar.</span></li>
          <li><b>Add to Home Screen</b><span>Scroll the share sheet and tap it.</span></li>
          <li><b>Open it</b><span>Launch Kalshi Knows from your home screen, then tap Enable spoiler alerts.</span></li>
        </ol>
        <button class="btn-sig" id="show-sheet">Show me how</button>`;
    } else if (!pushOK) {
      html = `<p class="get-lede">This browser can't receive web push. Keep this tab open: spoilers still take over the screen live. On iPhone, use Safari (iOS 16.4 or newer).</p>`;
    } else if (subscribed) {
      html = `<p class="get-lede"><span class="sig">You're in.</span> Your phone buzzes the moment the market jumps on a live game.</p>
        <div class="get-btns"><button class="btn-sig" id="push-test">Send me a test spoiler</button>
        <button class="btn-ghost mono" id="push-redo">Re-subscribe</button></div>`;
    } else {
      html = `<p class="get-lede">${standalone ? 'Installed. One more tap:' : 'Works right here in Chrome, Edge and Firefox. No install needed.'}</p>
        <div class="get-btns"><button class="btn-sig" id="push-enable">Enable spoiler alerts</button></div>`;
    }
    html += `<p class="get-note mono" id="push-note">${api ? 'Live server connected.' : 'Live server offline right now: alerts switch on when the engine is running.'}</p>`;
    box.innerHTML = html;
    $('#show-sheet', box)?.addEventListener('click', () => showSheet(true));
    $('#push-enable', box)?.addEventListener('click', enable);
    $('#push-redo', box)?.addEventListener('click', enable);
    $('#push-test', box)?.addEventListener('click', test);
  }
  const note = (t, bad) => { const n = $('#push-note'); if (n) { n.textContent = t; n.classList.toggle('bad', !!bad); } };

  async function enable() {
    const api = getApi();
    if (!api) { note('The live server is offline, so there is nothing to subscribe to yet. Try again during the game.', true); return; }
    let perm;
    try { perm = await Notification.requestPermission(); } catch { perm = Notification.permission; }
    if (perm !== 'granted') { note(perm === 'denied' ? 'Notifications are blocked. Turn them on in Settings > Notifications > Kalshi Knows.' : 'No permission, no spoilers.', true); return; }
    try {
      note('Subscribing…');
      const reg = await swReady();
      if (!vapid) await prefetch();
      if (!vapid) throw new Error('no VAPID key from the server');
      let sub = await reg.pushManager.getSubscription();
      if (sub && store.get('vapid', '') !== vapid) { await sub.unsubscribe(); sub = null; }
      if (!sub) sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: urlBase64ToUint8Array(vapid) });
      const r = await fetch(`${api}/api/push/subscribe`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(sub.toJSON()) });
      if (!r.ok) throw new Error(`server said ${r.status}`);
      store.set('sub', true); store.set('vapid', vapid);
      render(); note('Subscribed. Tap "Send me a test spoiler" to check it buzzes.');
    } catch (e) { note(`Couldn't subscribe: ${e.message || e}`, true); }
  }
  async function test() {
    const api = getApi(); if (!api) return note('Live server offline.', true);
    try { const sub = await (await navigator.serviceWorker.ready).pushManager.getSubscription(); const r = await fetch(`${api}/api/push/test`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ endpoint: sub && sub.endpoint }) }); note(r.ok ? 'Test sent. It should land in a second or two.' : `Server said ${r.status}`, !r.ok); }
    catch (e) { note(`Test failed: ${e.message}`, true); }
  }

  // bottom sheet for iOS Safari
  const sheet = $('#ios-sheet');
  function showSheet(force) {
    if (!sheet || PRESENT) return;
    if (!force && store.get('sheet_dismissed', 0) > Date.now() - 6 * 3600e3) return;
    sheet.hidden = false; requestAnimationFrame(() => sheet.classList.add('open'));
  }
  $('#sheet-x')?.addEventListener('click', () => { sheet.classList.remove('open'); store.set('sheet_dismissed', Date.now()); setTimeout(() => (sheet.hidden = true), 350); });
  sheet?.addEventListener('click', (e) => { if (e.target === sheet) $('#sheet-x').click(); });
  if (isIOS && !standalone && !PRESENT) setTimeout(() => showSheet(false), 7000);

  // Already subscribed on this device: re-send the subscription so a restarted engine (or a dropped one) still has it.
  async function resync() {
    const api = getApi();
    if (!api || !pushOK || Notification.permission !== 'granted' || !store.get('sub', false)) return;
    try {
      const reg = await swReady();
      const sub = await reg.pushManager.getSubscription();
      await prefetch();
      if (!sub || (vapid && store.get('vapid', '') !== vapid)) { store.set('sub', false); render(); return; }
      await fetch(`${api}/api/push/subscribe`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(sub.toJSON()) });
    } catch {}
  }

  render();
  prefetch().then(resync);
  return { render: () => { render(); prefetch(); } };
}
