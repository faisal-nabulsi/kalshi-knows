// Picks page (#/picks): bets the cross-market model would make right now, from data/picks.json (engine/picks.py)
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const pc = (x) => `${Math.round(x * 100)}%`;
const ago = (ms) => { const m = Math.round((Date.now() - ms) / 60000); return m < 1 ? 'just now' : m < 60 ? `${m} min ago` : `${Math.round(m / 60)} h ago`; };
function closesIn(ms) {
  const h = (ms - Date.now()) / 3600000;
  if (h <= 0) return 'already settled';
  return h < 1 ? `${Math.round(h * 60)} min` : h < 48 ? `${Math.floor(h)} h ${Math.round((h % 1) * 60)} min` : `${Math.round(h / 24)} days`;
}
const CSS = `
.pk-wrap{display:grid;gap:18px}
.pk-meta{color:var(--ink3);font-size:.78rem;letter-spacing:.04em}
.pk-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:14px}
.pk-card{background:var(--bg2);border:1px solid var(--line);padding:16px 16px 14px;display:grid;gap:10px;min-width:0}
.pk-card.near{opacity:.78;border-style:dashed}
.pk-top{display:flex;justify-content:space-between;gap:10px;align-items:flex-start}
.pk-title{font:600 1rem/1.3 var(--body);margin:0;overflow-wrap:anywhere}
.pk-sub{color:var(--ink2);font-size:.85rem;margin:2px 0 0;overflow-wrap:anywhere}
.pk-side{font:700 1.5rem/1 var(--display);letter-spacing:.02em;padding:4px 10px;border:1px solid currentColor;white-space:nowrap}
.pk-side.yes{color:var(--sig)}.pk-side.no{color:var(--cold)}
.pk-nums{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
.pk-nums div{background:var(--bg3);padding:8px}
.pk-nums dt{color:var(--ink3);font-size:.68rem;text-transform:uppercase;letter-spacing:.08em}
.pk-nums dd{margin:2px 0 0;font:600 1.15rem/1.1 var(--mono)}
.pk-bar{position:relative;height:6px;background:var(--bg3)}
.pk-bar i{position:absolute;top:-3px;width:2px;height:12px}
.pk-bar .m{background:var(--ink3)}.pk-bar .o{background:var(--sig)}
.pk-foot{display:flex;flex-wrap:wrap;gap:6px 14px;color:var(--ink2);font-size:.76rem}
.pk-tier{color:var(--bg);background:var(--ink2);padding:0 6px;font-weight:700}
.pk-tier.A{background:var(--sig)}
.pk-record{border:1px solid var(--line2);background:var(--bg2);padding:18px;display:grid;gap:8px}
.pk-record h3{margin:0;font:700 clamp(1.4rem,3.4vw,2.1rem)/1.05 var(--display);letter-spacing:.01em}
.pk-record p{margin:0;color:var(--ink2);font-size:.9rem}
.pk-label{color:var(--sig);font-size:.74rem;letter-spacing:.06em;text-transform:uppercase}
.pk-empty{color:var(--ink2);border:1px dashed var(--line2);padding:14px}
.pk-disc{color:var(--ink3);font-size:.8rem;border-top:1px solid var(--line);padding-top:12px}
`;
function card(p, near) {
  const yes = p.side === 'YES';
  const mine = yes ? p.model_prob : 1 - p.model_prob, mkt = yes ? p.market_price : 1 - p.market_price;
  const sub = [p.yes_label && `YES = ${p.yes_label}`, p.event_title && p.event_title !== p.title ? p.event_title : ''].filter(Boolean).join(' · ');
  return `<article class="pk-card${near ? ' near' : ''}">
    <div class="pk-top"><div><h3 class="pk-title">${esc(p.title)}</h3>${sub ? `<p class="pk-sub">${esc(sub)}</p>` : ''}</div>
      <span class="pk-side ${yes ? 'yes' : 'no'}">${near ? 'LEAN ' : 'BUY '}${esc(p.side)}</span></div>
    <dl class="pk-nums mono">
      <div><dt>Our odds</dt><dd>${pc(mine)}</dd></div>
      <div><dt>Market</dt><dd>${Math.round(mkt * 100)}¢</dd></div>
      <div><dt>Edge</dt><dd class="${near ? '' : 'sig'}">${p.edge_cents.toFixed(1)}¢</dd></div>
    </dl>
    <div class="pk-bar" title="grey = market price, orange = our probability (for ${esc(p.side)})"><i class="m" style="left:${(mkt * 100).toFixed(1)}%"></i><i class="o" style="left:${(mine * 100).toFixed(1)}%"></i></div>
    <div class="pk-foot mono"><span>EV after fees <b>${p.ev_cents_per_contract >= 0 ? '+' : ''}${p.ev_cents_per_contract.toFixed(1)}¢</b>/contract</span>
      <span>${(p.close_ms - Date.now()) <= 0 ? 'settled' : 'closes in ' + closesIn(p.close_ms)}</span><span>${esc(p.category || 'Other')}</span><span>${esc(p.horizon)} bucket</span>
      <span class="pk-tier ${esc(p.tier)}">TIER ${esc(p.tier)}</span></div>
  </article>`;
}
export function renderPicks(root, d) {
  if (!document.getElementById('pk-css')) { const s = document.createElement('style'); s.id = 'pk-css'; s.textContent = CSS; document.head.appendChild(s); }
  const b = d.backtest || {}, h24 = b.h24 || {}, h6 = b.h6 || {};
  const picks = d.picks || [], near = d.closest || [];
  root.innerHTML = `<div class="pk-wrap">
    <p class="pk-meta mono">${d.markets_scored} open markets scored ${ago(d.generated_ms)} · closing in ${d.window_hours?.[0] ?? 1}–${d.window_hours?.[1] ?? 30} h · bet when |model − price| ≥ ${Math.round((d.threshold ?? 0.08) * 100)}¢ · ${picks.length} pick${picks.length === 1 ? '' : 's'}</p>
    ${picks.length ? `<div class="pk-grid">${picks.slice(0, 24).map((p) => card(p, false)).join('')}</div>`
      : `<p class="pk-empty">No market clears the ${Math.round((d.threshold ?? 0.08) * 100)}¢ edge bar right now, so the model makes no bet. These are the closest calls:</p>
         <div class="pk-grid">${near.map((p) => card(p, true)).join('')}</div>`}
    <section class="pk-record">
      <span class="pk-label mono">${esc(b.label || '')}</span>
      <h3>Backtest on ${(h24.bets ?? 1603).toLocaleString()} unseen markets: won ${Math.round((h24.win_rate ?? 0.582) * 100)}%, +${Math.round((h24.roi_after_fees ?? 0.12) * 100)}% after fees</h3>
      <p class="pk-context">For context: at standard sportsbook odds (−110) you need 52.4% just to break even, and professional bettors who sustain ~55% are considered elite.</p>
      <p class="mono">Trained on ${(b.training_markets ?? 4363922).toLocaleString()} settled Kalshi markets, tested on ${esc(b.test_month || '2026-01')} it never saw. Rule: ${esc(b.rule || '')}. Won ${((h24.win_rate ?? 0) * 100).toFixed(1)}%, +${h24.pnl_cents_per_contract}¢ per contract, ROI +${((h24.roi_after_fees ?? 0) * 100).toFixed(1)}% after fees (95% CI ${((h24.roi_ci95?.[0] ?? 0) * 100).toFixed(1)}–${((h24.roi_ci95?.[1] ?? 0) * 100).toFixed(1)}%). At 6 h before close: ${(h6.bets ?? 0).toLocaleString()} bets, +${((h6.roi_after_fees ?? 0) * 100).toFixed(1)}%.</p>
      ${d.scorer_note ? `<p>Live scorer: ${esc(d.scorer_note)}</p>` : ''}
    </section>
    <p class="pk-disc mono">${esc(d.disclaimer || 'Paper recommendations, not financial advice. 21+. Kalshi demo exchange for automated orders.')}</p>
  </div>`;
}
function liveCard(p) {
  const yes = p.side === 'YES', q = p.model_q, ask = p.ask;
  const sub = [p.yes_label && p.yes_label !== p.title ? `YES = ${p.yes_label}` : '', p.category && p.category !== 'Other' ? p.category : ''].filter(Boolean).join(' · ');
  return `<article class="pk-card">
    <div class="pk-top"><div><h3 class="pk-title">${esc(p.title)}</h3>${sub ? `<p class="pk-sub">${esc(sub)}</p>` : ''}</div>
      <span class="pk-side ${yes ? 'yes' : 'no'}">BUY ${esc(p.side)}</span></div>
    <dl class="pk-nums mono">
      <div><dt>Our odds</dt><dd>${pc(q)}</dd></div>
      <div><dt>Ask then</dt><dd>${Math.round(ask * 100)}¢</dd></div>
      <div><dt>Pay up to</dt><dd class="sig">${Math.round(p.max_price * 100)}¢</dd></div>
    </dl>
    <div class="pk-bar" title="grey = price you pay, orange = our probability (for ${esc(p.side)})"><i class="m" style="left:${(ask * 100).toFixed(1)}%"></i><i class="o" style="left:${(q * 100).toFixed(1)}%"></i></div>
    <div class="pk-foot mono"><span>EV after fees <b>+${(p.ev_cents_per_contract ?? 0).toFixed(1)}¢</b>/contract</span>
      <span>${(p.close_ms - Date.now()) <= 0 ? 'closed, waiting to settle' : 'closes in ' + closesIn(p.close_ms)}</span><span>picked ${ago(p.ts_ms)} · ${esc(p.horizon)} before close</span></div>
  </article>`;
}
function renderLive(root, d) {
  if (!document.getElementById('pk-css')) { const s = document.createElement('style'); s.id = 'pk-css'; s.textContent = CSS; document.head.appendChild(s); }
  const rec = d.record || {}, picks = d.picks || [], near = d.near || [], hz = (d.rules && d.rules.horizons) || {};
  const money = (x) => (x == null ? '–' : `${x < 0 ? '−' : '+'}$${Math.abs(x).toFixed(2)}`);
  const since = rec.since_ms ? new Date(rec.since_ms).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) : 'today';
  const settled = rec.settled || 0;
  root.innerHTML = `<div class="pk-wrap">
    <p class="pk-meta mono">${d.generated_ms ? `Last scan ${ago(d.generated_ms)}: ${d.looked} markets reached 24 h or 6 h before close and got their one look` : 'First scan running…'}${d.scanning ? ' · scanning now' : ''} · bet when the model beats the price by ${hz['24h'] ? hz['24h'].threshold_cents : 8}¢ (24 h) / ${hz['6h'] ? hz['6h'].threshold_cents : 5}¢ (6 h) and the bet still pays after fees at the ask · ${picks.length} open pick${picks.length === 1 ? '' : 's'}</p>
    ${picks.length ? `<div class="pk-grid">${picks.slice(0, 30).map(liveCard).join('')}</div>`
      : `<p class="pk-empty">No open picks right now. The model only bets when a market reaches 24 h or 6 h before close with a big enough edge. Closest calls from the last scan:</p>
         <div class="pk-grid">${near.slice(0, 6).map((p) => card({ ...p, side: p.side, tier: 'C', ev_cents_per_contract: p.ev_cents_per_contract ?? 0 }, true)).join('')}</div>`}
    <section class="pk-record">
      <span class="pk-label mono">Live forward test since ${esc(since)} · real prices · graded when each market settles</span>
      <h3>${settled ? `${rec.won} of ${settled} settled picks won · ${money(rec.pnl_usd_at_10_per_bet)} at $10 a pick` : `${rec.picks || 0} pick${rec.picks === 1 ? '' : 's'} logged · first results when they settle`}</h3>
      <p class="mono">${settled ? `Win rate ${(rec.win_rate * 100).toFixed(1)}% · ${rec.pnl_cents_per_contract >= 0 ? '+' : ''}${rec.pnl_cents_per_contract.toFixed(1)}¢ per contract after fees · ROI ${(rec.roi * 100).toFixed(1)}% on $${rec.staked_usd.toFixed(0)} staked · ` : ''}${rec.open || 0} still open. Every pick is priced at the ask you'd really pay, then the Kalshi taker fee. A few dozen results say little; it takes a few hundred to tell a real edge from luck.</p>
    </section>
    <section class="pk-record">
      <span class="pk-label mono">Backtest · Jan 2026 · one month the model never saw</span>
      <h3>1,603 bets at 24 h before close: won 58%, +12% after fees</h3>
      <p class="mono">Trained on 4,363,922 settled Kalshi markets. 95% interval for the return: +6.5% to +17.8%. Fills were assumed at the last traded price, which is kinder than paying the ask; with 1¢ worse fills it was still +5.1¢ per contract. At 6 h before close: 5,371 bets, +6.7%.</p>
      ${d.scorer ? `<p>Live scorer: ${esc(d.scorer)}</p>` : ''}
    </section>
    <p class="pk-disc mono">${esc(d.disclaimer || '')}</p>
  </div>`;
}
export async function mountPicks(root, api) {
  const base = ((typeof api === 'string' ? api : (api && (api.api || api.base))) || '').replace(/\/+$/, '');
  if (base) {
    try {
      const r = await fetch(`${base}/api/picks`, { cache: 'no-store' });
      if (r.ok) { renderLive(root, await r.json()); return; }
    } catch { /* engine offline: fall back to the last static snapshot */ }
  }
  try {
    const r = await fetch(`data/picks.json?t=${Date.now()}`, { cache: 'no-store' });
    if (!r.ok) throw new Error(`picks.json ${r.status}`);
    renderPicks(root, await r.json());
  } catch (e) { root.innerHTML = `<p class="pk-empty">Couldn't load picks: ${esc(e.message || String(e))}</p>`; }
}
