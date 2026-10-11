// Hand-rolled SVG charts. Direct labels, tabular mono numbers, no legends.
import { clamp, esc, clock, pct, dur, usd, PLAY_SHORT } from './util.js';

const NS = 'http://www.w3.org/2000/svg';
const f1 = (v) => (Math.round(v * 10) / 10).toString();

function size(el, minH = 160) {
  const r = el.getBoundingClientRect();
  return { w: Math.max(280, Math.round(r.width)), h: Math.max(minH, Math.round(r.height || minH)) };
}
function stepPath(pts) {
  if (!pts.length) return '';
  let d = `M${f1(pts[0][0])},${f1(pts[0][1])}`;
  for (let i = 1; i < pts.length; i++) d += `H${f1(pts[i][0])}V${f1(pts[i][1])}`;
  return d;
}
function linePath(pts) {
  return pts.map((p, i) => `${i ? 'L' : 'M'}${f1(p[0])},${f1(p[1])}`).join('');
}

// ---------------------------------------------------------------- LIVE
// game: games item; opts: {now, delay, alerts, home, away}
export function liveChart(el, game, { now, delay = 48, alerts = [] } = {}) {
  const { w, h } = size(el, 220);
  const big = w > 900;
  const present = document.documentElement.classList.contains('present');
  const padL = big ? 56 : 34, padR = big ? (present ? 200 : 150) : 84, padT = big ? 46 : 38, padB = big ? 34 : 28;
  const hist = (game.history || []).filter((d) => d && d[0] <= now + 5000);
  const t1 = now;
  const win = (document.documentElement.classList.contains('present') ? 8 : 12) * 60e3;
  const t0 = Math.max(t1 - win, Math.min(t1 - 3 * 60e3, hist[0]?.[0] ?? t1 - win));
  const X = (t) => padL + ((t - t0) / (t1 - t0)) * (w - padL - padR);
  const Y = (p) => padT + (1 - p) * (h - padT - padB);
  // clip to the window: keep the last point before t0, pinned to the left edge
  let firstIn = hist.findIndex((d) => d[0] >= t0);
  if (firstIn < 0) firstIn = hist.length;
  const vis = hist.slice(Math.max(0, firstIn - 1)).map(([t, p]) => [Math.max(t, t0), p]);
  const pts = vis.map(([t, p]) => [X(t), Y(p)]);
  const pNow = game.p_home ?? hist.at(-1)?.[1] ?? 0.5;
  if (pts.length) pts.push([X(t1), Y(pNow)]);
  const streamT = t1 - delay * 1000;
  const xs = clamp(X(streamT), padL, w - padR);

  let g = '';
  // gridlines
  for (const p of [0, 0.25, 0.5, 0.75, 1]) {
    g += `<line x1="${padL}" x2="${w - padR}" y1="${f1(Y(p))}" y2="${f1(Y(p))}" class="${p === 0.5 ? 'gl-mid' : 'gl'}"/>`;
    g += `<text x="${padL - 8}" y="${f1(Y(p) + 4)}" class="ax" text-anchor="end">${Math.round(p * 100)}</text>`;
  }
  // time axis: every 5 minutes
  const step = 5 * 60e3;
  for (let t = Math.ceil(t0 / step) * step; t < t1 - 60e3; t += step) {
    g += `<text x="${f1(X(t))}" y="${h - 8}" class="ax" text-anchor="middle">${clock(t, { sec: false }).replace(/ (AM|PM)/, '')}</text>`;
  }
  // the future, to you
  if (xs < w - padR - 2) {
    g += `<rect x="${f1(xs)}" y="${padT}" width="${f1(w - padR - xs)}" height="${h - padT - padB}" fill="url(#hatch)"/>`;
    g += `<line x1="${f1(xs)}" x2="${f1(xs)}" y1="${padT - 22}" y2="${h - padB}" class="stream-line"/>`;
    // the delay label goes over the hatched gap when it fits; otherwise it joins the stream label
    const ahead = `${delay}s AHEAD`, cw = present ? 9.4 : 7.6;
    if (w - padR - xs >= ahead.length * cw + 4) {
      g += `<text x="${f1(xs - 6)}" y="${padT - 26}" class="lbl-cold" text-anchor="end">${w < 640 ? 'YOUR STREAM' : 'YOUR STREAM IS HERE'}</text>`;
      g += `<text x="${f1((xs + w - padR) / 2)}" y="${padT - 26}" class="lbl-sig" text-anchor="middle">${ahead}</text>`;
    } else {
      g += `<text x="${f1(xs - 6)}" y="${padT - 26}" class="lbl-cold" text-anchor="end">${w < 640 ? 'YOUR STREAM' : 'YOUR STREAM IS HERE'} <tspan class="lbl-sig">· ${delay}s BEHIND</tspan></text>`;
    }
  }
  // area + line
  if (pts.length > 1) {
    const area = `${stepPath(pts)}V${f1(Y(0))}H${f1(pts[0][0])}Z`;
    g += `<path d="${area}" class="area"/>`;
    g += `<path d="${stepPath(pts)}" class="pline"/>`;
  }
  // alert markers
  for (const a of alerts) {
    if (a.game_id && game.game_id && a.game_id !== game.game_id) continue;
    if (a.ts_ms < t0 || a.ts_ms > t1) continue;
    const x = X(a.ts_ms);
    const top = a.inferred?.[0];
    const lab = `${PLAY_SHORT[top?.type] || 'JUMP'} ${a.team || ''}`;
    g += `<line x1="${f1(x)}" x2="${f1(x)}" y1="${padT - 4}" y2="${h - padB}" class="al-line"/>`;
    const cw = lab.length * (present ? 9.4 : 7.4) + 12, chH = present ? 21 : 17;
    const flip = x + cw > w - padR + 40;
    const cx = flip ? x - cw + 1 : x - 1;
    g += `<rect x="${f1(cx)}" y="${padT - 4}" width="${f1(cw)}" height="${chH}" class="al-chip"/>`;
    g += `<text x="${f1(cx + 6)}" y="${padT + (present ? 11 : 8)}" class="al-txt">${esc(lab)}</text>`;
  }
  // now dot + direct labels
  const yN = Y(pNow);
  g += `<circle cx="${f1(X(t1))}" cy="${f1(yN)}" r="9" class="now-halo"/><circle cx="${f1(X(t1))}" cy="${f1(yN)}" r="4" class="now-dot"/>`;
  const lx = w - padR + 14;
  g += `<text x="${lx}" y="${f1(clamp(yN, padT + 10, h - padB - 26) + 2)}" class="dl-big">${esc(game.home || 'HOME')} ${Math.round(pNow * 100)}%</text>`;
  g += `<text x="${lx}" y="${f1(clamp(yN, padT + 10, h - padB - 26) + (big ? 26 : 20))}" class="dl-small">${esc(game.away || 'AWAY')} ${Math.round((1 - pNow) * 100)}%</text>`;
  g += `<text x="${padL}" y="14" class="ax-title">${esc(game.home || 'HOME')} WIN PROBABILITY · KALSHI MID PRICE</text>`;

  el.innerHTML = `<svg viewBox="0 0 ${w} ${h}" width="${w}" height="${h}" role="img" aria-label="${esc(game.home)} win probability ${Math.round(pNow * 100)} percent">
    <defs><pattern id="hatch" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="8" height="8" fill="rgba(255,77,26,0.035)"/><line x1="0" y1="0" x2="0" y2="8" stroke="rgba(255,77,26,0.22)" stroke-width="1.2"/></pattern></defs>
    ${g}</svg>`;
}

