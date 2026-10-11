// Shared helpers: DOM, formatting, teams, tiers, data loading.
export const $ = (s, r = document) => r.querySelector(s);
export const $$ = (s, r = document) => [...r.querySelectorAll(s)];
export const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
export const lerp = (a, b, t) => a + (b - a) * t;
export const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

export function h(html) {
  const t = document.createElement('template');
  t.innerHTML = html.trim();
  return t.content.firstElementChild;
}

export const params = new URLSearchParams(location.search);
export const PRESENT = params.has('present');
export const SITE_URL = (location.hostname === 'localhost' || location.hostname === '127.0.0.1')
  ? 'https://faisal-nabulsi.github.io/kalshi-knows/'
  : location.origin + location.pathname.replace(/index\.html$/, '');

// ---------- formatting ----------
const nf0 = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 });
export const int = (v) => nf0.format(Math.round(v ?? 0));
export const pct = (p, d = 0) => `${(100 * (p ?? 0)).toFixed(d)}%`;
export const cents = (p) => `${Math.round(100 * (p ?? 0))}¢`;
export function usd(v, { compact = false, sign = false } = {}) {
  v = Number(v) || 0;
  const s = sign && v > 0 ? '+' : v < 0 ? '−' : '';
  const a = Math.abs(v);
  let body;
  if (compact && a >= 1e6) body = `$${(a / 1e6).toFixed(a >= 1e7 ? 1 : 2)}M`;
  else if (compact && a >= 1e4) body = `$${(a / 1e3).toFixed(1)}K`;
  else if (a >= 100) body = `$${nf0.format(a)}`;
  else body = `$${a.toFixed(2)}`;
  return s + body;
}
export function clock(ms, { sec = true, tenth = false } = {}) {
  const d = new Date(ms);
  let hh = d.getHours(); const ap = hh >= 12 ? 'PM' : 'AM'; hh = hh % 12 || 12;
  const mm = String(d.getMinutes()).padStart(2, '0');
  const ss = String(d.getSeconds()).padStart(2, '0');
  const t = tenth ? `.${Math.floor(d.getMilliseconds() / 100)}` : '';
  return sec ? `${hh}:${mm}:${ss}${t} ${ap}` : `${hh}:${mm} ${ap}`;
}
export function dateShort(ms) {
  return new Date(ms).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
}
export function dur(min) {
  if (min == null) return '–';
  if (min < 1) return `${Math.round(min * 60)} s`;
  if (min < 120) return `${Math.round(min)} min`;
  if (min < 48 * 60) return `${(min / 60).toFixed(min < 600 ? 1 : 0)} hr`;
  return `${(min / 1440).toFixed(1)} days`;
}
export function ago(ms, now = Date.now()) {
  const s = Math.max(0, (now - ms) / 1000);
  if (s < 60) return `${Math.round(s)}s ago`;
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  if (s < 86400) return `${Math.round(s / 3600)} hr ago`;
  return `${Math.round(s / 86400)} days ago`;
}

// ---------- NFL ----------
export const TEAMS = {
  ARI: 'Cardinals', ATL: 'Falcons', BAL: 'Ravens', BUF: 'Bills', CAR: 'Panthers', CHI: 'Bears', CIN: 'Bengals', CLE: 'Browns',
  DAL: 'Cowboys', DEN: 'Broncos', DET: 'Lions', GB: 'Packers', HOU: 'Texans', IND: 'Colts', JAX: 'Jaguars', KC: 'Chiefs',
  LV: 'Raiders', LAC: 'Chargers', LAR: 'Rams', LA: 'Rams', MIA: 'Dolphins', MIN: 'Vikings', NE: 'Patriots', NO: 'Saints',
  NYG: 'Giants', NYJ: 'Jets', PHI: 'Eagles', PIT: 'Steelers', SF: '49ers', SEA: 'Seahawks', TB: 'Buccaneers', TEN: 'Titans',
  WAS: 'Commanders', WSH: 'Commanders',
};
export const EXTRA_TEAMS = {};
export const nick = (abbr) => EXTRA_TEAMS[abbr] || TEAMS[abbr] || abbr || '';
export const PLAY = { TD: 'Touchdown', FG: 'Field goal', TURNOVER: 'Turnover', BIG_PLAY: 'Big play', SAFETY: 'Safety', OTHER: 'Big swing' };
export const PLAY_SHORT = { TD: 'TD', FG: 'FG', TURNOVER: 'TURNOVER', BIG_PLAY: 'BIG PLAY', SAFETY: 'SAFETY', OTHER: 'SWING' };
export const PLAY_POINTS = { TD: 7, FG: 3, SAFETY: 2 };

