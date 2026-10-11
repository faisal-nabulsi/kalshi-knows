// Kalshi Knows: page orchestration.
import {
  $, $$, h, esc, clamp, int, pct, cents, usd, clock, dateShort, dur, ago, nick, PLAY, PLAY_SHORT, PRESENT, SITE_URL, params,
  loadData, fetchJSON, store, EXTRA_TEAMS, onVisible, countUp, tierOf, tierAlert, tierDutch, tierKnew, tierBadge, tierLadder, TIERS,
} from './util.js';
import { resolveApi, LiveSource, ReplaySource } from './data.js';
import { liveChart, sparkline, caseChart, lagChart, payoffChart } from './charts.js';
import { registerSW, initPush } from './push.js';
import { qrSVG } from './qr.js';

if (PRESENT) document.documentElement.classList.add('present');
const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;

const S = {
  results: null, lag: 2.6, delay: store.get('delay', null), delays: [],
  games: [], featured: params.get('game') || store.get('featured', null),
  alerts: new Map(), source: null, api: null, stage: null, push: null,
  db: null, knew: null, shownTakeover: new Set(), lastAlert: null,
};
const nickname = store.get('nick', null) || (() => { const n = `Couch Coach ${100 + Math.floor(Math.random() * 900)}`; store.set('nick', n); return n; })();

// ------------------------------------------------------------ chrome
function tickClock() {
  const now = S.source ? S.source.now() : Date.now();
  $('#clock').textContent = clock(now) + (S.source?.kind === 'replay' ? '' : ' PT').replace(' PT', '');
}
setInterval(tickClock, 1000); tickClock();

function setMode(mode, text) {
  const b = $('#mode-badge'); b.dataset.mode = mode; $('#mode-text').textContent = text;
}

// nav highlight
const navLinks = $$('.nav a');
const secObs = new IntersectionObserver((es) => es.forEach((e) => {
  if (!e.isIntersecting) return;
  navLinks.forEach((a) => a.toggleAttribute('aria-current', a.getAttribute('href') === `#${e.target.id}`));
}), { rootMargin: '-45% 0px -50% 0px' });
$$('main > section[id]').forEach((s) => secObs.observe(s));

// ------------------------------------------------------------ numbers + bindings
function bind() {
  const r = S.results || {};
  const sd = r.stream_delay_reference_s || { broadcast: 19, best_stream: 48, worst_stream: 62 };
  const gap = Math.max(0, S.delay - S.lag);
  const vals = {
    lag: S.lag.toFixed(1), delay: String(S.delay), gap: gap.toFixed(1), gapRound: `${Math.round(gap)} seconds`,
    delayRange: `${sd.broadcast} to ${sd.worst_stream}`, nPlays: int(r.market_lag?.n_plays ?? 0) || 'dozens of',
    broadcast: sd.broadcast, best: sd.best_stream, worst: sd.worst_stream,
  };
  $$('[data-bind]').forEach((el) => { const v = vals[el.dataset.bind]; if (v != null) el.textContent = v; });
  S.stage?.setNumbers({ lag: S.lag, delay: S.delay });
}

function renderDelaySeg() {
  const seg = $('#delay-seg');
  $$('button', seg).forEach((b) => b.remove());
  S.delays.forEach((d) => {
    const b = h(`<button role="radio" class="seg-btn mono" aria-checked="${d.v === S.delay}">${esc(d.k)} <b>${d.v}s</b></button>`);
    b.addEventListener('click', () => { S.delay = d.v; store.set('delay', d.v); renderDelaySeg(); bind(); renderLive(); });
    seg.appendChild(b);
  });
}

// ------------------------------------------------------------ 3D stage
async function initStage() {
  const canvas = $('#gl');
  try {
    const gl = canvas.getContext('webgl2') || canvas.getContext('webgl');
    if (!gl) throw new Error('no webgl');
    const { createStage } = await import('./hero3d.js');
    const sd = S.results?.stream_delay_reference_s || {};
    S.stage = createStage(canvas, $('#gl-labels'), { lag: S.lag, delay: S.delay, worst: sd.worst_stream || 62 });
    document.body.classList.add('gl-ready');
    const story = $('#top');
    const onScroll = () => {
      const r = story.getBoundingClientRect();
      const total = story.offsetHeight - innerHeight;
      S.stage.setProgress(clamp(-r.top / total, 0, 1));
    };
    addEventListener('scroll', onScroll, { passive: true }); onScroll();
    new IntersectionObserver(([e]) => S.stage.setVisible(e.isIntersecting), { threshold: 0 }).observe(story);
  } catch (e) {
    console.warn('3D disabled:', e.message);
    document.body.classList.add('no-gl');
  }
}

