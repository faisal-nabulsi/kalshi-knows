// Kalshi Knows: page orchestration.
import {
  $, $$, h, esc, clamp, int, pct, cents, usd, clock, dateShort, dur, ago, nick, PLAY, PLAY_SHORT, PRESENT, SITE_URL, params,
  loadData, fetchJSON, store, EXTRA_TEAMS, emblem, teamProbs, centsOr, TIER_CRIT, playFx, onVisible, countUp, tierOf, tierAlert, tierDutch, tierKnew, tierBadge, tierLadder, TIERS,
} from './util.js';
import { resolveApi, LiveSource, ReplaySource } from './data.js';
import { liveChart, sparkline, caseChart, lagChart, payoffChart } from './charts.js';
import { registerSW, initPush, initShield, onShield, shieldOn } from './push.js';
import { qrSVG } from './qr.js';

if (PRESENT) document.documentElement.classList.add('present');
const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;

const S = {
  results: null, lag: 2.6, delay: null, delayK: store.get('delayK', 'Peacock'), delays: [],
  games: [], featured: params.get('game') || store.get('featured', null),
  alerts: new Map(), source: null, api: null, stage: null, push: null,
  db: null, knew: null, shownTakeover: new Set(), lastAlert: null,
  day: new Map(), tally: null, unveiled: new Set(),
};
const nickname = store.get('nick', null) || (() => { const n = `Couch Coach ${100 + Math.floor(Math.random() * 900)}`; store.set('nick', n); return n; })();

// ------------------------------------------------------------ chrome
function tickClock() {
  const now = S.source ? S.source.now() : Date.now();
  $('#clock').textContent = clock(now) + (S.source?.kind === 'replay' ? '' : ' PT').replace(' PT', '');
}
setInterval(tickClock, 1000); tickClock();

function setMode(mode, text, detail = '') {
  const b = $('#mode-badge'); b.dataset.mode = mode;
  $('#mode-text').innerHTML = `${esc(text)}${detail ? `<span class="mode-detail"> · ${esc(detail)}</span>` : ''}`;
}


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
    const b = h(`<button role="radio" class="seg-btn mono" aria-checked="${d.k === S.delayK}">${esc(d.k)} <b>${d.v}s</b></button>`);
    b.addEventListener('click', () => { S.delay = d.v; S.delayK = d.k; store.set('delayK', d.k); renderDelaySeg(); bind(); renderLive(); renderReceipts(); });
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
      if (story.hidden) return;
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
  $('#proof-meta').innerHTML = `${r.games_analyzed ? `${int(r.games_analyzed)} GAMES · ` : ''}${int(r.market_lag?.n_plays || 0)} PLAYS LINED UP${mock ? ' · <span class="sample">SAMPLE DATA</span>' : ''}`;
  lagChart($('#lag-chart'), r);
  const m = r.model || {}, d = r.detector || {};
  // honest headline (lead review, 12:15): forward-in-time test, baseline on the same rows. results.json can override.
  const fw = { accuracy: 0.724, baseline: 0.571, n: 569, games: 58, ...(m.forward_test || r.forward_test || {}) };
  const lb = (r.model_leaderboard || []).slice().sort((a, b) => (b.tier || 0) - (a.tier || 0) || (a.log_loss ?? 9) - (b.log_loss ?? 9));
  const bt = r.market_lag?.by_type || {};
  $('#proof-grid').innerHTML = `
    <div class="pg-model">
      <p class="pg-k mono">PLAY CLASSIFIER · TRAINED ON 2025 GAMES, TESTED ON 2026 GAMES IT NEVER SAW</p>
      <div class="pg-big">${pct(fw.accuracy)}</div>
      <p class="pg-cap">of price jumps get the right play named, vs <b>${pct(fw.baseline)}</b> for always guessing "nothing big" (same ${int(fw.n)} jumps, ${int(fw.games)} games).${m.accuracy ? ` If you already know a big play happened, the upper bound is ${pct(m.accuracy)} (${int(m.n_test ?? 0)} plays).` : ''}</p>
      <div class="vs"><span style="--w:${fw.accuracy * 100}%" class="vs-sig"><i>OURS</i></span><span style="--w:${fw.baseline * 100}%" class="vs-cold"><i>ALWAYS "NOTHING BIG"</i></span></div>
    </div>
    <div class="pg-det">
      <p class="pg-k mono">JUMP DETECTOR · ${int(d.n_alerts)} ALERTS</p>
      <div class="pg-pair"><div><div class="pg-mid">${pct(d.precision)}</div><p>of alerts were a TD, field goal, turnover or 20+ yard play <span class="mono">(precision)</span></p></div>
      <div><div class="pg-mid">${pct(d.recall)}</div><p>of those plays set off an alert <span class="mono">(recall)</span>. If the market barely moves, we can't see the play.</p></div></div>
      ${Object.keys(bt).length ? `<p class="pg-k mono pg-k2">KALSHI LAG BY PLAY TYPE</p><ul class="pg-types">${Object.entries(bt).map(([k, v]) => `<li><span class="mono">${esc(PLAY_SHORT[k] || k)}</span><b class="mono">${(v.median_s ?? 0).toFixed(1)} s</b><em class="mono">n=${int(v.n)}</em></li>`).join('')}</ul>` : ''}
    </div>
    <div class="pg-bench">
      <p class="pg-k mono">HEAD-TO-HEAD VS CLAUDE OPUS 5.5 · 150 UNSEEN 2026 JUMPS · SAME INPUTS</p>
      <h3 class="pb-title">Ties the best frontier model on accuracy, beats it on calibration, in 7 ms.</h3>
      <table class="board pb-table"><thead><tr><th>Model</th><th class="num">Accuracy</th><th class="num">Log loss</th><th class="num">Brier</th></tr></thead><tbody>
        ${BENCH.map((b) => `<tr class="${b.ours ? 'pb-ours' : ''}"><td>${esc(b.name)}</td><td class="num mono"><span class="pb-bar" style="--w:${(b.acc * 100).toFixed(1)}%"></span>${(b.acc * 100).toFixed(1)}%</td><td class="num mono">${b.ll.toFixed(3)}</td><td class="num mono">${b.brier.toFixed(3)}</td></tr>`).join('')}
      </tbody></table>
      <p class="pb-note mono">Lower log loss and Brier score mean better-calibrated confidence. The 1.3-point accuracy gap is within noise (95% interval: -7 to +11 points). Kalshi Knows was trained on 2025 games only; Claude was zero-shot with the same game state and price move.</p>
    </div>
    ${lb.length ? `<div class="pg-board">
      <p class="pg-k mono">MODEL LEADERBOARD · THE PREDATOR SCALE · RANKED BY LOG LOSS ON REAL KALSHI JUMPS</p>
      <table class="board"><thead><tr><th>#</th><th>Model</th><th>Tier</th><th class="num">Accuracy</th><th class="num">Top 2</th><th class="num">Log loss</th></tr></thead>
      <tbody>${lb.map((x, i) => { const t = tierOf(x, () => 6 - i); return `<tr class="row-t${t.tier}"><td class="mono">${i + 1}</td><td>${esc(String(x.model).replace(/_/g, " "))}</td><td>${tierBadge(t)}<span class="board-blurb">${esc(t.blurb)}</span></td><td class="num mono">${pct(x.accuracy)}</td><td class="num mono">${pct(x.top2)}</td><td class="num mono">${(x.log_loss ?? 0).toFixed(2)}</td></tr>`; }).join('')}</tbody></table>
    </div>` : ''}`;
}