// ---------- the Predator Scale ----------
export const TIERS = {
  1: { name: 'Dugar', animal: 'DUGAR', blurb: 'Still on the waitlist for his own pre-seed round.' },
  2: { name: 'House Cat', animal: 'HOUSE CAT', blurb: "Pre-revenue, pre-product, pre-awake. 'Building in stealth' since 2023." },
  3: { name: 'Gazelle', animal: 'GAZELLE', blurb: "Fast, pretty, and somebody's lunch. Series A tourist." },
  4: { name: 'Everyone Else', animal: 'EVERYONE ELSE', blurb: 'A 40-slide consulting deck with no recommendation.' },
  5: { name: 'Lion', animal: 'LION', blurb: 'Tier-1 partner. Eats the gazelle, takes the board seat.' },
  6: { name: 'Kevin & Faisal', animal: 'KEVIN & FAISAL', blurb: 'Returned the fund. Twice.' },
};
export const tierAlert = (a) => {
  const p = Math.max(0, ...(a?.inferred || []).map((x) => x.prob || 0));
  return p < 0.35 ? 1 : p < 0.5 ? 2 : p < 0.65 ? 3 : p < 0.8 ? 4 : p < 0.9 ? 5 : 6;
};
export const tierDutch = (o) => {
  const r = o?.cost ? (o.profit_after_fees || 0) / o.cost : 0;
  return r <= 0 ? 1 : r < 0.005 ? 2 : r < 0.01 ? 3 : r < 0.02 ? 4 : r < 0.05 ? 5 : 6;
};
export const tierKnew = (c) => {
  const m = c?.lead_minutes ?? 0;
  return m <= 0 ? 1 : m < 30 ? 2 : m < 60 ? 3 : m < 120 ? 4 : m < 360 ? 5 : 6;
};
export function tierOf(obj, fn) {
  const t = clamp(Math.round(obj?.tier || fn(obj) || 1), 1, 6);
  return { tier: t, name: obj?.tier_name || TIERS[t].name, blurb: obj?.tier_blurb || TIERS[t].blurb };
}
// compact badge: six rungs + name
export function tierBadge(t, { blurb = false, size = '' } = {}) {
  const rungs = [1, 2, 3, 4, 5, 6].map((i) => `<i class="${i <= t.tier ? 'on' : ''}"></i>`).join('');
  return `<span class="tier tier-${t.tier} ${size}" title="Predator Scale ${t.tier}/6: ${esc(t.name)}. ${esc(t.blurb)}">
    <span class="tier-rungs" aria-hidden="true">${rungs}</span>
    <span class="tier-n mono">T${t.tier}</span><span class="tier-name">${esc(t.name)}</span>
    ${blurb ? `<span class="tier-blurb">${esc(t.blurb)}</span>` : ''}</span>`;
}
// full ladder, highlighted at t
export function tierLadder(t) {
  return `<ol class="ladder" aria-label="Predator Scale: tier ${t.tier} of 6">${[6, 5, 4, 3, 2, 1].map((i) =>
    `<li class="${i === t.tier ? 'on' : ''} l-${i}"><span class="mono">${i}</span>${esc(TIERS[i].name)}</li>`).join('')}</ol>`;
}

// ---------- data ----------
export async function fetchJSON(url, { timeout = 8000, noStore = true, ...opts } = {}) {
  const ctl = new AbortController();
  const id = setTimeout(() => ctl.abort(), timeout);
  try {
    const r = await fetch(url, { cache: noStore ? 'no-store' : 'default', signal: ctl.signal, ...opts });
    if (!r.ok) throw new Error(`${r.status} ${url}`);
    return await r.json();
  } finally { clearTimeout(id); }
}
// real file first, then the mock. Returns {data, mock}
export async function loadData(name, timeout = 20000) {
  try { return { data: await fetchJSON(`data/${name}.json`, { timeout }), mock: false }; }
  catch (e) {
    try { return { data: await fetchJSON(`data/${name}.mock.json`), mock: true }; }
    catch { return { data: null, mock: true }; }
  }
}

export const store = {
  get(k, d) { try { const v = localStorage.getItem('kk_' + k); return v == null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem('kk_' + k, JSON.stringify(v)); } catch {} },
};

export function onVisible(el, fn, { once = true, threshold = 0.2 } = {}) {
  if (!el) return;
  const io = new IntersectionObserver((es) => es.forEach((e) => {
    if (e.isIntersecting) { fn(e); if (once) io.disconnect(); }
  }), { threshold });
  io.observe(el);
}

export function countUp(el, to, fmt, ms = 1600) {
  const from = Number(el.dataset.v || 0);
  const t0 = performance.now();
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const step = (now) => {
    const k = reduce ? 1 : Math.min(1, (now - t0) / ms);
    const e = 1 - Math.pow(1 - k, 4);
    el.textContent = fmt(from + (to - from) * e);
    if (k < 1) requestAnimationFrame(step); else el.dataset.v = to;
  };
  requestAnimationFrame(step);
}