// ------------------------------------------------------------ results / proof
function renderProof(res, mock) {
  const r = res || {};
  $('#proof-meta').innerHTML = `${int(r.games_analyzed || 0)} GAMES · ${int(r.market_lag?.n_plays || 0)} SCORING PLAYS${mock ? ' · <span class="sample">SAMPLE DATA</span>' : ''}`;
  lagChart($('#lag-chart'), r);
  const m = r.model || {}, d = r.detector || {};
  const lb = (r.model_leaderboard || []).slice().sort((a, b) => (b.tier || 0) - (a.tier || 0) || (a.log_loss ?? 9) - (b.log_loss ?? 9));
  const bt = r.market_lag?.by_type || {};
  $('#proof-grid').innerHTML = `
    <div class="pg-model">
      <p class="pg-k mono">PLAY CLASSIFIER · ${esc(m.name || 'model')}</p>
      <div class="pg-big">${pct(m.accuracy)}</div>
      <p class="pg-cap">of real Kalshi jumps get the right play type on the first guess, against <b>${pct(m.baseline_accuracy)}</b> for always guessing the most common play. Right answer in the top two: <b>${pct(m.top2)}</b>. Tested on ${int(m.n_test)} jumps from real games.</p>
      <div class="vs"><span style="--w:${(m.accuracy || 0) * 100}%" class="vs-sig"><i>OURS</i></span><span style="--w:${(m.baseline_accuracy || 0) * 100}%" class="vs-cold"><i>BASELINE</i></span></div>
    </div>
    <div class="pg-det">
      <p class="pg-k mono">JUMP DETECTOR · ${int(d.n_alerts)} ALERTS</p>
      <div class="pg-pair"><div><div class="pg-mid">${pct(d.precision)}</div><p>of alerts were a real scoring play or turnover <span class="mono">(precision)</span></p></div>
      <div><div class="pg-mid">${pct(d.recall)}</div><p>of those plays set off an alert <span class="mono">(recall)</span></p></div></div>
      ${Object.keys(bt).length ? `<p class="pg-k mono pg-k2">KALSHI LAG BY PLAY TYPE</p><ul class="pg-types">${Object.entries(bt).map(([k, v]) => `<li><span class="mono">${esc(PLAY_SHORT[k] || k)}</span><b class="mono">${(v.median_s ?? 0).toFixed(1)} s</b><em class="mono">n=${int(v.n)}</em></li>`).join('')}</ul>` : ''}
    </div>
    ${lb.length ? `<div class="pg-board">
      <p class="pg-k mono">MODEL LEADERBOARD · THE PREDATOR SCALE · RANKED BY LOG LOSS ON REAL KALSHI JUMPS</p>
      <table class="board"><thead><tr><th>#</th><th>Model</th><th>Tier</th><th class="num">Accuracy</th><th class="num">Top 2</th><th class="num">Log loss</th></tr></thead>
      <tbody>${lb.map((x, i) => { const t = tierOf(x, () => 6 - i); return `<tr class="row-t${t.tier}"><td class="mono">${i + 1}</td><td>${esc(x.model)}</td><td>${tierBadge(t)}<span class="board-blurb">${esc(t.blurb)}</span></td><td class="num mono">${pct(x.accuracy)}</td><td class="num mono">${pct(x.top2)}</td><td class="num mono">${(x.log_loss ?? 0).toFixed(2)}</td></tr>`; }).join('')}</tbody></table>
    </div>` : ''}`;
}

// ------------------------------------------------------------ LIVE
const featured = () => {
  const g = S.games;
  if (!g.length) return null;
  const want = S.featured;
  if (want) {
    const m = g.find((x) => x.game_id === want) || g.find((x) => x.home === want || x.away === want);
    if (m) return m;
  }
  const recent = [...S.alerts.values()].sort((a, b) => b.ts_ms - a.ts_ms)[0];
  return (recent && g.find((x) => x.game_id === recent.game_id && x.status === 'in')) || g.find((x) => x.status === 'in') || g[0];
};

