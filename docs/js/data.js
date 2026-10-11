// Live (SSE from the backend) and Replay (data/replay.json on a loop) sources.
// Both emit: 'games' (detail: games[]), 'alert' (detail: alert), 'status' (detail: {mode, text}).
import { fetchJSON, PLAY_POINTS } from './util.js';

export async function resolveApi() {
  try {
    const override = new URLSearchParams(location.search).get('api');
    const cfg = override ? { api: override } : await fetchJSON('config.json', { timeout: 4000 });
    const api = (cfg?.api || '').replace(/\/+$/, '');
    if (!api) return null;
    const health = await fetchJSON(`${api}/api/health`, { timeout: 4500 });
    if (health?.ok) return { api, health };
  } catch (e) { /* offline → replay */ }
  return null;
}

export class LiveSource extends EventTarget {
  constructor(api, health) {
    super();
    this.api = api; this.health = health;
    this.skew = health?.now_ms ? health.now_ms - Date.now() : 0;
    this.kind = 'live';
    this.serverMode = health?.mode || 'live';
    this.lastGamesAt = 0;
  }
  now() { return Date.now() + this.skew; }
  emit(type, detail) { this.dispatchEvent(new CustomEvent(type, { detail })); }
  async start() {
    try {
      const [games, alerts] = await Promise.all([
        fetchJSON(`${this.api}/api/games`, { timeout: 6000 }).catch(() => []),
        fetchJSON(`${this.api}/api/alerts?since_ms=${this.now() - 3 * 3600e3}`, { timeout: 6000 }).catch(() => []),
      ]);
      if (games?.length) { this.lastGamesAt = Date.now(); this.emit('games', games); }
      (alerts || []).sort((a, b) => a.ts_ms - b.ts_ms).forEach((a) => this.emit('alert', { ...a, _initial: true }));
    } catch {}
    this.connect();
    // fallback poll if SSE is blocked by a proxy
    this.poll = setInterval(async () => {
      if (Date.now() - this.lastGamesAt < 8000) return;
      try {
        const g = await fetchJSON(`${this.api}/api/games`, { timeout: 4000 });
        if (g?.length) { this.lastGamesAt = Date.now(); this.emit('games', g); }
        const al = await fetchJSON(`${this.api}/api/alerts?since_ms=${this.now() - 120e3}`, { timeout: 4000 });
        (al || []).forEach((a) => this.emit('alert', a));
      } catch {}
    }, 3000);
  }
  connect() {
    // WebSocket first (Cloudflare quick tunnels buffer SSE); SSE as a fallback; polling covers both.
    this.wsFails = this.wsFails || 0;
    if ('WebSocket' in window && this.wsFails < 4) return this.connectWS();
    this.connectSSE();
  }
  connectWS() {
    let ws;
    try { ws = new WebSocket(`${this.api.replace(/^http/, 'ws')}/api/ws`); } catch { this.wsFails = 9; return this.connectSSE(); }
    this.ws = ws;
    let opened = false;
    ws.onopen = () => { opened = true; this.wsFails = 0; this.emit('status', { ok: true }); };
    ws.onmessage = (e) => {
      try {
        const m = JSON.parse(e.data);
        if (m.event === 'games') { this.lastGamesAt = Date.now(); this.emit('games', m.data); }
        else if (m.event === 'alert') this.emit('alert', m.data);
      } catch {}
    };
    ws.onclose = () => {
      if (!opened) this.wsFails++;
      this.emit('status', { ok: false });
      clearTimeout(this.reT);
      this.reT = setTimeout(() => this.connect(), Math.min(15000, 1500 * (1 + this.wsFails)));
    };
    ws.onerror = () => { try { ws.close(); } catch {} };
  }
  connectSSE() {
    if (!('EventSource' in window)) return;
    this.es?.close();
    const es = new EventSource(`${this.api}/api/stream`);
    this.es = es;
    es.addEventListener('open', () => this.emit('status', { ok: true }));
    es.addEventListener('games', (e) => {
      try { this.lastGamesAt = Date.now(); this.emit('games', JSON.parse(e.data)); } catch {}
    });
    es.addEventListener('alert', (e) => { try { this.emit('alert', JSON.parse(e.data)); } catch {} });
    es.addEventListener('error', () => { this.emit('status', { ok: false }); if (es.readyState === 2) setTimeout(() => this.connectSSE(), 5000); });
  }
  async guess(alert_id, nickname, guess) {
    try {
      await fetch(`${this.api}/api/guess`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ alert_id, nickname, guess }) });
    } catch {}
  }
  async guesses(alert_id) {
    try { return await fetchJSON(`${this.api}/api/guesses?alert_id=${encodeURIComponent(alert_id)}`, { timeout: 3000 }); }
    catch { return null; }
  }
}

const CLOCK_RE = /\((\d{1,2}:\d{2})\s*-\s*(\d)(?:st|nd|rd|th)\)/;
const WINDOW = 20 * 60e3;