// train/out/claude_bench.json (n = 150): numbers copied here because train/ isn't published
const BENCH = [
  { name: 'Kalshi Knows (trained on 2025 only)', acc: 0.773, ll: 0.513, brier: 0.301, ours: true },
  { name: 'Claude Opus 5.5 (zero-shot, same inputs)', acc: 0.760, ll: 0.615, brier: 0.354 },
  { name: 'Always guess "nothing big"', acc: 0.647, ll: 4.881, brier: 0.707 },
];

// ------------------------------------------------------------ LIVE
// "Two venues, one game" panel under the game tiles: lazy-loaded, silent if the engine has no /api/venues
let venuesUnmount = null;
function mountVenuesPanel(api) {
  try {
    venuesUnmount?.(); venuesUnmount = null;
    let el = document.getElementById('venues');
    if (!el) { el = document.createElement('div'); el.id = 'venues'; document.getElementById('games')?.after(el); }
    import('./venues.js').then((m) => { venuesUnmount = m.mountVenues(el, api); }).catch(() => {});
  } catch (e) { /* optional panel */ }
}

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
  const hasP = g.p_home != null;
  const p = g.p_home ?? 0.5;
  el.innerHTML = `
    <div class="gb-team ${g.possession === g.away ? 'poss' : ''}"><span class="gb-abbr">${esc(g.away)}</span><span class="gb-nick">${esc(nick(g.away))}</span><span class="gb-score ${bumpA ? 'bump' : ''}">${g.away_score ?? 0}</span><span class="gb-p mono">${hasP ? cents(1 - p) : '–'}</span></div>
    <div class="gb-team ${g.possession === g.home ? 'poss' : ''}"><span class="gb-abbr">${esc(g.home)}</span><span class="gb-nick">${esc(nick(g.home))}</span><span class="gb-score ${bumpH ? 'bump' : ''}">${g.home_score ?? 0}</span><span class="gb-p mono">${hasP ? cents(p) : '–'}</span></div>
    <div class="gb-clock mono"><b>${esc(per)}</b>${g.situation ? `<span>${esc(g.situation)}</span>` : ''}</div>`;
  $('#hb-game').innerHTML = `<b>${esc(g.away)} ${g.away_score ?? 0}</b> <i>at</i> <b>${esc(g.home)} ${g.home_score ?? 0}</b> <span class="mono">${esc(per)}${hasP ? ` · ${esc(g.home)} ${pct(p)}` : ''}</span>`;
}

function renderGames() {
  const el = $('#games');
  const f = featured();
  const rank = { in: 0, pre: 1, post: 2 };
  const others = S.games.filter((g) => g !== f).sort((a, b) => (rank[a.status] ?? 1) - (rank[b.status] ?? 1));
  if (!others.length) { el.innerHTML = ''; return; }
  el.innerHTML = `<p class="games-head mono">OTHER GAMES · TAP TO WATCH</p>` + others.map((g) => `
    <button class="game-row" data-id="${esc(g.game_id)}">
      <span class="gr-name">${esc(g.short_name || `${g.away} @ ${g.home}`)}</span>
      <span class="gr-score mono">${g.away_score ?? 0}–${g.home_score ?? 0}</span>
      <span class="gr-clock mono">${g.status === 'in' ? `Q${g.period ?? ''} ${esc(g.clock || '')}` : g.status === 'post' ? 'FINAL' : g.status === 'pre' ? 'PREGAME' : esc((g.status || '').toUpperCase())}</span>
      ${sparkline((g.history || []).slice(-300), 110, 28)}
      <span class="gr-p mono">${g.p_home != null ? `${esc(g.home)} ${cents(g.p_home)}` : '–'}</span>
    </button>`).join('');
  $$('.game-row', el).forEach((b) => b.addEventListener('click', () => { S.featured = b.dataset.id; store.set('featured', S.featured); renderLive(); }));
}

function renderLive() {
  if (route !== 'live') return;
  const g = featured();
  renderGameBug(g);
  if (g) liveChart($('#live-chart'), g, { now: S.source.now(), delay: S.delay, alerts: [...S.alerts.values()] });
  renderGames();
}

// when the play happened: ESPN's own timestamp if we have it, else the price jump start minus the median market lag
function playMs(a) {
  const w = a.confirmed?.espn_wallclock_ms;
  if (w) return w;
  if (a.jump_started_ms) return a.jump_started_ms - S.lag * 1000;
  return a.ts_ms - S.lag * 1000;
}
// seconds between our alert and the moment the chosen stream shows the play
function beforeStream(a) { return S.delay - (a.ts_ms - playMs(a)) / 1000; }

// what ESPN says happened; swing plays (no TD/FG/turnover/20+ yd play, but ESPN's win probability moved 5+ pts)
const isSwing = (c) => c?.play_type === 'SWING';
const swingLabel = (c) => `Real swing play${c.swing_kind && c.swing_kind !== 'Swing play' ? `: ${c.swing_kind}` : ''}${c.swing_detail ? ` — ${c.swing_detail}` : ''}`;
const confText = (c) => !c ? '' : isSwing(c) ? `${swingLabel(c)}${c.play_text ? ` · ${c.play_text}` : ''}` : (c.play_text || '');
const isReplay = () => S.source?.kind === 'replay' || S.source?.serverMode === 'replay';
const callOf = (a) => {
  const top = a.inferred?.[0] || { type: 'OTHER', prob: 0 };
  const team = nick(a.team) || a.team || '';
  return a.named === false || top.type === 'OTHER' ? { team, play: `Big swing`, prob: null } : { team, play: PLAY[top.type] || top.type, prob: top.prob };
};
function feedItem(a) {
  const top = a.inferred?.[0] || { type: 'OTHER', prob: 0 };
  const call = callOf(a);
  const c = a.confirmed;
  const tp = teamProbs(a);
  const lead = Math.max(0, beforeStream(a));
  const game = S.games.find((g) => g.game_id === a.game_id);
  return `<li class="fi ${c ? 'fi-conf' : 'fi-pend'} ${S.unveiled.has(a.id) ? 'unveil' : ''}" data-id="${esc(a.id)}">
    <div class="fi-top mono"><span>${clock(a.ts_ms)}</span><span>${esc(game?.short_name || a.short_name || '')}</span></div>
    <div class="shroud"><div class="fi-play"><b>${esc(call.team)}</b> ${esc(call.play)} <span class="fi-move mono">${pct(tp.before)}→${pct(tp.after)}</span></div>
    ${c ? `<p class="fi-text">${esc(confText(c))}</p>
      <p class="fi-lead">${lead >= 1 ? `<span class="sig">${lead.toFixed(0)}s before ${esc(S.delayK)} showed it.</span>` : `<span>On ${esc(S.delayK)}, you saw this one first.</span>`}${c.lead_s > 0 ? ` <span class="mono">Arrived ${(+c.lead_s).toFixed(0)}s before the same play showed up in ESPN's public play-by-play feed.</span>` : ''}</p>`
      : `<p class="fi-text mono fi-wait">${call.prob != null ? `${pct(top.prob)} sure · ` : ''}${gradeOf(a) === 'no_match' ? 'ESPN shows no matching play' : 'waiting for the play-by-play to confirm'}</p>`}</div>
    <span class="shroud-tap mono">Spoiler Shield · tap to reveal</span>
  </li>`;
}