let lastScores = {};
function renderGameBug(g) {
  const el = $('#gamebug');
  if (!g) { el.innerHTML = `<div class="gb-empty mono">No live NFL games right now. Showing the last recording when one is available.</div>`; return; }
  const per = g.status === 'post' ? 'FINAL' : g.status === 'pre' ? 'PREGAME' : (`${g.period ? `Q${g.period}` : ''} ${g.clock || ''}`.trim() || (S.source?.kind === 'replay' ? 'REPLAY' : 'LIVE'));
  const key = g.game_id;
  const prev = lastScores[key] || {};
  const bumpA = prev.a != null && prev.a !== g.away_score, bumpH = prev.h != null && prev.h !== g.home_score;
  lastScores[key] = { a: g.away_score, h: g.home_score };
  const p = g.p_home ?? 0.5;
  el.innerHTML = `
    <div class="gb-team ${g.possession === g.away ? 'poss' : ''}"><span class="gb-abbr">${esc(g.away)}</span><span class="gb-nick">${esc(nick(g.away))}</span><span class="gb-score ${bumpA ? 'bump' : ''}">${g.away_score ?? 0}</span><span class="gb-p mono">${cents(1 - p)}</span></div>
    <div class="gb-team ${g.possession === g.home ? 'poss' : ''}"><span class="gb-abbr">${esc(g.home)}</span><span class="gb-nick">${esc(nick(g.home))}</span><span class="gb-score ${bumpH ? 'bump' : ''}">${g.home_score ?? 0}</span><span class="gb-p mono">${cents(p)}</span></div>
    <div class="gb-clock mono"><b>${esc(per)}</b>${g.situation ? `<span>${esc(g.situation)}</span>` : ''}</div>`;
  $('#hb-game').innerHTML = `<b>${esc(g.away)} ${g.away_score ?? 0}</b> <i>at</i> <b>${esc(g.home)} ${g.home_score ?? 0}</b> <span class="mono">${esc(per)} · ${esc(g.home)} ${pct(p)}</span>`;
}

function renderGames() {
  const el = $('#games');
  const f = featured();
  const others = S.games.filter((g) => g !== f);
  if (!others.length) { el.innerHTML = ''; return; }
  el.innerHTML = `<p class="games-head mono">OTHER GAMES · TAP TO WATCH</p>` + others.map((g) => `
    <button class="game-row" data-id="${esc(g.game_id)}">
      <span class="gr-name">${esc(g.short_name || `${g.away} @ ${g.home}`)}</span>
      <span class="gr-score mono">${g.away_score ?? 0}–${g.home_score ?? 0}</span>
      <span class="gr-clock mono">${g.status === 'in' ? `Q${g.period ?? ''} ${esc(g.clock || '')}` : esc((g.status || '').toUpperCase())}</span>
      ${sparkline((g.history || []).slice(-300), 110, 28)}
      <span class="gr-p mono">${esc(g.home)} ${cents(g.p_home)}</span>
    </button>`).join('');
  $$('.game-row', el).forEach((b) => b.addEventListener('click', () => { S.featured = b.dataset.id; store.set('featured', S.featured); renderLive(); }));
}

function renderLive() {
  const g = featured();
  renderGameBug(g);
  if (g) liveChart($('#live-chart'), g, { now: S.source.now(), delay: S.delay, alerts: [...S.alerts.values()] });
  renderGames();
}

function beforeStream(a) {
  const c = a.confirmed;
  if (c?.espn_wallclock_ms) return S.delay - (a.ts_ms - c.espn_wallclock_ms) / 1000;
  return S.delay - S.lag;
}

function feedItem(a) {
  const top = a.inferred?.[0] || { type: 'OTHER', prob: 0 };
  const t = tierOf(a, tierAlert);
  const c = a.confirmed;
  const lead = Math.max(0, beforeStream(a));
  const game = S.games.find((g) => g.game_id === a.game_id);
  return `<li class="fi ${c ? 'fi-conf' : 'fi-pend'}" data-id="${esc(a.id)}">
    <div class="fi-top mono"><span>${clock(a.ts_ms)}</span><span>${esc(game?.short_name || '')}</span></div>
    <div class="fi-play"><b>${esc(nick(a.team) || a.team)}</b> ${esc(PLAY[top.type] || top.type)} <span class="fi-move mono">${pct(a.p_before)}→${pct(a.p_after)}</span></div>
    ${tierBadge(t)}
    ${c ? `<p class="fi-text">${esc(c.play_text || '')}</p>
      <p class="fi-lead"><span class="sig">Kalshi knew ${lead.toFixed(0)}s before your stream.</span>${c.lead_s != null ? ` <span class="mono">ESPN's feed caught up ${(+c.lead_s).toFixed(0)}s later.</span>` : ''}</p>`
      : `<p class="fi-text mono fi-wait">${pct(top.prob)} sure · waiting for the play-by-play to confirm</p>`}
  </li>`;
}

function renderFeed() {
  const list = [...S.alerts.values()].sort((a, b) => b.ts_ms - a.ts_ms).slice(0, 30);
  $('#feed').innerHTML = list.map(feedItem).join('');
  $('#feed-count').textContent = String(S.alerts.size);
  $('#feed-empty').hidden = list.length > 0;
}

