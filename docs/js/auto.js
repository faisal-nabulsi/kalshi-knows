// "Auto" page: rules, kill switch, live order blotter, movers feed.  mountAuto(rootEl, api)
// api: the backend base URL string, or {api:"https://..."} as returned by resolveApi(). Play money only.
const $ = (tag, props = {}, ...kids) => {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === 'class') e.className = v; else if (k === 'text') e.textContent = v;
    else if (k.startsWith('on')) e.addEventListener(k.slice(2), v); else if (v !== false && v != null) e.setAttribute(k, v === true ? '' : v);
  }
  for (const c of kids.flat()) if (c != null) e.append(c.nodeType ? c : document.createTextNode(c));
  return e;
};
const pct = (x) => (x == null ? '–' : (x * 100).toFixed(0) + '¢');
const usd = (x) => (x == null ? '–' : (x < 0 ? '-$' : '$') + Math.abs(x).toFixed(2));
const clean = (t) => String(t || '').replace(/\*\*/g, '');
const isPolitics = (m) => /politic|election/i.test(m.category || '');
const ago = (ms) => { const s = Math.max(0, (Date.now() - ms) / 1000 | 0); return s < 90 ? s + 's' : s < 5400 ? (s / 60 | 0) + 'm' : (s / 3600 | 0) + 'h'; };