const feedSeen = new Set();
function renderFeed() {
  const list = [...S.alerts.values()].sort((a, b) => b.ts_ms - a.ts_ms).slice(0, 30);
  $('#feed').innerHTML = list.map((a) => { const html = feedItem(a); if (feedSeen.has(a.id)) return html; feedSeen.add(a.id); return html.replace('class="fi ', 'class="fi fi-new '); }).join('');
  $('#feed-count').textContent = String(S.alerts.size);
  $('#feed-empty').hidden = list.length > 0;
  const leads = [...S.alerts.values()].map((a) => +a.confirmed?.lead_s).filter((v) => v > 0).sort((a, b) => a - b);
  const sum = $('#feed-sum');
  if (sum) {
    sum.hidden = !leads.length;
    const med = leads.length ? leads[Math.floor((leads.length - 1) / 2)] : 0;
    const rng = leads.length > 1 ? `${leads[0].toFixed(0)}-${leads[leads.length - 1].toFixed(0)} s` : `${leads[0]?.toFixed(0)} s`;
    sum.innerHTML = `Our alerts arrived <b>${rng}</b> before the same play showed up in ESPN's public play-by-play feed, which we check every few seconds (${leads.length} matched play${leads.length === 1 ? '' : 's'}${leads.length > 4 ? `, median ${med.toFixed(0)} s` : ''}).`;
  }
}

function onAlert(a) {
  if (!a?.id) return;
  const prev = S.alerts.get(a.id);
  if (prev && !!prev.confirmed === !!a.confirmed && (prev.grade ?? null) === (a.grade ?? null)
    && (prev.stage ?? null) === (a.stage ?? null) && prev.headline === a.headline && !a._initial) return; // nothing new (stage 1 -> 2 is new)
  const merged = { ...prev, ...a, confirmed: a.confirmed || prev?.confirmed || null };
  S.alerts.set(a.id, merged);
  S.day.set(a.id, { ...S.day.get(a.id), ...merged });
  renderReceipts();
  if (!a._initial) S.lastAlert = merged;
  else if (!S.lastAlert || merged.ts_ms > S.lastAlert.ts_ms) S.lastAlert = merged;
  renderFeed();
  if (TO.alert?.id === a.id) TO.update(merged);
  if (a._initial) return;
  const age = (S.source.now() - a.ts_ms) / 1000;
  if (!params.has('quiet') && !S.shownTakeover.has(a.id) && age < 30 && !a.confirmed) { S.shownTakeover.add(a.id); TO.open(merged); }
  renderLive();
}

// ------------------------------------------------------------ RECEIPTS (every alert today, graded)
// Old recordings (docs/data/replay.json) carry only the nearest ESPN play's text: look its type/team up in the
// recording's play list (the beneficiary team: the recovering team on a fumble, the defense on an interception).
function legacyGrade(a) {
  const c = a.confirmed, plays = S.source?.plays || [];
  const same = (x) => x.wallclock_ms === c.espn_wallclock_ms;
  const p = plays.find((x) => same(x) && x.text && c.play_text && x.text.slice(0, 30) === c.play_text.slice(0, 30)) || plays.find(same);
  if (!p || !p.type || p.type === 'OTHER' || p.team !== a.team) return 'no_match';
  if (callOf(a).prob == null) return 'swing_hit';          // unnamed "big swing": never WRONG
  return a.inferred?.[0]?.type === p.type ? 'correct' : 'wrong';
}
function gradeOf(a) {
  const unnamed = callOf(a).prob == null;                  // "Big swing to X": nothing named, so it can't be WRONG
  if ('grade' in a && a.grade !== undefined) {
    const g = a.grade || 'pending';
    return g === 'wrong' && unnamed ? 'swing_hit' : g === 'correct' && unnamed ? 'swing_hit' : g;
  }
  if (a.confirmed) {
    if (a.confirmed.play_type == null && a.confirmed.inferred_correct == null) return legacyGrade(a);
    if (unnamed) return 'swing_hit';
    return a.confirmed.inferred_correct ? 'correct' : 'wrong';
  }
  if ('espn_nearest' in a) return 'no_match';
  return 'pending';
}
const GRADE = { correct: ['RIGHT', 'g-ok'], wrong: ['WRONG', 'g-bad'], no_match: ['NO MATCHING PLAY', 'g-miss'], swing_hit: ['REAL PLAY, NOT NAMED', 'g-swing'], pending: ['GRADING', 'g-pend'] };
const dayStart = () => { const d = new Date(S.source?.now?.() ?? Date.now()); d.setHours(0, 0, 0, 0); return d.getTime(); };
function dayAlerts() {
  const all = [...S.day.values()];
  if (S.source?.kind !== 'live') return all; // a replay: show the whole recording
  const t0 = dayStart();
  const real = all.filter((a) => a.ts_ms >= t0 && !String(a.id).startsWith('r_'));
  return real.length || S.source.serverMode !== 'replay' ? real : all.filter((a) => a.ts_ms >= t0);
}
function renderReceipts() {
  const body = $('#rc-body'); if (!body) return;
  const list = dayAlerts().sort((a, b) => b.ts_ms - a.ts_ms);
  // FUNNEL, counted from the same rows the table shows: real play -> swing play -> no matching play -> grading
  const t = { n: list.length, correct: 0, wrong: 0, no_match: 0, swing_hit: 0, pending: 0, real: 0, realNamed: 0, realSwing: 0, swing: 0, swingNamed: 0 };
  list.forEach((a) => {
    const g = gradeOf(a); t[g] = (t[g] || 0) + 1;
    if (g === 'correct' || g === 'wrong' || g === 'swing_hit') {
      const named = g !== 'swing_hit';
      if (isSwing(a.confirmed)) { t.swing++; if (named) t.swingNamed++; } else { t.real++; if (named) t.realNamed++; else t.realSwing++; }
    }
  });
  const realWrong = t.realNamed - t.correct;
  const namedTxt = t.realNamed ? `${t.realNamed} named${realWrong ? `: ${t.correct} right, ${realWrong} wrong` : t.realNamed > 1 ? ', all right' : ', right'}` : '';
  const realBits = [namedTxt, t.realSwing ? `${t.realSwing} big swing${t.realSwing === 1 ? '' : 's'}` : ''].filter(Boolean).join(' · ');
  const parts = [`<b class="g-ok">${t.real} tied to a TD, FG, turnover or 20+ yd play</b>${realBits ? ` (${realBits})` : ''}`,
    `<b class="g-swing">${t.swing} on another play that swung ESPN's win odds 5+ pts</b> (stops, conversions, missed FGs, returns${t.swingNamed ? `; ${t.swingNamed} of them we'd named wrong` : ''})`,
    `<b class="g-miss">${t.no_match} no matching play</b>`];
  if (t.pending) parts.push(`${t.pending} grading`);
  $('#rc-tally').innerHTML = `${S.source?.kind === 'live' && !isReplay() ? 'Today' : 'This replay'}, ${t.n} alert${t.n === 1 ? '' : 's'}: ${parts.join(' · ')}`;
  const graded = t.n - (t.pending || 0), hits = t.correct + t.wrong;
  // Lead with what a user acts on: when we NAME a play, how often is it right? Then how each alert was graded.
  $('#rc-acc').innerHTML = graded > 0
    ? `${hits ? `When we named the play: <b>${t.correct} of ${hits} right (${pct(t.correct / hits)})</b>. ` : 'No named plays graded yet. '}`
      + `Every alert is checked against ESPN's play-by-play: first for a TD, field goal, turnover or 20+ yard play by that team, then for any play that moved ESPN's own win probability 5+ points toward that team. If neither, it counts as a miss.`
    : 'No graded alerts yet. Each one is graded within about 3 minutes of firing.';
  $('#rc-empty').hidden = list.length > 0;
  // no-match rows are collapsed by default (the count above is never hidden)
  let more = $('#rc-more');
  if (!more) {
    more = document.createElement('button');
    more.id = 'rc-more'; more.type = 'button'; more.className = 'mono';
    more.style.cssText = 'display:block;margin:12px 24px 18px;padding:8px 12px;background:none;color:var(--ink2);border:1px dashed var(--line);font-size:.8rem;letter-spacing:.06em;cursor:pointer';
    more.addEventListener('click', () => { S.rcAll = !S.rcAll; renderReceipts(); });
    body.closest('table')?.after(more);
  }
  more.hidden = !t.no_match;
  more.textContent = S.rcAll ? `Hide the ${t.no_match} with no matching play` : `Show all (${t.no_match} more with no matching play)`;
  const rows = S.rcAll ? list : list.filter((a) => gradeOf(a) !== 'no_match');
  body.innerHTML = rows.map((a) => {
    const g = gradeOf(a);
    let [gl, gc] = GRADE[g] || GRADE.pending;
    if (g === 'swing_hit' && isSwing(a.confirmed)) gl = 'REAL SWING PLAY';
    const call = callOf(a);
    const matched = g === 'correct' || g === 'wrong' || g === 'swing_hit';
    const lead = beforeStream(a), espn = +a.confirmed?.lead_s;
    const hs = matched
      ? `${lead >= 1 ? `<b class="sig">${lead.toFixed(0)} s</b> before ${esc(S.delayK)}` : `none on ${esc(S.delayK)}`}${espn > 0 ? `<em>${espn.toFixed(0)} s before ESPN's public feed</em>` : ''}`
      : g === 'pending' ? `<span class="rc-dim">grading</span>` : `<span class="rc-dim">no play to beat</span>`;
    const detail = isSwing(a.confirmed) ? `${swingLabel(a.confirmed)}${a.confirmed.play_text ? ` · ESPN: ${a.confirmed.play_text}` : ''}`
      : a.confirmed?.play_text ? `ESPN: ${a.confirmed.play_text}` : g === 'no_match' && a.espn_nearest?.play_text ? `Nearest ESPN play: ${a.espn_nearest.play_text}` : '';
    const game = S.games.find((x) => x.game_id === a.game_id);
    return `<tr class="rc-row ${gc} ${S.unveiled.has(a.id) ? 'unveil' : ''}" data-id="${esc(a.id)}">
      <td class="mono rc-time">${clock(a.ts_ms, { sec: false })}</td>
      <td class="rc-game mono">${esc(game?.short_name || a.short_name || '')}</td>
      <td class="rc-call"><span class="shroud"><b>${esc(call.team)}</b> ${esc(call.play)}${detail ? `<small>${esc(detail.length > 170 ? `${detail.slice(0, 168)}…` : detail)}</small>` : ''}</span><span class="shroud-tap mono">Spoiler Shield · tap to reveal</span></td>
      <td class="num mono rc-sure">${call.prob != null ? pct(call.prob) : '–'}</td>
      <td class="rc-g"><span class="rc-grade mono">${gl}</span></td>
      <td class="rc-lead mono">${hs}</td></tr>`;
  }).join('');
}
async function pollDay() {
  if (!S.api || S.source?.kind !== 'live') return;
  try {
    const [al, hl] = await Promise.all([
      fetchJSON(`${S.api}/api/alerts?since_ms=${dayStart()}`, { timeout: 8000 }).catch(() => null),
      fetchJSON(`${S.api}/api/health`, { timeout: 6000 }).catch(() => null)]);
    (al || []).forEach((a) => S.day.set(a.id, { ...S.day.get(a.id), ...a }));
    if (hl?.tally) S.tally = hl.tally;
    renderReceipts();
  } catch {}
}
// Spoiler Shield: tap a blurred card or row to reveal just that one
function unveilOn(sel) {
  $(sel)?.addEventListener('click', (e) => {
    const row = e.target.closest('[data-id]');
    if (!row || !shieldOn() || row.classList.contains('unveil')) return;
    S.unveiled.add(row.dataset.id); row.classList.add('unveil');
  });
}
unveilOn('#feed'); unveilOn('#rc-body');