function onAlert(a) {
  if (!a?.id) return;
  const prev = S.alerts.get(a.id);
  const merged = { ...prev, ...a, confirmed: a.confirmed || prev?.confirmed || null };
  S.alerts.set(a.id, merged);
  if (!a._initial) S.lastAlert = merged;
  else if (!S.lastAlert || merged.ts_ms > S.lastAlert.ts_ms) S.lastAlert = merged;
  renderFeed();
  if (TO.alert?.id === a.id) TO.update(merged);
  if (a._initial) return;
  const age = (S.source.now() - a.ts_ms) / 1000;
  if (!params.has('quiet') && !S.shownTakeover.has(a.id) && age < 30 && !a.confirmed) { S.shownTakeover.add(a.id); TO.open(merged); }
  renderLive();
}

// ------------------------------------------------------------ SPOILER takeover
const TO = {
  alert: null, timer: null, votes: null, mine: null, t0: 0, revealT: null,
  open(a, { demo = false } = {}) {
    clearInterval(this.timer); clearTimeout(this.revealT); clearTimeout(this.closeT);
    this.alert = a; this.mine = null; this.demo = demo;
    this.t0 = demo ? S.source.now() : a.ts_ms;
    this.votes = { TD: 0, FG: 0, TURNOVER: 0, BIG_PLAY: 0, n: 0 };
    const el = $('#takeover');
    el.classList.remove('revealed', 'done', 'shown'); el.hidden = false;
    const t = tierOf(a, tierAlert);
    el.dataset.tier = t.tier;
    const g = S.games.find((x) => x.game_id === a.game_id);
    $('#to-game').textContent = g?.short_name || a.game_id || '';
    $('#to-when').textContent = `MARKET MOVED ${clock(this.t0, { tenth: true })}`;
    const top = a.inferred?.[0] || { type: 'OTHER', prob: 0 };
    $('#to-team').textContent = nick(a.team) || a.team || '';
    $('#to-play').dataset.pre = `UP ${Math.round(Math.abs(a.delta ?? (a.p_after - a.p_before)) * 100)}¢`;
    $('#to-play').dataset.post = PLAY[top.type] || top.type;
    $('#to-play').textContent = $('#to-play').dataset.pre;
    $('#to-sure').innerHTML = `<b>${pct(top.prob)} SURE</b> · ${esc(a.team)} ${pct(a.p_before)} → ${pct(a.p_after)}`;
    $('#to-alt').textContent = (a.inferred || []).slice(1, 3).map((x) => `${(PLAY[x.type] || x.type).toLowerCase()} ${pct(x.prob)}`).join(' · ') ? `or: ${(a.inferred || []).slice(1, 3).map((x) => `${(PLAY[x.type] || x.type).toLowerCase()} ${pct(x.prob)}`).join(' · ')}` : '';
    let tierEl = $('#to-tier');
    if (!tierEl) { tierEl = h('<div class="to-tier" id="to-tier"></div>'); $('.to-count').appendChild(tierEl); }
    tierEl.innerHTML = `<p class="mono to-tier-k">PREDATOR SCALE</p>${tierLadder(t)}<p class="to-tier-blurb">${esc(t.blurb)}</p>`;
    const delayName = S.delays.find((d) => d.v === S.delay)?.k || 'your stream';
    $('#to-lower').innerHTML = `<span class="to-lower-tag">KALSHI KNOWS</span><span>The price moved at ${clock(this.t0, { tenth: true })}. You're on <b>${esc(delayName.toLowerCase())}</b>, about ${S.delay}s behind real life.${S.source.kind === 'replay' ? ' <em>REPLAY</em>' : ''}</span>`;
    this.renderVotes();
    requestAnimationFrame(() => el.classList.add('shown'));
    this.revealT = setTimeout(() => this.reveal(), reduceMotion ? 0 : 4200);
    S.stage?.kick();
    try { navigator.vibrate?.([90, 50, 90]); } catch {}
    this.timer = setInterval(() => this.tick(), 100); this.tick();
    this.pollN = 0;
  },
  reveal() {
    const el = $('#takeover'); if (el.hidden) return;
    el.classList.add('revealed'); $('#to-pre').textContent = 'SPOILER · WHAT THE MARKET SAYS HAPPENED';
    $('#to-play').textContent = $('#to-play').dataset.post;
  },
  update(a) {
    this.alert = a;
    if (a.confirmed && $('#takeover').classList.contains('done')) $('#to-alt').textContent = a.confirmed.play_text || '';
  },
  tick() {
    const el = $('#takeover'); if (el.hidden) return;
    const elapsed = (S.source.now() - this.t0) / 1000;
    const total = Math.max(1, S.delay - S.lag);
    const rem = total - elapsed;
    $('#to-count').textContent = rem > 0 ? Math.ceil(rem) : '0';
    $('#to-bar').style.transform = `scaleX(${clamp(rem / total, 0, 1)})`;
    if (rem <= 0 && !el.classList.contains('done')) {
      el.classList.add('done'); this.reveal();
      $('#to-count-label').textContent = 'ON YOUR STREAM';
      $('#to-pre').textContent = 'YOUR STREAM JUST CAUGHT UP';
      if (this.alert.confirmed?.play_text) $('#to-alt').textContent = this.alert.confirmed.play_text;
      this.closeT = setTimeout(() => this.close(), PRESENT ? 9000 : 7000);
    } else if (rem > 0) $('#to-count-label').textContent = 'ON YOUR STREAM IN';
    // votes
    if (++this.pollN % 15 === 0 && S.source.kind === 'live') {
      S.source.guesses(this.alert.id).then((v) => { if (v && TO.alert) { this.votes = { ...this.votes, ...v }; this.renderVotes(); } });
    } else if (S.source.kind !== 'live' && elapsed < 14 && this.pollN % 4 === 0) this.simVotes();
  },
  simVotes() { // replay crowd: grows for ~14s, leaning toward the model's answer
    const w = { TD: 1, FG: 1, TURNOVER: 1, BIG_PLAY: 1 };
    (this.alert.inferred || []).forEach((x) => { if (w[x.type] != null) w[x.type] += x.prob * 5; });
    const tot = Object.values(w).reduce((s, x) => s + x, 0);
    const adds = 1 + Math.floor(Math.random() * 3);
    for (let i = 0; i < adds; i++) {
      let r = Math.random() * tot;
      for (const k of Object.keys(w)) { r -= w[k]; if (r <= 0) { this.votes[k]++; this.votes.n++; break; } }
    }
    this.renderVotes();
  },
  vote(k) {
    if (this.mine) return;
    this.mine = k; this.votes[k] = (this.votes[k] || 0) + 1; this.votes.n = (this.votes.n || 0) + 1;
    S.source.guess?.(this.alert.id, nickname, k);
    this.renderVotes();
  },
  renderVotes() {
    const box = $('#to-vote');
    const n = Math.max(1, this.votes.n || Object.values(this.votes).reduce((s, x) => s + (typeof x === 'number' ? x : 0), 0));
    box.innerHTML = ['TD', 'FG', 'TURNOVER', 'BIG_PLAY'].map((k) => {
      const v = this.votes[k] || 0;
      return `<button class="vb ${this.mine === k ? 'mine' : ''}" data-k="${k}" ${this.mine ? 'disabled' : ''}>
        <span class="vb-k">${PLAY_SHORT[k]}</span><span class="vb-n mono">${v}</span><i style="transform:scaleX(${(v / n).toFixed(3)})"></i></button>`;
    }).join('');
    $$('.vb', box).forEach((b) => b.addEventListener('click', () => this.vote(b.dataset.k)));
    $('#to-vote-n').textContent = `${this.votes.n || 0} ${S.source.kind === 'live' ? 'people' : 'replay crowd'} voted${this.mine ? ` · you said ${PLAY_SHORT[this.mine]}` : ''}`;
  },
  close() {
    clearInterval(this.timer); clearTimeout(this.revealT); clearTimeout(this.closeT);
    const el = $('#takeover'); el.classList.remove('shown');
    setTimeout(() => { el.hidden = true; }, 300);
    this.alert = null;
  },
};
$('#to-close').addEventListener('click', () => TO.close());
$('#to-reveal').addEventListener('click', () => TO.reveal());