export class ReplaySource extends EventTarget {
  constructor(rep) {
    super();
    this.kind = 'replay';
    this.rep = rep;
    this.hist = (rep.history || []).slice().sort((a, b) => a[0] - b[0]);
    this.alerts = (rep.alerts || []).slice().sort((a, b) => a.ts_ms - b.ts_ms);
    this.plays = (rep.plays || []).slice().sort((a, b) => a.wallclock_ms - b.wallclock_ms);
    this.t0 = this.hist[0]?.[0] ?? Date.now();
    this.t1 = this.hist.at(-1)?.[0] ?? this.t0 + 60e3;
    this.recorded = this.t0;
    const first = this.alerts[0];
    this.setCursor(first ? Math.max(this.t0, first.ts_ms - 14e3) : this.t0);
    this.fired = new Set(); this.confirmedSent = new Set();
  }
  emit(type, detail) { this.dispatchEvent(new CustomEvent(type, { detail })); }
  setCursor(c) { this.baseCursor = c; this.baseWall = performance.now(); this.last = c; }
  now() { return this.baseCursor + (performance.now() - this.baseWall); }
  start() {
    // alerts that happened before the cursor go straight into the feed
    for (const a of this.alerts) if (a.ts_ms <= this.last) { this.fired.add(a.id); this.confirmedSent.add(a.id); this.emit('alert', { ...a, _initial: true }); }
    this.tick(true);
    this.timer = setInterval(() => this.tick(), 250);
    this.gamesTimer = setInterval(() => this.emitGames(), 2000);
  }
  nextAlert() { const c = this.now(); return this.alerts.find((a) => a.ts_ms > c + 1000); }
  skip() {
    const n = this.nextAlert() || this.alerts[0];
    if (!n) return;
    if (n.ts_ms <= this.now()) this.reset();
    this.setCursor(n.ts_ms - 9e3);
    this.emitGames();
  }
  reset() { this.fired.clear(); this.confirmedSent.clear(); this.emit('reset', {}); }
  tick() {
    let c = this.now();
    if (c > this.t1 + 8e3) { // loop
      this.reset();
      const first = this.alerts[0];
      this.setCursor(first ? Math.max(this.t0, first.ts_ms - 14e3) : this.t0);
      c = this.now(); this.emitGames();
    }
    for (const a of this.alerts) {
      if (!this.fired.has(a.id) && a.ts_ms <= c) {
        this.fired.add(a.id);
        this.emit('alert', { ...a, confirmed: null });
      }
      const seen = a.confirmed?.espn_seen_ms;
      if (seen && this.fired.has(a.id) && !this.confirmedSent.has(a.id) && seen <= c) {
        this.confirmedSent.add(a.id);
        this.emit('alert', a);
      }
    }
    this.last = c;
  }
  pAt(t) {
    const h = this.hist; let lo = 0, hi = h.length - 1;
    if (!h.length) return 0.5;
    if (t <= h[0][0]) return h[0][1];
    while (lo < hi) { const m = (lo + hi + 1) >> 1; if (h[m][0] <= t) lo = m; else hi = m - 1; }
    return h[lo][1];
  }
  state(c) {
    const g = this.rep.game || {};
    let home = 0, away = 0, period = null, clockStr = null, situation = '', poss = g.possession;
    const past = this.plays.filter((p) => p.wallclock_ms <= c);
    const withScore = past.filter((p) => p.home_score != null);
    if (withScore.length) { const l = withScore.at(-1); home = l.home_score; away = l.away_score; }
    else {
      // count forward from kickoff: TD 6 (+1 PAT / +2 conversion), FG 3, safety 2
      for (const p of past) {
        let pts = PLAY_POINTS[p.type] || 0;
        if (p.type === 'TD') { const t = (p.text || '').toUpperCase(); pts = 6 + (/EXTRA POINT IS GOOD/.test(t) ? 1 : /ATTEMPT SUCCEEDS|CONVERSION.*SUCCEEDS/.test(t) ? 2 : 0); }
        if (!pts) continue;
        if (p.team === g.home) home += pts; else away += pts;
      }
      if (c >= this.t1) { home = g.home_score ?? home; away = g.away_score ?? away; }
    }
    const lp = past.at(-1);
    if (lp) {
      if (lp.period) period = lp.period;
      if (lp.clock) clockStr = lp.clock;
      const m = CLOCK_RE.exec(lp.text || '');
      if (m) { clockStr = m[1]; period = +m[2]; }
      situation = lp.text?.replace(CLOCK_RE, '').trim() || '';
      poss = lp.team || poss;
    }
    return { home_score: Math.max(0, home), away_score: Math.max(0, away), period, clock: clockStr, situation, possession: poss };
  }
  emitGames() {
    const c = this.now();
    const from = c - WINDOW;
    const history = this.hist.filter(([t]) => t >= from && t <= c);
    const g = { ...(this.rep.game || {}), ...this.state(c), status: 'in', p_home: this.pAt(c), history };
    this.emit('games', [g]);
  }
  guess() {}
  guesses() { return null; }
}