// ------------------------------------------------------------ SPOILER takeover
function fitText(el) {
  el.style.fontSize = '';
  const box = el.parentElement.clientWidth;
  let fs = parseFloat(getComputedStyle(el).fontSize), guard = 0;
  while (el.scrollWidth > box && fs > 24 && guard++ < 40) { fs *= 0.94; el.style.fontSize = `${fs}px`; }
}
const TO = {
  alert: null, timer: null, votes: null, mine: null, t0: 0, revealT: null,
  open(a, { demo = false } = {}) {
    clearInterval(this.timer); clearTimeout(this.revealT); clearTimeout(this.closeT);
    this.alert = a; this.mine = null; this.demo = demo;
    this.t0 = demo ? S.source.now() : a.ts_ms;
    this.votes = { TD: 0, FG: 0, TURNOVER: 0, BIG_PLAY: 0, n: 0 };
    const el = $('#takeover');
    el.classList.remove('revealed', 'done', 'shown'); el.hidden = false;
    el.classList.remove('unveil');
    el.dataset.tier = tierOf(a, tierAlert).tier;
    const g = S.games.find((x) => x.game_id === a.game_id);
    $('#to-game').textContent = g?.short_name || a.game_id || '';
    $('#to-when').textContent = `${isReplay() ? 'REPLAY · ' : ''}MARKET MOVED ${clock(this.t0, { tenth: true })}`;
    const top = a.inferred?.[0] || { type: 'OTHER', prob: 0 };
    $('#to-team').textContent = nick(a.team) || a.team || '';
    $('#to-play').dataset.pre = `UP ${Math.round(Math.abs(teamProbs(a).after - teamProbs(a).before) * 100)}¢`;
    $('#to-play').dataset.post = callOf(a).play;
    $('#to-play').textContent = $('#to-play').dataset.pre;
    this.setCall(a);
    $('#to-lower').innerHTML = `<span class="to-lower-tag">KALSHI KNOWS</span><span>The price moved at ${clock(this.t0, { tenth: true })}. You're on <b>${esc(S.delayK)}</b>, about ${S.delay}s behind real life.${isReplay() ? ' <em>REPLAY of a real alert from earlier today</em>' : ''}</span>`;
    this.renderVotes();
    requestAnimationFrame(() => { el.classList.add('shown'); fitText($('#to-play')); fitText($('#to-team')); });
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
    fitText($('#to-play')); fitText($('#to-team'));
  },
  // confidence + alternatives; stage 1 ("big swing", nothing named yet) -> stage 2 (the call) updates in place
  setCall(a) {
    const call = callOf(a), tp = teamProbs(a);
    const sure = a.stage === 'provisional' ? 'NAMING THE PLAY…' : call.prob != null ? `${pct(call.prob)} SURE` : 'TOO CLOSE TO NAME';
    $('#to-sure').innerHTML = `<b>${sure}</b> · ${esc(a.team)} ${pct(tp.before)} → ${pct(tp.after)}`;
    const alts = call.prob != null ? (a.inferred || []).slice(1, 3).map((x) => `${(PLAY[x.type] || x.type).toLowerCase()} ${pct(x.prob)}`).join(' · ') : '';
    $('#to-alt').textContent = alts ? `or: ${alts}` : '';
  },
  update(a) {
    this.alert = a;
    const el = $('#takeover'), call = callOf(a);
    if (!el.hidden && call.play !== $('#to-play').dataset.post) {   // the named call landed while the takeover is up
      $('#to-play').dataset.post = call.play;
      if (el.classList.contains('revealed')) { $('#to-play').textContent = call.play; fitText($('#to-play')); }
      this.setCall(a);
    }
    if (a.confirmed && el.classList.contains('done')) $('#to-alt').textContent = confText(a.confirmed);
  },
  tick() {
    const el = $('#takeover'); if (el.hidden) return;
    const elapsed = (S.source.now() - this.t0) / 1000;
    const total = Math.max(1, beforeStream(this.alert));
    const rem = total - elapsed;
    $('#to-count').textContent = rem > 0 ? Math.ceil(rem) : '0';
    $('#to-bar').style.transform = `scaleX(${clamp(rem / total, 0, 1)})`;
    if (rem <= 0 && !el.classList.contains('done')) {
      el.classList.add('done'); this.reveal();
      $('#to-count-label').textContent = 'ON YOUR STREAM';
      $('#to-pre').textContent = 'YOUR STREAM JUST CAUGHT UP';
      if (this.alert.confirmed?.play_text) $('#to-alt').textContent = confText(this.alert.confirmed);
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
$('#to-reveal').addEventListener('click', () => { $('#takeover').classList.add('unveil'); TO.reveal(); });
$('.to-main').addEventListener('click', () => $('#takeover').classList.add('unveil'));

// ------------------------------------------------------------ SOMEONE KNEW
function renderKnew(data, mock) {
  if (!data) return;
  S.knew = data;
  const st = data.stats || {};
  const nCases = st.n ?? (data.cases || []).length;
  const nFirst = st.share_market_first != null ? Math.round(st.share_market_first * nCases) : (data.cases || []).filter((c) => (c.lead_minutes || 0) >= 15).length;
  $('#knew-meta').innerHTML = `${int(data.markets_scanned)} SETTLED MARKETS WITH BIG MOVES${mock ? ' · <span class="sample">SAMPLE DATA</span>' : ''}`;
  $('#knew-stats').innerHTML = `
    <div class="ks ks-wide"><div class="ks-big">${nFirst} of ${nCases}</div><p>cases we checked by hand moved at least 15 minutes before the earliest primary source (official post or press release). Picked from ${int(data.markets_scanned)} markets with big moves.</p></div>
    <div class="ks"><div class="ks-big">${dur(st.median_lead_minutes)}</div><p>median head start the price had on that source, across all ${nCases} cases</p></div>`;
  const cases = caseOrder(data.cases);
  $('#cases').innerHTML = cases.map((c, i) => {
    const t = tierOf(c, tierKnew);
    return `<article class="case ${i === 0 ? 'case-lead' : ''} case-t${t.tier}">
      <header class="case-head mono"><span>CASE ${String(i + 1).padStart(3, '0')}</span><span>${esc(c.category || '')}</span><span>RESOLVED ${esc((c.result || '').toUpperCase())}</span></header>
      <h3 class="case-title">${esc(c.title)}</h3>
      <div class="case-body">
        <div class="case-chart" data-case="${i}"></div>
        <div class="case-side">
          <div class="case-lead-n ${c.lead_minutes < 0 ? 'case-late' : ''}"><span>${esc(dur(c.lead_minutes).split(' ')[0])}</span><em>${esc(dur(c.lead_minutes).split(' ')[1] || '')}<br>${c.lead_minutes < 0 ? 'behind the news' : 'head start'}</em></div>
          ${tierBadge(t, { blurb: true })}
        </div>
      </div>
      <blockquote class="case-news"><p>&ldquo;${esc(c.first_news_title)}&rdquo;</p>
        <cite class="mono">${c.first_news_url ? `<a href="${esc(c.first_news_url)}" target="_blank" rel="noopener">${esc(c.first_news_source || 'source')}</a>` : esc(c.first_news_source || '')} · earliest source ${clock(c.first_news_ms, { sec: false })}, ${dateShort(c.first_news_ms)}</cite></blockquote>
      <p class="case-verdict">${esc(c.verdict || '')}</p>
    </article>`;
  }).join('');
  drawCases();
}
// Princeton leads (no public leak found), then GPT-6 (public clues existed), then the rest by head start
function caseOrder(list) {
  const pri = (c) => (c.feature_rank ?? (/princeton/i.test(c.title || '') ? 0 : /gpt-6/i.test(c.title || '') ? 1 : 2));
  return (list || []).slice().sort((a, b) => pri(a) - pri(b) || (b.lead_minutes || 0) - (a.lead_minutes || 0));
}
function drawCases() {
  if (!S.knew || route !== 'headlines') return;
  const cases = caseOrder(S.knew.cases);
  $$('.case-chart').forEach((el) => caseChart(el, cases[+el.dataset.case]));
}

// ------------------------------------------------------------ DUTCH BOOK
let dbSel = null;
// "Exhaustive" sets whose list of outcomes isn't actually complete: an unlisted outcome can win and every ticket loses
const isTrap = (o) => /:fake_exh$/.test(o.id || '') || /not exhaustive|isn.t exhaustive|not complete/i.test(o.explanation || '');
const realArb = (o) => !isTrap(o) && (o.profit_before_fees || 0) > 0;
const afterFees = (o) => !isTrap(o) && (o.profit_after_fees || 0) >= 0.01;
function renderDutch(data, { mock = false, live = false } = {}) {
  if (!data) return;
  S.db = data;
  $('#dutch-meta').innerHTML = `${live ? 'LIVE FROM THE ENGINE' : 'SNAPSHOT'} · UPDATED ${esc(ago(data.updated_ms))}${mock ? ' · <span class="sample">SAMPLE DATA</span>' : ''}`;
  const all = [...(data.opportunities || []), ...(data.near_misses || [])];
  const nBefore = all.filter(realArb).length, nAfter = all.filter(afterFees).length, nTrap = all.filter(isTrap).length;
  $('#db-claim').textContent = `We scanned ${int(data.scanned_markets)} markets: ${nBefore} arbitrage${nBefore === 1 ? '' : 's'} before fees, ${nAfter} after. ${nAfter ? 'Most get eaten by fees.' : "Fees are Kalshi's moat."}`;
  const opps = (data.opportunities || []).filter((o) => !isTrap(o)).sort((a, b) => (b.profit_after_fees || 0) - (a.profit_after_fees || 0)).slice(0, 30);
  const nearAll = (data.near_misses || []).slice().sort((a, b) => (b.profit_before_fees || 0) - (a.profit_before_fees || 0));
  const showNear = !opps.length && nearAll.length > 0;
  const rows = showNear ? nearAll.slice(0, 30).map((o) => ({ ...o, _near: true, _trap: isTrap(o) })) : opps;
  const total = opps.reduce((s, o) => s + Math.max(0, o.profit_after_fees || 0), 0);
  const amt = $('#db-amount');
  const fmt = (v) => `$${int(v)}`;
  if (opps.length) {
    amt.style.cssText = ''; delete amt.dataset.funnel; amt.parentElement.style.gridTemplateColumns = '';
    $('.db-label').innerHTML = 'of free money on Kalshi after fees <span class="sig">right now</span>'; $('.db-label').style.maxWidth = '';
    if (amt.dataset.seen) countUp(amt, total, fmt, 900);
    else onVisible(amt, () => { amt.dataset.seen = 1; countUp(amt, total, fmt, 2200); }, { threshold: 0.4 });
  } else {
    // Zero after fees is the finding, not a broken counter: show the funnel instead of "$0"
    const nLooked = all.filter((o) => (o.profit_before_fees || 0) > 0).length;
    amt.dataset.funnel = 1; amt.dataset.seen = 1;
    amt.parentElement.style.gridTemplateColumns = '1fr';     // one column: funnel line, then the headline
    amt.style.cssText = 'grid-row:auto;font-size:clamp(1.6rem,4vw,3.6rem);line-height:1.1;letter-spacing:0;color:var(--ink)';
    amt.innerHTML = `${int(data.scanned_markets)} markets scanned <span class="sig">→</span> ${int(nLooked)} looked free <span class="sig">→</span> 0 survive Kalshi's fees`;
    $('.db-label').innerHTML = `Fees are Kalshi's moat. <span class="sig">Every "free money" set below is a trap or gets eaten by the fee.</span>`;
    $('.db-label').style.maxWidth = '40ch';
  }
  $('#db-sub').textContent = `${int(data.scanned_events)} events · ${int(data.scanned_markets)} markets · ${nBefore} arbitrages before fees · ${nAfter} after · ${nTrap} traps where the list isn't complete`;
  S.dbOpps = rows; S.dbNear = showNear;
  $('.db-list-head').innerHTML = showNear ? `<span>LOOKS FREE · ISN&rsquo;T ${tierBadge(tierOf({ tier: 1 }, () => 1))}</span><span>WORST CASE</span>` : '<span>OPPORTUNITY</span><span>PROFIT AFTER FEES</span>';
  $('#db-list').innerHTML = rows.map((o, i) => {
    const label = o._near ? (o._trap ? 'TRAP: list not complete' : 'EATEN BY FEES') : esc((o.kind || '').replace('_', ' '));
    const right = !o._near ? `<span class="db-profit mono">${usd(o.profit_after_fees, { compact: true, sign: true })}</span>`
      : o._trap ? `<span class="db-profit mono db-loss">${usd(-(o.cost || 0), { compact: true })}<em>paper ${usd(o.profit_before_fees, { compact: true, sign: true })}</em></span>`
      : `<span class="db-profit mono db-loss">${usd(o.profit_after_fees, { compact: true, sign: true })}<em>before fees ${usd(o.profit_before_fees, { compact: true, sign: true })}</em></span>`;
    return `<li><button class="db-item ${i === (dbSel ?? 0) ? 'on' : ''} ${o._near ? 'db-trap' : ''}" data-i="${i}">
      <span class="db-kind mono ${o._near ? 'db-kind-bad' : ''}">${label}</span>
      <span class="db-title">${esc(o.title)}</span>
      <span class="db-cat mono">${esc(o.category || '')} · ${(o.legs || []).length} legs</span>
      ${o._near ? '' : tierBadge(tierOf(o, tierDutch))}
      ${right}</button></li>`;
  }).join('') || `<li class="db-none">Nothing open right now. Kalshi is behaving.</li>`;
  $$('.db-item').forEach((b) => b.addEventListener('click', () => { dbSel = +b.dataset.i; $$('.db-item').forEach((x) => x.classList.toggle('on', x === b)); renderDbDetail(rows[dbSel]); if (innerWidth < 900) $('#db-detail').scrollIntoView({ behavior: 'smooth', block: 'start' }); }));
  if (dbSel != null && dbSel >= rows.length) dbSel = 0;
  renderDbDetail(rows[dbSel ?? 0]);
  const nm = showNear ? [] : nearAll.filter((o) => !isTrap(o)).slice(0, 4);
  const cats = Object.entries(data.by_category || {}).sort((a, b) => b[1].violations - a[1].violations).slice(0, 6);
  const maxV = Math.max(1, ...cats.map(([, v]) => v.violations));
  $('#db-near').innerHTML = `
    ${nm.length ? `<p class="db-near-k mono">EATEN BY FEES · PROFITABLE UNTIL THE FEE</p><ul class="db-nm">${nm.map((o) => `<li><b>${esc(o.title)}</b><span class="mono">${usd(o.profit_before_fees, { compact: true, sign: true })} → <em>${usd(o.profit_after_fees, { compact: true, sign: true })}</em> after fees</span></li>`).join('')}</ul>` : ''}
    ${cats.length ? `<p class="db-near-k mono">WHERE THE CONTRADICTIONS LIVE</p><ul class="db-cats">${cats.map(([k, v]) => `<li><span>${esc(k)}</span><i style="--w:${(100 * v.violations / maxV).toFixed(1)}%"></i><b class="mono">${int(v.violations)}<em> / ${int(v.events)}</em></b></li>`).join('')}</ul>` : ''}`;
}
function renderDbDetail(o) {
  const el = $('#db-detail');
  if (!o) { el.innerHTML = ''; return; }
  const near = !!o._near, trap = near && isTrap(o);
  const legs = o.legs || [];
  const shown = legs.slice(0, 10);
  const pa = o.profit_after_fees || 0;
  const kicker = trap ? '<span class="sig">TRAP: LIST NOT COMPLETE</span>' : near ? '<span class="sig">EATEN BY FEES</span>' : 'PAPER TRADE';
  const plain = trap
    ? `<p class="dd-plain">Spend <b>${usd(o.cost)}</b> on every listed outcome. If something <b>not on the list</b> wins, every ticket loses. <b class="sig">Worst-case payout $0.00. Worst-case loss ${usd(-(o.cost || 0))}.</b> <span class="dd-paper">The ${usd(o.profit_before_fees, { sign: true })} profit is on paper only: it holds only if the list were complete.</span></p>`
    : near
      ? `<p class="dd-plain">Spend <b>${usd(o.cost, { compact: true })}</b>, collect at least <b>${usd(o.worst_case_payout, { compact: true })}</b> whatever happens: <b>${usd(o.profit_before_fees, { sign: true })}</b> before fees. Kalshi's fee is <b>${usd(o.fees)}</b>, so you end at <b class="sig">${usd(pa, { sign: true })}</b>. ${esc(o.explanation || '')}</p>`
      : `<p class="dd-plain">Spend <b>${usd(o.cost, { compact: true })}</b>. Whatever happens, get back at least <b>${usd(o.worst_case_payout, { compact: true })}</b>. That's <b class="sig">${usd(o.profit_before_fees, { compact: true })}</b> before fees and <b class="${pa > 0 ? 'sig' : 'cold'}">${usd(pa, { compact: true })}</b> after Kalshi's fee${pa > 0 ? '.' : ': the fee eats it.'}</p>`;
  const ledger = trap
    ? `<div><dt>Cost</dt><dd>${usd(o.cost)}</dd></div>
      <div class="ledger-bad"><dt>Worst-case payout</dt><dd>$0.00</dd></div>
      <div class="ledger-total ledger-bad"><dt>Worst-case loss</dt><dd class="sig">${usd(-(o.cost || 0))}</dd></div>
      <div class="ledger-paper"><dt>Paper profit <em>only if the list were complete</em></dt><dd>${usd(o.profit_before_fees, { sign: true })}</dd></div>`
    : `<div><dt>Cost</dt><dd>${usd(o.cost)}</dd></div>
      <div><dt>Worst-case payout</dt><dd>${usd(o.worst_case_payout)}</dd></div>
      <div><dt>Profit before fees</dt><dd>${usd(o.profit_before_fees, { sign: true })}</dd></div>
      <div><dt>Kalshi fees</dt><dd>−${usd(o.fees)}</dd></div>
      <div class="ledger-total"><dt>Profit after fees</dt><dd class="${pa > 0 ? 'sig' : ''}">${usd(pa, { sign: true })}</dd></div>`;
  el.innerHTML = `
    <p class="dd-k mono">${kicker} · ${esc((o.kind || '').replace('_', ' ').toUpperCase())} · ${esc((o.category || '').toUpperCase())}</p>
    <h3 class="dd-title">${esc(o.title)}</h3>
    ${near ? '' : `<div class="dd-tier">${tierBadge(tierOf(o, tierDutch), { blurb: true, size: 'tier-lg' })}</div>`}
    ${plain}
    ${trap ? `<p class="dd-expl">${esc(o.explanation || '')}</p>` : ''}
    <table class="legs"><thead><tr><th>Buy</th><th>Contract</th><th class="num">Price</th><th class="num">Qty</th><th class="num">Cost</th></tr></thead>
      <tbody>${shown.map((l) => `<tr><td><span class="side side-${esc(l.side)} mono">${esc((l.side || '').toUpperCase())}</span></td><td>${esc(l.label)}</td><td class="num mono">${cents(l.price)}</td><td class="num mono">${int(l.qty)}</td><td class="num mono">${usd((l.price || 0) * (l.qty || 1), { compact: true })}</td></tr>`).join('')}
      ${legs.length > shown.length ? `<tr class="legs-more"><td colspan="5" class="mono">+ ${legs.length - shown.length} more legs</td></tr>` : ''}</tbody></table>
    <div class="dd-chart" id="dd-chart"></div>
    <dl class="ledger mono">${ledger}</dl>
    ${near ? '' : `<p class="dd-expl">${esc(o.explanation || '')}</p>`}`;
  if (!near && route === 'dutch') payoffChart($('#dd-chart'), o);
}

// ------------------------------------------------------------ PREDATOR SCALE
function renderScale() {
  const el = $('#scale-list');
  el.innerHTML = [6, 5, 4, 3, 2, 1].map((i) => `<li class="sc sc-${i}">
    <span class="sc-n">${i}</span>
    <span class="sc-em">${emblem(i)}</span>
    <div class="sc-txt"><h3 class="sc-name">${esc(TIERS[i].name)}</h3><p class="sc-blurb">${esc(TIERS[i].blurb)}</p></div>
    <dl class="sc-crit mono">${['Spoiler', 'Dutch Book', 'Beat the headlines'].map((k, j) => `<div><dt>${k}</dt><dd>${esc(TIER_CRIT[i][j])}</dd></div>`).join('')}</dl>
  </li>`).join('');
  $$('.sc', el).forEach((li) => li.addEventListener('pointerenter', () => playFx($('.em', li))));
  onVisible(el, () => {
    el.classList.add('in');
    $$('.sc .em', el).forEach((svg, k) => setTimeout(() => playFx(svg), 500 + k * 160));
  }, { threshold: 0.25 });
}
renderScale();

// ------------------------------------------------------------ ticker
let tickerSig = '';
function renderTicker() {
  const items = [];
  const rank = { in: 0, pre: 1, post: 2 };
  S.games.slice().sort((a, b) => (rank[a.status] ?? 1) - (rank[b.status] ?? 1)).forEach((g) => {
    const name = `<b>${esc(g.short_name || `${g.away} @ ${g.home}`)}</b>`;
    if (g.p_home == null) { items.push(`<span class="tk">${name} <em class="mono">${g.status === 'post' ? 'FINAL' : 'KICKOFF SOON'}</em></span>`); return; }
    items.push(`<span class="tk">${name} ${esc(g.home)} <em class="mono">${cents(g.p_home)}</em> · ${esc(g.away)} <em class="mono">${cents(1 - g.p_home)}</em></span>`);
  });
  const last = S.lastAlert;
  if (last && !shieldOn()) items.push(`<span class="tk tk-sig"><b>LAST ALERT</b> ${esc(last.headline || '')}</span>`);
  if (S.db) {
    items.push(S.dbNear ? `<span class="tk"><b>DUTCH BOOK</b> ${int(S.db.scanned_markets)} markets scanned · 0 arbitrages left after fees</span>` : `<span class="tk"><b>DUTCH BOOK</b> <em class="mono">$${int(S.db.total_mispricing_usd)}</em> of contradictory pricing open</span>`);
    (S.dbOpps || []).slice(0, 3).forEach((o) => items.push(o._near ? `<span class="tk">${esc(o.title)} <em class="mono">looks free, isn't</em></span>` : `<span class="tk">${esc(o.title)} <em class="mono">${usd(o.profit_after_fees, { compact: true, sign: true })}</em></span>`));
  }
  caseOrder(S.knew?.cases).slice(0, 2).forEach((c) => items.push(`<span class="tk"><b>BEAT THE HEADLINES</b> ${esc(c.title)} <em class="mono">${esc(dur(c.lead_minutes))} ${c.lead_minutes < 0 ? 'after the news' : 'early'}</em></span>`));
  const sig = items.join('');
  if (sig === tickerSig || !items.length) return;
  tickerSig = sig;
  const track = $('#ticker-track');
  track.innerHTML = `<div class="tk-run">${sig}</div><div class="tk-run" aria-hidden="true">${sig}</div>`;
  const w = track.firstElementChild.scrollWidth;
  track.style.setProperty('--dur', `${Math.max(30, w / 70)}s`);
}

// ------------------------------------------------------------ pages (hash routes: GitHub Pages has no rewrites)
const ROUTES = ['live', 'headlines', 'dutch', 'proof', 'scale', 'auto', 'alerts'];
const LEGACY = { top: 'live', live: 'live', receipts: 'live', knew: 'headlines', dutch: 'dutch', proof: 'proof', scale: 'scale', get: 'alerts' };
const TITLES = { live: 'Live', headlines: 'The market beat the headlines', dutch: 'Dutch Book', proof: 'Proof', scale: 'Predator Scale', auto: 'Auto', alerts: 'Get alerts' };
// Auto page: js/auto.js is loaded and mounted only while #/auto is open (it polls the engine every 3 s)
let autoUnmount = null, autoApi = null;
async function syncAuto(page) {
  if (page !== 'auto' || (autoUnmount && autoApi !== S.api)) { try { autoUnmount?.(); } catch {} autoUnmount = null; }
  if (page !== 'auto' || autoUnmount) return;
  const root = $('#auto-root');
  if (!S.api) { root.innerHTML = '<p class="auto-empty">The live engine is offline right now, so there is nothing to automate. This page connects by itself when it is back.</p>'; return; }
  try {
    const { mountAuto } = await import('./auto.js');
    if (route !== 'auto' || autoUnmount) return;
    autoApi = S.api; autoUnmount = mountAuto(root, S.api);
  } catch (e) { root.innerHTML = `<p class="auto-empty">Couldn't load the Auto page: ${esc(e.message || String(e))}</p>`; }
}
let route = null;
function parseRoute() {
  const raw = location.hash, k = decodeURIComponent(raw.replace(/^#\/?/, '')).toLowerCase();
  if (raw.startsWith('#/') && ROUTES.includes(k)) return { page: k };
  if (LEGACY[k]) return { page: LEGACY[k], anchor: k };
  return { page: 'live' };
}
let stageStarted = false;
function startStage() { if (stageStarted || !S.results) return; stageStarted = true; initStage(); }
function redraw(page = route) {
  if (page === 'live') { startStage(); if (S.games.length && S.source) renderLive(); }
  else if (page === 'headlines') drawCases();
  else if (page === 'proof') { if (S.results && $('#lag-chart').innerHTML) lagChart($('#lag-chart'), S.results); }
  else if (page === 'dutch') { if (S.dbOpps?.length) renderDbDetail(S.dbOpps[dbSel ?? 0]); }
}
function go() {
  const { page, anchor } = parseRoute();
  if (location.hash !== `#/${page}`) history.replaceState(null, '', `${location.pathname}${location.search}#/${page}`);
  const changed = page !== route;
  route = page;
  document.documentElement.dataset.route = page;
  $$('[data-page]').forEach((el) => { el.hidden = el.dataset.page !== page; });
  $$('a[data-route]').forEach((a) => { if (a.dataset.route === page) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current'); });
  document.title = `${TITLES[page]} · Kalshi Knows`;
  const el = anchor && anchor !== 'top' && anchor !== page ? $(`#${anchor}`) : anchor === 'live' ? $('#live') : null;
  if (el && !el.hidden) {
    const jump = () => el.scrollIntoView({ behavior: changed ? 'instant' : 'smooth', block: 'start' });
    requestAnimationFrame(jump);
    if (changed) setTimeout(jump, 900); // first load: the 3D story and feed change height while booting
  }
  else if (changed) scrollTo(0, 0);
  if (changed) { requestAnimationFrame(() => redraw(page)); syncAuto(page); }
}
addEventListener('hashchange', go);
go();

// ------------------------------------------------------------ boot
async function boot() {
  registerSW();
  const resP = loadData('results'), knewP = loadData('someone_knew'), dbP = loadData('dutchbook', 45000);

  // results first: they set the story numbers
  const { data: res, mock: resMock } = await resP;
  S.results = res || {};
  const sd = S.results.stream_delay_reference_s || { broadcast: 19, best_stream: 48, worst_stream: 62 };
  S.lag = S.results.market_lag?.median_s ?? 2.6;
  // Stats Perform, Super Bowl LX latency report (published reference values, not our measurement)
  S.delays = [{ k: 'Antenna', v: 19 }, { k: 'Cable', v: 38 }, { k: 'Peacock', v: 48 }, { k: 'YouTube TV', v: 53 }, { k: 'Hulu Live', v: 53 }, { k: 'DirecTV', v: 60 }, { k: 'NFL+', v: 62 }];
  const dk = S.delays.find((d) => d.k === S.delayK) || S.delays[2];
  S.delayK = dk.k; S.delay = dk.v;
  bind(); renderDelaySeg();
  if (route === 'live') startStage();
  onVisible($('#proof'), () => renderProof(S.results, resMock), { threshold: 0.05 });

  // live or replay
  const onGames = (e) => { S.games = e.detail || []; S.games.forEach((g) => Object.assign(EXTRA_TEAMS, g.team_names || {})); renderLive(); renderTicker(); };
  const onAlertEv = (e) => onAlert(e.detail);
  const startLive = (live) => {
    S.api = live.api;
    S.source = new LiveSource(live.api, live.health);
    const serverReplay = live.health.mode === 'replay';
    const okMode = () => setMode(serverReplay ? 'replay' : 'live', serverReplay ? 'REPLAY' : 'LIVE', serverReplay ? 'live server' : '');
    okMode();
    $('#live-meta').textContent = `KALSHI PUBLIC ORDER BOOK · ${int(live.health.games_tracked)} GAMES TRACKED · UPDATES EVERY ~2 S`;
    $('#skip-btn').hidden = true;
    S.source.addEventListener('status', (e) => { if (e.detail.ok || Date.now() - S.source.lastGamesAt < 12000) okMode(); else setMode('warn', 'RECONNECTING'); });
    S.source.addEventListener('games', okMode);
    syncAuto(route);
    if (!serverReplay) mountVenuesPanel(live.api);
  };
  const live = await resolveApi();
  if (live) startLive(live);
  else {
    const { data: rep, mock } = await loadData('replay');
    if (rep?.history?.length) {
      S.source = new ReplaySource(rep);
      setMode('replay', 'REPLAY', `recorded ${dateShort(S.source.recorded)}`);
      $('#live-meta').innerHTML = `REPLAY OF ${esc(rep.game?.short_name || '')}, RECORDED ${esc(dateShort(S.source.recorded).toUpperCase())} · REAL SPEED${mock ? ' · <span class="sample">SAMPLE DATA</span>' : ''}`;
      $('#skip-btn').hidden = false;
      $('#skip-btn').addEventListener('click', () => S.source.skip?.());
      S.source.addEventListener('reset', () => { S.alerts.clear(); S.day.clear(); S.shownTakeover.clear(); renderFeed(); renderReceipts(); });
    } else {
      setMode('off', 'OFF AIR');
      S.source = { kind: 'none', now: () => Date.now(), addEventListener() {}, start() {} };
    }
    // The live server may just have been slow to answer (quick tunnels hiccup). Keep checking, and switch over
    // in place when it answers, without reloading the page. Never switch in the middle of a spoiler.
    {
      const retry = setInterval(async () => {
        if (!$('#takeover').hidden) return;
        const back = await resolveApi();
        if (!back || !$('#takeover').hidden) return;
        clearInterval(retry);
        S.source.stop?.();
        S.alerts.clear(); S.day.clear(); S.shownTakeover.clear(); S.games = []; S.lastAlert = null;
        renderFeed();
        startLive(back);
        pollDay();
        S.source.addEventListener('games', onGames);
        S.source.addEventListener('alert', onAlertEv);
        S.source.start();
        S.push?.render();
        loadDb();
      }, 15000);
    }
  }
  S.source.addEventListener('games', onGames);
  S.source.addEventListener('alert', onAlertEv);
  S.source.start();
  setInterval(() => { if (S.games.length) renderLive(); }, 1000);
  pollDay(); setInterval(pollDay, 30000);

  $('#demo-btn').addEventListener('click', () => { if (S.lastAlert) TO.open(S.lastAlert, { demo: true }); });

  S.push = initPush(() => S.api);
  initShield();
  onShield(() => { renderFeed(); renderReceipts(); renderTicker(); });

  // other sections
  knewP.then(({ data, mock }) => { renderKnew(data, mock); renderTicker(); });
  // snapshot right away; the live scan replaces it when (if) the engine answers
  let dbLive = false;
  async function loadDb() {
    if (!S.api) return false;
    try { const d = await fetchJSON(`${S.api}/api/dutchbook`, { timeout: 15000 }); if (d?.opportunities) { dbLive = true; renderDutch(d, { live: true }); renderTicker(); return true; } } catch {}
    return false;
  }
  dbP.then(({ data, mock }) => { if (!dbLive) { renderDutch(data, { mock }); renderTicker(); } });
  loadDb();
  setInterval(loadDb, 60000);

  // QR codes
  const url = SITE_URL;
  $('#get-url').textContent = url.replace(/^https?:\/\//, '');
  qrSVG(url).then((svg) => { $('#get-qr').innerHTML = svg; if (PRESENT) { $('#pqr-code').innerHTML = svg; $('#pqr').hidden = false; } }).catch(() => {});

  // resize charts
  let rT;
  addEventListener('resize', () => { clearTimeout(rT); rT = setTimeout(() => redraw(route), 150); });
}

// presenter QR: shows over the hero and the install section only (it would cover the live feed). Q pins it on.
const pqrIn = new Map();
function pqrUpdate() {
  const pq = $('#pqr'); if (!pq) return;
  pq.classList.toggle('pqr-off', !pq.dataset.pin && ![...pqrIn.values()].some(Boolean));
}
if (PRESENT) {
  const io = new IntersectionObserver((es) => { es.forEach((e) => pqrIn.set(e.target, e.isIntersecting)); pqrUpdate(); }, { rootMargin: '-35% 0px -35% 0px' });
  ['#top', '#get', '.foot'].forEach((q) => { const el = $(q); if (el) io.observe(el); });
}

// keyboard: presenter controls
addEventListener('keydown', (e) => {
  if (e.target.matches('input, textarea')) return;
  const k = e.key.toLowerCase();
  if (k === 'escape') TO.close();
  else if (k === 't' && S.lastAlert) TO.open(S.lastAlert, { demo: true });
  else if (k === 'n' && S.source?.skip) S.source.skip();
  else if (k === 'r') TO.reveal();
  else if (k === 'q' && PRESENT) { const pq = $('#pqr'); pq.dataset.pin = pq.dataset.pin ? '' : '1'; pqrUpdate(); }
  else if ('1234567'.includes(k) && k) {
    if (k === '1' && route === 'live') $('#live').scrollIntoView({ behavior: 'smooth' });
    else location.hash = `#/${ROUTES[+k - 1]}`;
  }
});

boot().catch((e) => console.error(e));