// ------------------------------------------------------------ SOMEONE KNEW
function renderKnew(data, mock) {
  if (!data) return;
  S.knew = data;
  const st = data.stats || {};
  $('#knew-meta').innerHTML = `${int(data.markets_scanned)} SETTLED MARKETS SCANNED${mock ? ' · <span class="sample">SAMPLE DATA</span>' : ''}`;
  $('#knew-stats').innerHTML = `
    <div class="ks"><div class="ks-big">${dur(st.median_lead_minutes)}</div><p>median head start the price had on the first article</p></div>
    <div class="ks"><div class="ks-big">${pct(st.share_market_first)}</div><p>of big moves happened before any news we could find</p></div>
    <div class="ks"><div class="ks-big">${int(st.n ?? (data.cases || []).length)}</div><p>case files below, each with the article that came second</p></div>`;
  const cases = (data.cases || []).slice().sort((a, b) => (b.lead_minutes || 0) - (a.lead_minutes || 0));
  $('#cases').innerHTML = cases.map((c, i) => {
    const t = tierOf(c, tierKnew);
    return `<article class="case ${i === 0 ? 'case-lead' : ''} case-t${t.tier}">
      <header class="case-head mono"><span>CASE ${String(i + 1).padStart(3, '0')}</span><span>${esc(c.category || '')}</span><span>RESOLVED ${esc((c.result || '').toUpperCase())}</span></header>
      <h3 class="case-title">${esc(c.title)}</h3>
      <div class="case-body">
        <div class="case-chart" data-case="${i}"></div>
        <div class="case-side">
          <div class="case-lead-n"><span>${esc(dur(c.lead_minutes).split(' ')[0])}</span><em>${esc(dur(c.lead_minutes).split(' ')[1] || '')}<br>head start</em></div>
          ${tierBadge(t, { blurb: true })}
        </div>
      </div>
      <blockquote class="case-news"><p>&ldquo;${esc(c.first_news_title)}&rdquo;</p>
        <cite class="mono">${c.first_news_url ? `<a href="${esc(c.first_news_url)}" target="_blank" rel="noopener">${esc(c.first_news_source || 'source')}</a>` : esc(c.first_news_source || '')} · first article ${clock(c.first_news_ms, { sec: false })}, ${dateShort(c.first_news_ms)}</cite></blockquote>
      <p class="case-verdict">${esc(c.verdict || '')}</p>
    </article>`;
  }).join('');
  drawCases();
}
function drawCases() {
  if (!S.knew) return;
  const cases = (S.knew.cases || []).slice().sort((a, b) => (b.lead_minutes || 0) - (a.lead_minutes || 0));
  $$('.case-chart').forEach((el) => caseChart(el, cases[+el.dataset.case]));
}