export function mountAuto(root, api) {
  const base = ((typeof api === 'string' ? api : (api && (api.api || api.base))) || '').replace(/\/+$/, '');
  const j = async (path, opt) => { const r = await fetch(base + '/api/auto' + path, opt); if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error || r.status); return r.json(); };
  const send = (path, method, body) => j(path, { method, headers: { 'content-type': 'application/json' }, body: body ? JSON.stringify(body) : undefined });
  let cat = 'All', timer = null, alive = true;
  root.classList.add('auto'); root.textContent = '';
  const top = $('div', { class: 'auto-top' }), stats = $('div', { class: 'auto-stats' }), kill = $('button', { class: 'auto-kill', 'aria-pressed': 'false' });
  const note = $('div', { class: 'auto-note' });
  const modeEl = $('div', { class: 'auto-mode is-dry' });
  const mvMeta = $('p', { class: 'auto-mvmeta' });
  const rulesEl = $('div', { class: 'rules' }), builderEl = $('div', { class: 'builder' }), blot = $('div', { class: 'tbl-wrap' }), chips = $('div', { class: 'chips' }), mv = $('div', { class: 'tbl-wrap' });
  top.append(stats, kill);
  root.append($('h2', { text: 'Auto' }),
    $('p', { class: 'sub', text: 'Rules that turn our signals into orders. Play money only: orders go to Kalshi\'s official demo exchange, or are simulated against the live public order book. Not financial advice.' }),
    modeEl, top, note, $('h3', { text: 'Rules' }), rulesEl, $('h3', { text: 'New rule' }), builderEl,
    $('h3', { text: 'Order blotter' }), blot,
    $('h3', { text: 'Movers across Kalshi · every category except politics' }), mvMeta, chips, mv);

  const badge = (o) => o.kind === 'alert_only' ? $('span', { class: 'badge alert', text: 'ALERT ONLY' })
    : o.mode === 'demo' ? $('span', { class: 'badge demo', text: 'KALSHI DEMO' }) : $('span', { class: 'badge dry', text: 'DRY RUN' });
  const describe = (r) => {
    const t = r.trigger, a = r.action; let w;
    if (t.type === 'alert') w = `a spoiler alert for ${t.team && t.team !== 'any' ? t.team : 'any team'}, ${t.play_type && t.play_type !== 'any' ? t.play_type : 'any play'} at ${(t.min_confidence * 100 | 0)}%+`;
    else if (t.type === 'mover') w = `${t.scope === 'any' ? 'any market' : (t.ticker || t.series || t.category)} moves ${(t.min_move * 100 | 0)}+ pts in ${t.window_s} s`;
    else w = `a Dutch Book pays after fees (> $${t.min_profit_after_fees || 0})`;
    const d = a.type === 'alert_only' ? 'alert only (no order)' : a.type === 'buy_set' ? `buy all legs (${a.sets || 1} set)` : `buy ${(a.side || 'yes').toUpperCase()} x${a.count} on ${a.target === 'same_game' || !a.target ? 'the game market' : a.target === 'moved_market' ? 'the moved market' : a.ticker}`;
    return [$('b', { text: 'WHEN ' }), w, $('br'), $('b', { text: 'THEN ' }), d];
  };

  function renderRules(rules) {
    rulesEl.textContent = '';
    for (const r of rules) {
      const l = r.limits || {};
      const tog = $('button', { class: 'tog', role: 'switch', 'aria-checked': String(!!r.enabled), 'aria-label': 'Enable ' + r.name,
        onclick: async () => { await send('/rules', 'POST', { ...r, enabled: !r.enabled }); tick(); } });
      rulesEl.append($('div', { class: 'rule' + (r.enabled ? '' : ' off') },
        $('div', { class: 'rule-name', text: r.name }), $('div', { class: 'rule-when' }, ...describe(r)),
        $('div', { class: 'rule-foot' }, tog, $('span', { class: 'lim', text: `max ${l.max_contracts_per_order ?? '–'}/order · $${l.max_usd_per_day ?? '–'}/day · ${l.cooldown_s ?? 0}s cooldown` }),
          $('button', { class: 'del', text: 'delete', onclick: async () => { await send('/rules/' + encodeURIComponent(r.id), 'DELETE'); tick(); } }))));
    }
    if (!rules.length) rulesEl.append($('div', { class: 'auto-empty', text: 'No rules yet. Build one below.' }));
  }

  function buildBuilder() {
    const sel = (opts, v) => { const s = $('select'); for (const [val, lab] of opts) s.append($('option', { value: val, text: lab })); if (v) s.value = v; return s; };
    const trig = sel([['alert', 'a spoiler alert'], ['mover', 'a market moves'], ['dutchbook', 'a Dutch Book pays']]);
    const team = $('input', { type: 'text', placeholder: 'team (SF) or any', value: 'any' });
    const play = sel([['any', 'any play'], ['TD', 'TD'], ['FG', 'FG'], ['TURNOVER', 'turnover'], ['BIG_PLAY', 'big play']]);
    const conf = $('input', { type: 'number', value: '85', min: '1', max: '100' });
    const scope = $('input', { type: 'text', placeholder: 'ticker/series or any', value: 'any' });
    const mvPts = $('input', { type: 'number', value: '15', min: '1', max: '99' });
    const win = $('input', { type: 'number', value: '60', min: '30' });
    const act = sel([['buy_yes', 'buy YES'], ['buy_no', 'buy NO'], ['alert_only', 'alert only']]);
    const cnt = $('input', { type: 'number', value: '5', min: '1', max: '100' });
    const name = $('input', { type: 'text', placeholder: 'rule name (optional)' });
    const err = $('div', { class: 'err' });
    const aBox = $('span', {}, ' team ', team, ' play ', play, ' confidence ≥ ', conf, '%'), mBox = $('span', {}, ' ', scope, ' by ≥ ', mvPts, ' pts in ', win, ' s');
    const sync = () => { aBox.hidden = trig.value !== 'alert'; mBox.hidden = trig.value !== 'mover'; if (trig.value === 'dutchbook') act.value = 'buy_yes'; };
    trig.addEventListener('change', sync);
    const go = $('button', { class: 'go', text: 'Add rule', onclick: async () => {
      err.textContent = '';
      const t = trig.value; let trigger, action;
      if (t === 'alert') trigger = { type: 'alert', team: team.value.trim() || 'any', play_type: play.value, min_confidence: conf.value / 100, named_only: true };
      else if (t === 'mover') { const s = scope.value.trim(); trigger = { type: 'mover', scope: !s || s === 'any' ? 'any' : s.includes('-') ? 'ticker' : 'series', min_move: mvPts.value / 100, window_s: +win.value };
        if (trigger.scope === 'ticker') trigger.ticker = s; if (trigger.scope === 'series') trigger.series = s.toUpperCase(); }
      else trigger = { type: 'dutchbook', min_profit_after_fees: 0 };
      if (t === 'dutchbook') action = { type: 'buy_set', sets: 1, max_slippage: 0.02 };
      else if (act.value === 'alert_only') action = { type: 'alert_only' };
      else action = { type: 'buy', side: act.value === 'buy_no' ? 'no' : 'yes', count: +cnt.value, max_slippage: 0.02, target: t === 'mover' ? 'moved_market' : 'same_game' };
      if (t === 'mover' && action.type === 'buy') action = { ...action, side: undefined, direction: 'follow' };
      try { await send('/rules', 'POST', { name: name.value || undefined, enabled: true, trigger, action, limits: { max_contracts_per_order: +cnt.value || 5, max_usd_per_day: 10, cooldown_s: 60 } }); name.value = ''; tick(); }
      catch (e) { err.textContent = String(e.message || e); } } });
    builderEl.append($('span', { class: 'kw', text: 'When' }), trig, aBox, mBox, $('span', { class: 'kw', text: 'then' }), act, ' ×', cnt, name, go, err);
    sync();
  }

  function renderStatus(s) {
    stats.textContent = '';
    const stat = (k, v, cls) => $('div', { class: 'auto-stat' }, $('small', { text: k }), $('b', { class: cls || '', text: v }));
    const demo = s.mode === 'demo';
    modeEl.className = 'auto-mode ' + (demo ? 'is-demo' : 'is-dry');
    modeEl.textContent = '';
    const seg = $('div', { class: 'am-seg', role: 'radiogroup', 'aria-label': 'Order mode' });
    for (const [m, lab] of [['dry_run', 'Dry run'], ['demo', 'Kalshi demo']]) {
      seg.append($('button', { role: 'radio', 'aria-checked': String(s.mode === m), disabled: m === 'demo' && !s.key_present,
        title: m === 'demo' && !s.key_present ? 'Needs a Kalshi demo API key on the engine' : '',
        text: lab, onclick: async () => { try { await send('/mode', 'POST', { mode: m }); } catch (e) { note.textContent = 'Mode not changed: ' + (e.message || e); } tick(); } }));
    }
    modeEl.append($('div', { class: 'am-txt' }, $('b', { text: demo ? 'KALSHI DEMO EXCHANGE' : 'DRY RUN' }), $('span', { text: demo ? ' — play money' : ' — simulated against the live Kalshi order book' })), seg);
    stats.append(
      stat('P&L today', usd(s.pnl.today), s.pnl.today < 0 ? 'neg' : 'pos'), stat('P&L total', usd(s.pnl.total), s.pnl.total < 0 ? 'neg' : 'pos'),
      stat('Exposure', usd(s.pnl.exposure)), stat('Orders', String(s.orders)));
    kill.setAttribute('aria-pressed', String(s.kill));
    kill.textContent = ''; kill.append(s.kill ? 'Kill switch ON' : 'Kill switch', $('small', { text: s.kill ? 'no orders will be sent. tap to resume' : 'stop every rule now' }));
    note.textContent = s.key_present ? `Demo key found. Orders go to ${s.demo_base} (play money). Loss cap ${usd(s.daily_loss_cap_usd)}/day.`
      : 'No demo key: running DRY RUN. Orders are simulated against the live public order book and the signed request is only previewed. Scanner: '
        + `${s.scanner.tracked || 0} markets tracked.`;
  }

  function renderOrders(os) {
    blot.textContent = '';
    if (!os.length) return blot.append($('div', { class: 'auto-empty', text: 'No orders yet. Rules fire when their trigger hits.' }));
    const tb = $('tbody');
    for (const o of os.slice(0, 60)) {
      const trg = o.trigger || {};
      const req = o.request ? $('details', {}, $('summary', { text: 'signed request' }), $('pre', { text: JSON.stringify(o.request, null, 1) })) : null;
      const demo = o.demo ? $('details', {}, $('summary', { text: 'demo ' + (o.demo.order_id || '').slice(0, 8) + ' · ' + (o.demo.status || '') }), $('pre', { text: JSON.stringify(o.demo.fills) })) : null;
      tb.append($('tr', {}, $('td', { text: ago(o.ts_ms) }), $('td', {}, badge(o)),
        $('td', {}, $('span', { class: 'atk', text: o.ticker || trg.ticker || '–' }), $('span', { class: 'why', text: o.rule_name }),
          trg.headline || trg.title ? $('span', { class: 'why', text: clean(trg.headline || trg.title) }) : null),
        $('td', { text: o.kind === 'alert_only' ? `${trg.move > 0 ? '+' : ''}${(trg.move * 100).toFixed(0)} pts` : o.side ? `BUY ${o.side.toUpperCase()}` : '' }),
        $('td', { class: 'n', text: o.count ? `${o.filled || 0}/${o.count}` : '' }),
        $('td', { class: 'n', text: o.limit_price ? `${pct(o.limit_price)} lim · ${pct(o.avg_price)} avg` : '' }),
        $('td', { class: 'st-' + o.status }, o.status, o.reason ? $('span', { class: 'why', text: o.reason }) : null, o.note ? $('span', { class: 'why', text: o.note }) : null, req, demo)));
    }
    blot.append($('table', { class: 'tbl' }, $('thead', {}, $('tr', {}, ...['age', 'mode', 'market / rule', 'action', 'filled', 'price', 'status'].map((h) => $('th', { text: h })))), tb));
  }

  function renderMovers(d) {
    d = { ...d, movers: (d.movers || []).filter((m) => !isPolitics(m)) };
    mvMeta.textContent = `Proof the engine isn't just NFL: it scans ${d.scanner.tracked || 0} active markets every 30 s and lists every 5+ point move in a minute.${d.movers.length ? ` ${new Set(d.movers.map((m) => m.category)).size} categories moving right now.` : ''}`;
    const cats = ['All', ...new Set(d.movers.map((m) => m.category))];
    chips.textContent = '';
    for (const c of cats) chips.append($('button', { class: 'chip', text: c, 'aria-pressed': String(c === cat), onclick: () => { cat = c; tick(); } }));
    mv.textContent = '';
    const items = d.movers.filter((m) => cat === 'All' || m.category === cat);
    if (!items.length) return mv.append($('div', { class: 'auto-empty', text: `Scanning ${d.scanner.tracked || 0} active markets every 30 s. Moves of 5+ points show up here.` }));
    const tb = $('tbody');
    for (const m of items.slice(0, 40)) tb.append($('tr', {}, $('td', { text: ago(m.ts_ms) }), $('td', { text: m.category }),
      $('td', {}, $('span', { class: 'atk', text: clean(m.title) || m.ticker }), $('span', { class: 'why', text: m.ticker })),
      $('td', { class: 'n ' + (m.move > 0 ? 'mv-up' : 'mv-dn'), text: `${m.move > 0 ? '+' : ''}${(m.move * 100).toFixed(0)} pts / ${m.window_s}s` }),
      $('td', { class: 'n', text: `${pct(m.p_then)} → ${pct(m.p_now)}` })));
    mv.append($('table', { class: 'tbl' }, $('thead', {}, $('tr', {}, ...['age', 'category', 'market', 'move', 'price'].map((h) => $('th', { text: h })))), tb));
  }

  async function tick() {
    if (!alive) return;
    try {
      const [s, r, o, m] = await Promise.all([j('/status'), j('/rules'), j('/orders?limit=60'), j('/movers?limit=80')]);
      renderStatus(s); renderRules(r); renderOrders(o); renderMovers(m);
    } catch (e) { note.textContent = 'Auto engine offline: ' + (e.message || e); }
  }
  kill.addEventListener('click', async () => { await send('/kill', 'POST', { on: kill.getAttribute('aria-pressed') !== 'true' }); tick(); });
  buildBuilder(); tick();
  timer = setInterval(() => { if (!document.hidden) tick(); }, 3000);
  return () => { alive = false; clearInterval(timer); };   // unmount
}