export function sparkline(pts, w = 120, h = 32) {
  if (!pts?.length) return `<svg width="${w}" height="${h}"></svg>`;
  const t0 = pts[0][0], t1 = pts.at(-1)[0] || t0 + 1;
  const P = pts.map(([t, p]) => [((t - t0) / (t1 - t0 || 1)) * (w - 4) + 2, (1 - p) * (h - 4) + 2]);
  return `<svg class="spark" viewBox="0 0 ${w} ${h}" width="${w}" height="${h}" aria-hidden="true"><line x1="0" x2="${w}" y1="${h / 2}" y2="${h / 2}" class="gl-mid"/><path d="${stepPath(P)}" class="pline"/></svg>`;
}

// ---------------------------------------------------------------- SOMEONE KNEW
export function caseChart(el, c) {
  const { w, h } = size(el, 180);
  const padL = 10, padR = 44, padT = 34, padB = 26;
  const s = (c.series || []).slice().sort((a, b) => a[0] - b[0]);
  if (!s.length) { el.innerHTML = ''; return; }
  const t0 = Math.min(s[0][0], c.move_start_ms), t1 = Math.max(s.at(-1)[0], c.first_news_ms);
  const X = (t) => padL + ((t - t0) / (t1 - t0 || 1)) * (w - padL - padR);
  const Y = (p) => padT + (1 - p) * (h - padT - padB);
  const xm = X(c.move_start_ms), xn = X(c.first_news_ms);
  const before = s.filter((d) => d[0] <= c.move_start_ms), after = s.filter((d) => d[0] >= c.move_start_ms);
  let g = '';
  for (const p of [0, 0.5, 1]) {
    g += `<line x1="${padL}" x2="${w - padR}" y1="${f1(Y(p))}" y2="${f1(Y(p))}" class="${p === 0.5 ? 'gl-mid' : 'gl'}"/>`;
    g += `<text x="${w - padR + 6}" y="${f1(Y(p) + 4)}" class="ax">${Math.round(p * 100)}%</text>`;
  }
  // lead window
  if (xn > xm) g += `<rect x="${f1(xm)}" y="${padT}" width="${f1(xn - xm)}" height="${h - padT - padB}" class="lead-win"/>`;
  g += `<path d="${linePath(before.map(([t, p]) => [X(t), Y(p)]))}" class="pline-cold"/>`;
  g += `<path d="${linePath(after.map(([t, p]) => [X(t), Y(p)]))}" class="pline-sig"/>`;
  g += `<line x1="${f1(xm)}" x2="${f1(xm)}" y1="${padT - 6}" y2="${h - padB}" class="mk-sig"/>`;
  g += `<line x1="${f1(xn)}" x2="${f1(xn)}" y1="${padT - 6}" y2="${h - padB}" class="mk-cold"/>`;
  // bracket
  const by = 14;
  if (xn - xm > 24) {
    g += `<path d="M${f1(xm)},${by + 6}V${by}H${f1(xn)}V${by + 6}" class="bracket"/>`;
    g += `<text x="${f1(Math.min(Math.max((xm + xn) / 2, padL + 45), w - 60))}" y="${by - 4}" class="lbl-sig" text-anchor="middle">${dur(c.lead_minutes)} EARLY</text>`;
  } else if (xm - xn > 24) {
    g += `<path d="M${f1(xn)},${by + 6}V${by}H${f1(xm)}V${by + 6}" class="bracket bracket-cold"/>`;
    g += `<text x="${f1(Math.min(Math.max((xm + xn) / 2, padL + 90), w - 100))}" y="${by - 4}" class="lbl-cold" text-anchor="middle">NEWS CAME ${dur(c.lead_minutes)} FIRST</text>`;
  }
  const mLeft = xn < xm ? xm + 97 > w - padR : xm - 92 > padL;
  const mTop = xn < xm && mLeft; // news first and no room on the right: lift it clear of FIRST ARTICLE
  g += `<text x="${f1(mLeft ? xm - 5 : xm + 5)}" y="${mTop ? padT + 14 : h - padB - 8}" class="lbl-sig" text-anchor="${mLeft ? 'end' : 'start'}">PRICE MOVES</text>`;
  const nRight = xn + 100 < w - padR;
  if (xn < xm) { // news first: label the article on the far side so it never sits on PRICE MOVES
    const nLeft = xn - 100 > padL;
    g += `<text x="${f1(nLeft ? xn - 5 : xn + 5)}" y="${nLeft ? h - padB - 8 : padT + 14}" class="lbl-cold" text-anchor="${nLeft ? 'end' : 'start'}">FIRST ARTICLE</text>`;
  } else g += `<text x="${f1(nRight ? xn + 5 : xn - 5)}" y="${nRight ? h - padB - 8 : padT + 14}" class="lbl-cold" text-anchor="${nRight ? 'start' : 'end'}">FIRST ARTICLE</text>`;
  // the stored price trace can stop well before the article; say so instead of letting the line just vanish
  const xe = X(s.at(-1)[0]);
  if (xn - xe > 90 && s.at(-1)[0] > c.move_start_ms) g += `<text x="${f1(xe + 6)}" y="${f1(Y(s.at(-1)[1]) + (s.at(-1)[1] > 0.5 ? 16 : -8))}" class="ax">PRICE TRACE ENDS</text>`;
  g += `<text x="${padL}" y="${h - 6}" class="ax">${clock(t0, { sec: false })}</text>`;
  g += `<text x="${w - padR}" y="${h - 6}" class="ax" text-anchor="end">${clock(t1, { sec: false })}</text>`;
  el.innerHTML = `<svg viewBox="0 0 ${w} ${h}" width="${w}" height="${h}" role="img" aria-label="Price moved ${dur(c.lead_minutes)} ${c.lead_minutes < 0 ? 'after' : 'before'} the first article">${g}</svg>`;
}