// ------------------------------------------------------------ DUTCH BOOK
let dbSel = null;
function renderDutch(data, { mock = false, live = false } = {}) {
  if (!data) return;
  S.db = data;
  $('#dutch-meta').innerHTML = `${live ? 'LIVE FROM THE ENGINE' : 'SNAPSHOT'} · UPDATED ${esc(ago(data.updated_ms))}${mock ? ' · <span class="sample">SAMPLE DATA</span>' : ''}`;
  const amt = $('#db-amount');
  const fmt = (v) => `$${int(v)}`;
  if (amt.dataset.seen) countUp(amt, data.total_mispricing_usd || 0, fmt, 900);
  else onVisible(amt, () => { amt.dataset.seen = 1; countUp(amt, data.total_mispricing_usd || 0, fmt, 2200); }, { threshold: 0.4 });
  $('#db-sub').textContent = `${int(data.scanned_events)} events · ${int(data.scanned_markets)} markets scanned · ${int((data.opportunities || []).length)} contradictions found`;
  const opps = (data.opportunities || []).slice().sort((a, b) => (b.profit_after_fees || 0) - (a.profit_after_fees || 0)).slice(0, 30);
  S.dbOpps = opps;
  $('#db-list').innerHTML = opps.map((o, i) => {
    const t = tierOf(o, tierDutch);
    return `<li><button class="db-item ${i === (dbSel ?? 0) ? 'on' : ''}" data-i="${i}">
      <span class="db-kind mono">${esc((o.kind || '').replace('_', ' '))}</span>
      <span class="db-title">${esc(o.title)}</span>
      <span class="db-cat mono">${esc(o.category || '')} · ${(o.legs || []).length} legs</span>
      ${tierBadge(t)}
      <span class="db-profit mono">${usd(o.profit_after_fees, { compact: true, sign: true })}</span></button></li>`;
  }).join('') || `<li class="db-none">No contradictions open right now. Kalshi is behaving.</li>`;
  $$('.db-item').forEach((b) => b.addEventListener('click', () => { dbSel = +b.dataset.i; $$('.db-item').forEach((x) => x.classList.toggle('on', x === b)); renderDbDetail(opps[dbSel]); if (innerWidth < 900) $('#db-detail').scrollIntoView({ behavior: 'smooth', block: 'start' }); }));
  renderDbDetail(opps[dbSel ?? 0]);
  const nm = (data.near_misses || []).slice(0, 4);
  const cats = Object.entries(data.by_category || {}).sort((a, b) => b[1].violations - a[1].violations).slice(0, 6);
  const maxV = Math.max(1, ...cats.map(([, v]) => v.violations));
  $('#db-near').innerHTML = `
    ${nm.length ? `<p class="db-near-k mono">NEAR MISSES · PROFITABLE UNTIL THE FEE</p><ul class="db-nm">${nm.map((o) => `<li><b>${esc(o.title)}</b><span class="mono">${usd(o.profit_before_fees, { compact: true, sign: true })} → <em>${usd(o.profit_after_fees, { compact: true, sign: true })}</em> after fees</span></li>`).join('')}</ul>` : ''}
    ${cats.length ? `<p class="db-near-k mono">WHERE THE CONTRADICTIONS LIVE</p><ul class="db-cats">${cats.map(([k, v]) => `<li><span>${esc(k)}</span><i style="--w:${(100 * v.violations / maxV).toFixed(1)}%"></i><b class="mono">${int(v.violations)}<em> / ${int(v.events)}</em></b></li>`).join('')}</ul>` : ''}`;
}
function renderDbDetail(o) {
  const el = $('#db-detail');
  if (!o) { el.innerHTML = ''; return; }
  const t = tierOf(o, tierDutch);
  const legs = o.legs || [];
  const shown = legs.slice(0, 10);
  const pa = o.profit_after_fees || 0;
  el.innerHTML = `
    <p class="dd-k mono">PAPER TRADE · ${esc((o.kind || '').replace('_', ' ').toUpperCase())} · ${esc((o.category || '').toUpperCase())}</p>
    <h3 class="dd-title">${esc(o.title)}</h3>
    <div class="dd-tier">${tierBadge(t, { blurb: true, size: 'tier-lg' })}</div>
    <p class="dd-plain">Spend <b>${usd(o.cost, { compact: true })}</b>. Whatever happens, get back at least <b>${usd(o.worst_case_payout, { compact: true })}</b>. That's <b class="sig">${usd(o.profit_before_fees, { compact: true })}</b> before fees and <b class="${pa > 0 ? 'sig' : 'cold'}">${usd(pa, { compact: true })}</b> after Kalshi's fee${pa > 0 ? '.' : ': the fee eats it.'}</p>
    <table class="legs"><thead><tr><th>Buy</th><th>Contract</th><th class="num">Price</th><th class="num">Qty</th><th class="num">Cost</th></tr></thead>
      <tbody>${shown.map((l) => `<tr><td><span class="side side-${esc(l.side)} mono">${esc((l.side || '').toUpperCase())}</span></td><td>${esc(l.label)}</td><td class="num mono">${cents(l.price)}</td><td class="num mono">${int(l.qty)}</td><td class="num mono">${usd((l.price || 0) * (l.qty || 1), { compact: true })}</td></tr>`).join('')}
      ${legs.length > shown.length ? `<tr class="legs-more"><td colspan="5" class="mono">+ ${legs.length - shown.length} more legs</td></tr>` : ''}</tbody></table>
    <div class="dd-chart" id="dd-chart"></div>
    <dl class="ledger mono">
      <div><dt>Cost</dt><dd>${usd(o.cost)}</dd></div>
      <div><dt>Worst-case payout</dt><dd>${usd(o.worst_case_payout)}</dd></div>
      <div><dt>Profit before fees</dt><dd>${usd(o.profit_before_fees, { sign: true })}</dd></div>
      <div><dt>Kalshi fees</dt><dd>−${usd(o.fees)}</dd></div>
      <div class="ledger-total"><dt>Profit after fees</dt><dd class="${pa > 0 ? 'sig' : ''}">${usd(pa, { sign: true })}</dd></div>
    </dl>
    <p class="dd-expl">${esc(o.explanation || '')}</p>`;
  payoffChart($('#dd-chart'), o);
}

