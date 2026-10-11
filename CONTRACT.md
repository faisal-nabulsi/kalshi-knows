# Kalshi Knows: interface contract (every agent builds against this)

Product: **Kalshi Knows**, the prediction market as a time machine. Three time scales:
- **Now: Dutch Book.** Open Kalshi prices that contradict each other (a set of paper trades that pays off in every outcome).
- **Seconds: Kalshi Knows (live).** The market moves when a play happens; TV streams are 20–60 s behind. We detect the jump, infer the play, and push a spoiler to phones before the TV shows it.
- **Hours: Someone Knew.** Settled markets whose price moved before the first news article.

## Hard rules (all agents)
- Kalshi: PUBLIC endpoints only, base `https://api.elections.kalshi.com/trade-api/v2`. No API key, no auth, no trading endpoints, ever. Stay at or below 4 requests/s per process. Back off on 429/5xx (exponential, with jitter).
- ESPN public JSON: `https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard` and `/summary?event=<id>` (plays carry `wallclock`).
- Paper trading only. Present everything as insight, not financial advice.
- No politics or elections markets anywhere in the UI. Keep it PG. Never accuse named people of insider trading: say "the market moved before the first article."
- Write everything fresh (hackathon rule: nothing we built before). Open-source libraries and public datasets are fine.
- Python: `.venv/bin/python` (3.12). Add packages with `uv pip install --python .venv/bin/python <pkg>`.
- Only edit files in your own directory. Commit only your own paths (`git add <your paths> && git commit`). If `.git/index.lock` exists, wait 2 s and retry. Never `git add -A`, never switch branches.
- Secrets live in `engine/.env` (gitignored). Never print or commit them.

## Repo layout
```
docs/                 website (GitHub Pages root, static PWA). Owner: web agent
docs/data/*.json      static snapshots the site falls back to when the backend is offline
docs/config.json      {"api": "https://<tunnel>.trycloudflare.com"} (written by engine/run_live.sh)
engine/               live backend (FastAPI). Owner: live-engine agent (dutchbook.py: dutchbook agent)
pipeline/             offline data jobs. Owners: nfl-data agent (nfl_*), someone-knew agent (someone_knew*)
train/                model training on AWS. Owner: lead (Faisal's main session)
results/              metrics JSON + charts
```

## Timestamps and prices
- All timestamps are **epoch milliseconds (UTC)** as integers, field names end in `_ms`.
- All probabilities and prices are floats in **[0,1]** (Kalshi dollars = probability).

## Backend API (base URL from docs/config.json; CORS open; HTTPS via Cloudflare tunnel)
- `GET /api/health` → `{"ok":true,"now_ms":int,"games_tracked":int,"mode":"live"|"replay"}`
- `GET /api/games` → list of
  ```json
  {"game_id":"401872992","short_name":"SF @ SEA","home":"SEA","away":"SF",
   "home_score":17,"away_score":14,"period":4,"clock":"8:12","status":"in"|"pre"|"post",
   "possession":"SF","situation":"2nd & 7 at SEA 34",
   "kalshi_home":"KXNFLGAME-26OCT11SFSEA-SEA","kalshi_away":"KXNFLGAME-26OCT11SFSEA-SF",
   "p_home":0.62,"history":[[ts_ms,p_home], ...]}   // last ~20 min, ~2 s resolution
  ```
- `GET /api/alerts?since_ms=` → list of
  ```json
  {"id":"a_17", "ts_ms":int, "game_id":"401872992", "team":"SF",
   "p_before":0.41, "p_after":0.58, "delta":0.17,           // signed, in favour of `team`
   "inferred":[{"type":"TD","team":"SF","prob":0.81},{"type":"TURNOVER","team":"SF","prob":0.11}],
   "headline":"49ers touchdown (81% sure)",
   "confirmed":null | {"play_text":"...","espn_wallclock_ms":int,"espn_seen_ms":int,"lead_s":float}}
  ```
  Play types: `TD`, `FG`, `TURNOVER`, `BIG_PLAY`, `SAFETY`, `OTHER`.
- `GET /api/stream` → Server-Sent Events: `event: games` (data = games list) every ~2 s; `event: alert` (data = alert) when an alert fires or gets confirmed.
- `GET /api/push/vapid` → `{"publicKey":"<base64url>"}`
- `POST /api/push/subscribe` body = browser `PushSubscription.toJSON()` → `{"ok":true}`
- `POST /api/push/test` → sends a test push to every subscriber
- `POST /api/guess` `{"alert_id","nickname","guess":"TD"|"FG"|"TURNOVER"|"BIG_PLAY"}` → `{"ok":true}`
- `GET /api/guesses?alert_id=` → `{"TD":12,"FG":3,"TURNOVER":5,"BIG_PLAY":2,"n":22}`
- `GET /api/dutchbook` → same schema as `docs/data/dutchbook.json` below (live, refreshed every ~60 s)

Push payload (JSON the service worker receives): `{"title":"SPOILER · SF @ SEA","body":"49ers touchdown (81% sure). Your stream shows it in ~30s.","url":"./#live","tag":"a_17"}`

## Static data files (docs/data/), the site's offline fallback
- `replay.json`: a real recorded game, so the site works with no backend:
  `{"game":{...games item without history...},"history":[[ts_ms,p_home],...],"alerts":[alert,...],"plays":[{"wallclock_ms":int,"text":"...","type":"TD"|...,"team":"SF"}]}`
- `dutchbook.json`:
  `{"updated_ms":int,"scanned_events":int,"scanned_markets":int,"total_mispricing_usd":float,
    "opportunities":[{"id":"...","event_ticker":"...","title":"...","category":"...",
      "kind":"bracket_sum"|"ladder"|"exhaustive_set"|"complement",
      "legs":[{"ticker":"...","label":"...","side":"yes"|"no","price":0.12,"qty":1}],
      "cost":float,"worst_case_payout":float,"profit_before_fees":float,"fees":float,"profit_after_fees":float,
      "explanation":"plain-English one-liner"}],
    "near_misses":[ ...same shape, profit_after_fees <= 0 but profit_before_fees > 0 ... ],
    "by_category":{"Economics":{"events":int,"violations":int}, ...}}`
- `someone_knew.json`:
  `{"generated_ms":int,"markets_scanned":int,"cases":[{"ticker":"...","title":"...","category":"...","result":"yes"|"no",
     "move_start_ms":int,"move_end_ms":int,"p_before":0.12,"p_after":0.91,
     "first_news_ms":int,"first_news_title":"...","first_news_url":"...","first_news_source":"...",
     "lead_minutes":float,"series":[[ts_ms,p],...],"verdict":"plain-English one-liner"}],
    "stats":{"median_lead_minutes":float,"share_market_first":float,"n":int}}`
- `results.json` (lead fills in): `{"market_lag":{"median_s":float,"p25_s":float,"p75_s":float,"n_plays":int,"by_type":{...}},
   "stream_delay_reference_s":{"broadcast":19,"best_stream":48,"worst_stream":62},
   "detector":{"precision":float,"recall":float,"n_alerts":int},
   "model":{"name":"...","accuracy":float,"top2":float,"baseline_accuracy":float,"n_test":int},
   "games_analyzed":int}`
