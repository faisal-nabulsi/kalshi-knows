// "Two venues, one game": Kalshi vs Polymarket for each live game. No-op when the engine has no /api/venues.
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const WINDOW_MS = 10 * 60 * 1000;
const cents = (p) => `${Math.round(p * 100)}c`;

function chart(g, now, w = 320, h = 84) {
  const t0 = now - WINDOW_MS;
  const k = (g.kalshi_history || []).filter((x) => x[0] >= t0);
  const p = (g.poly_history || []).filter((x) => x[0] >= t0);
  const all = [...k, ...p].map((x) => x[1]);
  if (!all.length) return '';
  let lo = Math.min(...all), hi = Math.max(...all);
  const pad = Math.max(0.02, (hi - lo) * 0.15);
  lo = Math.max(0, lo - pad); hi = Math.min(1, hi + pad);
  const X = (t) => ((t - t0) / WINDOW_MS) * w;
  const Y = (v) => h - ((v - lo) / (hi - lo || 1)) * h;
  // step line (a price holds until the next update), extended to "now"
  const path = (pts) => {
    if (!pts.length) return '';
    let d = `M${X(pts[0][0]).toFixed(1)},${Y(pts[0][1]).toFixed(1)}`;
    for (let i = 1; i < pts.length; i++) d += `H${X(pts[i][0]).toFixed(1)}V${Y(pts[i][1]).toFixed(1)}`;
    return d + `H${w}`;
  };
  const grid = [lo, (lo + hi) / 2, hi].map((v) => `<line x1="0" x2="${w}" y1="${Y(v).toFixed(1)}" y2="${Y(v).toFixed(1)}" class="vn-grid"/><text x="2" y="${(Y(v) - 2).toFixed(1)}" class="vn-ax">${Math.round(v * 100)}</text>`).join('');
  return `<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" class="vn-svg" role="img" aria-label="${esc(g.home)} win probability on Kalshi and Polymarket, last 10 minutes">${grid}
    <path d="${path(p)}" class="vn-line vn-poly"/><path d="${path(k)}" class="vn-line vn-kalshi"/></svg>`;
}

function badge(g) {
  const l = g.last_leadlag;
  if (!l || l.kalshi_first_by_s == null) return '<span class="vn-badge vn-badge-none mono">no lead-lag measured yet</span>';
  const s = l.kalshi_first_by_s;
  if (Math.abs(s) < 1) return `<span class="vn-badge mono">Both venues moved together (${esc(l.team || '')})</span>`;
  return `<span class="vn-badge ${s > 0 ? 'vn-k' : 'vn-p'} mono">${s > 0 ? 'Kalshi' : 'Polymarket'} moved first by ${Math.abs(s).toFixed(1).replace(/\.0$/, '')} s</span>`;
}

function render(root, d) {
  const gs = (d.games || []).filter((g) => g.status === 'in' && g.mapping === 'ok' && g.poly_p_home != null && g.kalshi_p_home != null);
  if (!gs.length) { root.hidden = true; root.innerHTML = ''; return; }
  root.hidden = false;
  root.innerHTML = `<div class="vn-head"><h3 class="vn-title">Two venues, one game</h3>
    <span class="vn-key mono"><i class="vn-sw vn-kalshi"></i>Kalshi <i class="vn-sw vn-poly"></i>Polymarket</span></div>
    <div class="vn-grid-cards">${gs.map((g) => {
      const gap = g.gap == null ? null : Math.round(g.gap * 100);
      const gapTxt = gap == null ? '–' : gap === 0 ? '0c' : `${gap > 0 ? '+' : ''}${gap}c`;
      return `<article class="vn-card">
        <div class="vn-row"><b class="vn-name">${esc(g.short_name)}</b><span class="vn-clock mono">${g.period ? `Q${esc(g.period)} ` : ''}${esc(g.clock || '')}</span></div>
        <div class="vn-prices mono"><span class="vn-kalshi-t">${esc(g.home)} ${cents(g.kalshi_p_home)}</span><span class="vn-poly-t">${esc(g.home)} ${cents(g.poly_p_home)}</span>
          <span class="vn-gap" title="Kalshi minus Polymarket, home-win probability">gap ${gapTxt}</span></div>
        ${chart(g, d.now_ms)}
        ${badge(g)}
      </article>`;
    }).join('')}</div>
    <p class="vn-note mono">Home-team win probability, midpoint of best bid and ask on each venue, last 10 min. Polymarket times are when our server received them (their own trade times lag about 2 s). Kalshi is sampled about every 2 s.</p>`;
}

export function mountVenues(rootEl, api) {
  if (!rootEl || !api) return () => {};
  if (!document.querySelector('link[data-venues-css]')) {
    const l = document.createElement('link');
    l.rel = 'stylesheet'; l.href = new URL('../venues.css', import.meta.url).href; l.dataset.venuesCss = '1';
    document.head.appendChild(l);
  }
  rootEl.classList.add('venues'); rootEl.hidden = true;
  let stop = false, timer = null, ctl = null;
  const tick = async () => {
    if (stop) return;
    try {
      ctl = new AbortController();
      const to = setTimeout(() => ctl.abort(), 6000);
      const r = await fetch(`${api}/api/venues`, { signal: ctl.signal, cache: 'no-store' });
      clearTimeout(to);
      if (r.status === 404) { rootEl.hidden = true; return; } // engine without the venues module: stay silent, stop polling
      if (r.ok) render(rootEl, await r.json());
    } catch (e) { /* offline or slow: keep the last render */ }
    if (!stop) timer = setTimeout(tick, 2000);
  };
  tick();
  return () => { stop = true; clearTimeout(timer); ctl?.abort(); rootEl.hidden = true; rootEl.innerHTML = ''; };
}