// ------------------------------------------------------------ ticker
let tickerSig = '';
function renderTicker() {
  const items = [];
  S.games.forEach((g) => items.push(`<span class="tk"><b>${esc(g.short_name || `${g.away} @ ${g.home}`)}</b> ${esc(g.home)} <em class="mono">${cents(g.p_home)}</em> · ${esc(g.away)} <em class="mono">${cents(1 - (g.p_home ?? 0.5))}</em></span>`));
  const last = S.lastAlert;
  if (last) items.push(`<span class="tk tk-sig"><b>LAST SPOILER</b> ${esc(last.headline || '')}</span>`);
  if (S.db) {
    items.push(`<span class="tk"><b>DUTCH BOOK</b> <em class="mono">$${int(S.db.total_mispricing_usd)}</em> of contradictory pricing open</span>`);
    (S.dbOpps || []).slice(0, 3).forEach((o) => items.push(`<span class="tk">${esc(o.title)} <em class="mono">${usd(o.profit_after_fees, { compact: true, sign: true })}</em></span>`));
  }
  (S.knew?.cases || []).slice(0, 3).forEach((c) => items.push(`<span class="tk"><b>SOMEONE KNEW</b> ${esc(c.title)} <em class="mono">${esc(dur(c.lead_minutes))} early</em></span>`));
  const sig = items.join('');
  if (sig === tickerSig || !items.length) return;
  tickerSig = sig;
  const track = $('#ticker-track');
  track.innerHTML = `<div class="tk-run">${sig}</div><div class="tk-run" aria-hidden="true">${sig}</div>`;
  const w = track.firstElementChild.scrollWidth;
  track.style.setProperty('--dur', `${Math.max(30, w / 70)}s`);
}