// ---------------------------------------------------------------- PROOF: latency race
export function lagChart(el, res) {
  const { w } = size(el, 200);
  const ml = res?.market_lag || {}, sd = res?.stream_delay_reference_s || {};
  const rows = [
    { k: 'THE PLAY', v: 0, cls: 'bone', note: 'real time' },
    { k: 'KALSHI MOVES', v: ml.median_s ?? 2.6, lo: ml.p25_s, hi: ml.p75_s, cls: 'sig', note: `median of ${ml.n_plays ?? '–'} plays` },
    { k: 'CABLE TV', v: sd.broadcast ?? 19, cls: 'cold', note: 'broadcast' },
    { k: 'BEST STREAM', v: sd.best_stream ?? 48, cls: 'cold', note: 'streaming app' },
    { k: 'WORST STREAM', v: sd.worst_stream ?? 62, cls: 'cold', note: 'streaming app' },
  ];
  const max = Math.max(65, ...rows.map((r) => r.v + 3));
  const big = w > 900;
  const padL = big ? 210 : 112, padR = big ? 90 : 56, rowH = big ? 54 : 40, top = 30;
  const h = top + rows.length * rowH + 24;
  const X = (v) => padL + (v / max) * (w - padL - padR);
  let g = '';
  for (let s = 0; s <= max; s += 10) {
    g += `<line x1="${f1(X(s))}" x2="${f1(X(s))}" y1="${top - 8}" y2="${h - 22}" class="gl"/>`;
    g += `<text x="${f1(X(s))}" y="${h - 4}" class="ax" text-anchor="middle">${s}s</text>`;
  }
  rows.forEach((r, i) => {
    const y = top + i * rowH, bh = big ? 20 : 14, yc = y + rowH / 2;
    g += `<text x="0" y="${f1(yc + 5)}" class="row-k">${r.k}</text>`;
    if (r.v > 0) g += `<rect class="hbar bar-${r.cls}" x="${padL}" y="${f1(yc - bh / 2)}" width="${f1(X(r.v) - padL)}" height="${bh}" style="--d:${i * 120}ms"/>`;
    else g += `<rect class="hbar bar-bone" x="${padL - 1}" y="${f1(yc - bh)}" width="3" height="${bh * 2}"/>`;
    if (r.lo != null && r.hi != null) g += `<line x1="${f1(X(r.lo))}" x2="${f1(X(r.hi))}" y1="${f1(yc + bh)}" y2="${f1(yc + bh)}" class="iqr"/>`;
    g += `<text x="${f1(Math.max(X(r.v), padL) + 10)}" y="${f1(yc + 6)}" class="row-v row-v-${r.cls}">${r.v === 0 ? '0 s' : `${Number.isInteger(r.v) ? r.v : r.v.toFixed(1)} s`}</text>`;
  });
  el.innerHTML = `<svg viewBox="0 0 ${w} ${h}" width="${w}" height="${h}" role="img" aria-label="Kalshi moves ${rows[1].v} seconds after a play; streams show it ${rows[3].v} to ${rows[4].v} seconds after">${g}</svg>`;
}