// ------------------------------------------------------------ boot
async function boot() {
  registerSW();
  const resP = loadData('results'), knewP = loadData('someone_knew'), dbP = loadData('dutchbook', 45000);

  // results first: they set the story numbers
  const { data: res, mock: resMock } = await resP;
  S.results = res || {};
  const sd = S.results.stream_delay_reference_s || { broadcast: 19, best_stream: 48, worst_stream: 62 };
  S.lag = S.results.market_lag?.median_s ?? 2.6;
  S.delays = [{ k: 'Cable', v: sd.broadcast }, { k: 'Streaming', v: sd.best_stream }, { k: 'Sketchy stream', v: sd.worst_stream }];
  if (!S.delays.some((d) => d.v === S.delay)) S.delay = sd.best_stream;
  bind(); renderDelaySeg();
  initStage();
  onVisible($('#proof'), () => renderProof(S.results, resMock), { threshold: 0.05 });

  // live or replay
  const live = await resolveApi();
  if (live) {
    S.api = live.api;
    S.source = new LiveSource(live.api, live.health);
    const serverReplay = live.health.mode === 'replay';
    setMode(serverReplay ? 'replay' : 'live', serverReplay ? 'LIVE SERVER · REPLAY' : 'LIVE');
    $('#live-meta').textContent = `KALSHI PUBLIC ORDER BOOK · ${int(live.health.games_tracked)} GAMES TRACKED · UPDATES EVERY ~2 S`;
    S.source.addEventListener('status', (e) => setMode(e.detail.ok ? (serverReplay ? 'replay' : 'live') : 'warn', e.detail.ok ? (serverReplay ? 'LIVE SERVER · REPLAY' : 'LIVE') : 'RECONNECTING'));
  } else {
    const { data: rep, mock } = await loadData('replay');
    if (rep?.history?.length) {
      S.source = new ReplaySource(rep);
      setMode('replay', `REPLAY · recorded ${dateShort(S.source.recorded)}`);
      $('#live-meta').innerHTML = `REPLAY OF ${esc(rep.game?.short_name || '')}, RECORDED ${esc(dateShort(S.source.recorded).toUpperCase())} · REAL SPEED${mock ? ' · <span class="sample">SAMPLE DATA</span>' : ''}`;
      $('#skip-btn').hidden = false;
      $('#skip-btn').addEventListener('click', () => S.source.skip());
      S.source.addEventListener('reset', () => { S.alerts.clear(); S.shownTakeover.clear(); renderFeed(); });
    } else {
      setMode('off', 'OFF AIR');
      S.source = { kind: 'none', now: () => Date.now(), addEventListener() {}, start() {} };
    }
  }
  S.source.addEventListener('games', (e) => { S.games = e.detail || []; S.games.forEach((g) => Object.assign(EXTRA_TEAMS, g.team_names || {})); renderLive(); renderTicker(); });
  S.source.addEventListener('alert', (e) => onAlert(e.detail));
  S.source.start();
  setInterval(() => { if (S.games.length) renderLive(); }, 1000);

  $('#demo-btn').addEventListener('click', () => { if (S.lastAlert) TO.open(S.lastAlert, { demo: true }); });

  S.push = initPush(() => S.api);

  // other sections
  knewP.then(({ data, mock }) => { renderKnew(data, mock); renderTicker(); });
  const loadDb = async () => {
    if (S.api) {
      try { const d = await fetchJSON(`${S.api}/api/dutchbook`, { timeout: 15000 }); if (d?.opportunities) { renderDutch(d, { live: true }); renderTicker(); return true; } } catch {}
    }
    return false;
  };
  if (!(await loadDb())) dbP.then(({ data, mock }) => { renderDutch(data, { mock }); renderTicker(); });
  if (S.api) setInterval(loadDb, 60000);

  // QR codes
  const url = SITE_URL;
  $('#get-url').textContent = url.replace(/^https?:\/\//, '');
  qrSVG(url).then((svg) => { $('#get-qr').innerHTML = svg; if (PRESENT) { $('#pqr-code').innerHTML = svg; $('#pqr').hidden = false; } }).catch(() => {});

  // resize charts
  let rT;
  addEventListener('resize', () => { clearTimeout(rT); rT = setTimeout(() => { renderLive(); drawCases(); if (S.results && $('#lag-chart').innerHTML) lagChart($('#lag-chart'), S.results); if (S.dbOpps) renderDbDetail(S.dbOpps[dbSel ?? 0]); }, 150); });
}

// keyboard: presenter controls
addEventListener('keydown', (e) => {
  if (e.target.matches('input, textarea')) return;
  const k = e.key.toLowerCase();
  if (k === 'escape') TO.close();
  else if (k === 't' && S.lastAlert) TO.open(S.lastAlert, { demo: true });
  else if (k === 'n' && S.source?.skip) S.source.skip();
  else if (k === 'r') TO.reveal();
  else if ('12345'.includes(k) && k) $(['#live', '#knew', '#dutch', '#proof', '#get'][+k - 1])?.scrollIntoView({ behavior: 'smooth' });
});

boot().catch((e) => console.error(e));