// ---------------------------------------------------------------- DUTCH BOOK payoff
// Returns per-outcome payouts if we can work them out, else null.
export function payoffs(o) {
  if (Array.isArray(o.outcomes) && o.outcomes.length) return o.outcomes.map((x) => ({ label: x.label, payout: x.payout }));
  const legs = o.legs || [];
  if (!legs.length) return null;
  if (o.kind === 'bracket_sum' || o.kind === 'exhaustive_set') {
    return legs.map((li, i) => ({
      label: li.label,
      payout: legs.reduce((s, lj, j) => s + (lj.qty || 1) * ((lj.side === 'yes') === (i === j) ? 1 : 0), 0),
    }));
  }
  if (o.kind === 'complement' && legs.length === 2) {
    return [legs[0], legs[1]].map((li, i) => ({
      label: li.side === 'yes' ? li.label : `Not: ${li.label}`,
      payout: legs.reduce((s, lj, j) => s + (lj.qty || 1) * ((lj.side === 'yes') === (i === j) ? 1 : 0), 0),
    }));
  }
  return null;
}

export function payoffChart(el, o) {
  const { w } = size(el, 160);
  const outs = payoffs(o);
  const cost = o.cost || 0;
  if (!outs || outs.length > 14) {
    // honest fallback: cost vs guaranteed payout
    const max = Math.max(cost, o.worst_case_payout || 0) * 1.08 || 1;
    const padL = 150, padR = 110, X = (v) => padL + (v / max) * (w - padL - padR);
    const h = 104;
    el.innerHTML = `<svg viewBox="0 0 ${w} ${h}" width="${w}" height="${h}" role="img" aria-label="Cost versus guaranteed payout">
      <text x="0" y="30" class="row-k">YOU PAY</text><rect class="hbar bar-cold" x="${padL}" y="16" width="${f1(X(cost) - padL)}" height="20"/>
      <text x="${f1(X(cost) + 8)}" y="31" class="row-v row-v-cold">${usd(cost, { compact: true })}</text>
      <text x="0" y="78" class="row-k">WORST CASE BACK</text><rect class="hbar bar-sig" x="${padL}" y="64" width="${f1(X(o.worst_case_payout) - padL)}" height="20"/>
      <text x="${f1(X(o.worst_case_payout) + 8)}" y="79" class="row-v row-v-sig">${usd(o.worst_case_payout, { compact: true })}</text>
    </svg>`;
    return;
  }
  const n = outs.length;
  const max = Math.max(cost, ...outs.map((x) => x.payout)) * 1.12 || 1;
  const big = w > 700;
  const h = big ? 230 : 190, padT = 26, padB = 64, padL = 8, padR = 8;
  const bw = (w - padL - padR) / n;
  const Y = (v) => padT + (1 - v / max) * (h - padT - padB);
  let g = '';
  outs.forEach((x, i) => {
    const bx = padL + i * bw + bw * 0.16, ww = bw * 0.68;
    const win = x.payout - cost;
    g += `<rect x="${f1(bx)}" y="${f1(Y(x.payout))}" width="${f1(ww)}" height="${f1(Y(0) - Y(x.payout))}" class="${win > 0 ? 'bar-sig' : 'bar-cold'} hbar"/>`;
    g += `<text x="${f1(bx + ww / 2)}" y="${f1(Y(x.payout) - 6)}" class="row-v row-v-${win > 0 ? 'sig' : 'cold'}" text-anchor="middle">${usd(win, { sign: true, compact: true })}</text>`;
    const lab = String(x.label).slice(0, Math.max(6, Math.floor(bw / 6.6)));
    g += `<text x="${f1(bx + ww / 2)}" y="${h - padB + 18}" class="ax" text-anchor="middle">${esc(lab)}</text>`;
  });
  g += `<line x1="${padL}" x2="${w - padR}" y1="${f1(Y(cost))}" y2="${f1(Y(cost))}" class="cost-line"/>`;
  g += `<text x="${w - padR}" y="${f1(Y(cost) - 6)}" class="lbl-cold" text-anchor="end">WHAT YOU PAID ${usd(cost, { compact: true })}</text>`;
  g += `<text x="${padL}" y="${h - 12}" class="ax">IF THE ANSWER IS… (every possible outcome)</text>`;
  el.innerHTML = `<svg viewBox="0 0 ${w} ${h}" width="${w}" height="${h}" role="img" aria-label="Profit in every outcome">${g}</svg>`;
}

export { pct };
