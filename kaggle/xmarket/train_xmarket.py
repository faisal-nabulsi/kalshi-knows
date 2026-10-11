"""Kalshi Knows: cross-market study on the Jon-Becker public Kalshi dataset (MIT).

Runs on a Kaggle GPU kernel with internet on. Steps:
 1. download data.tar.zst (36 GiB) and stream-extract ONLY Kalshi markets + trades (reduced columns)
 2. settled binary Kalshi markets (multivariate/combo skipped) + price features from trades strictly BEFORE
    close_time - {24h, 6h, 1h}
 3. time-split (event-level, embargoed) models: raw price vs calibration vs XGBoost (GPU), by category,
    reliability by price decile, favorite-longshot bias, paper strategy net of Kalshi taker fee
 4. outputs in /kaggle/working/xmarket_out (+ offline W&B run in /kaggle/working/wandb). No API keys used.
Set XM_SMOKE=1 to run the whole thing on a small synthetic dataset (no download).
"""
import glob, io, json, math, os, re, shutil, subprocess, sys, tarfile, time, urllib.request
T0 = time.time()
SMOKE = os.environ.get("XM_SMOKE") == "1"
LOCAL = os.environ.get("XM_LOCAL") == "1"   # run on the Mac (Kaggle egress to the data hosts was blocked)
MOD = int(os.environ.get("XM_MOD", "1"))     # keep markets with hash(ticker) % MOD == 0
URL = "https://s3.jbecker.dev/data.tar.zst"
OUT = "/tmp/xm_smoke_out" if SMOKE else ("/tmp/xm_local_out" if LOCAL else "/kaggle/working/xmarket_out")
os.makedirs(OUT, exist_ok=True)
if LOCAL:
    os.environ.update({"WANDB_MODE": "offline", "WANDB_DIR": OUT, "WANDB_SILENT": "true"})
elif not SMOKE:
    os.environ.update({"WANDB_MODE": "offline", "WANDB_DIR": "/kaggle/working", "WANDB_SILENT": "true"})
    subprocess.run("pip install -q wandb duckdb zstandard 2>&1 | tail -2", shell=True)
else:
    os.environ.update({"WANDB_MODE": "offline", "WANDB_DIR": "/tmp/xm_smoke_out", "WANDB_SILENT": "true"})

import numpy as np, pandas as pd, pyarrow as pa, pyarrow.compute as pc, pyarrow.parquet as pq, duckdb


def log(*a):
    print(f"[{time.time() - T0:7.0f}s]", *a, flush=True)


def sh(c):
    log("$", c)
    return subprocess.run(c, shell=True, capture_output=True, text=True).stdout.strip()


log("df:\n" + sh("df -h / /tmp /kaggle/working /kaggle/tmp 2>&1"))
log("mem:", sh("free -g | head -2"), "| cpus:", os.cpu_count(), "| gpu:", sh("nvidia-smi -L 2>&1 | head -2"))

H = [("24h", 86400), ("6h", 21600), ("1h", 3600)]
MKCOLS = ["ticker", "event_ticker", "market_type", "title", "status", "last_price", "volume", "open_interest",
          "result", "created_time", "open_time", "close_time", "_fetched_at"]

# ---------------------------------------------------------------- 1. extraction
RED = None


def pick_dir():
    best, free = None, -1
    for d in ["/tmp/xm_local"] if LOCAL else (["/kaggle/tmp", "/tmp"] if not SMOKE else ["/tmp"]):
        try:
            os.makedirs(d, exist_ok=True)
            f = shutil.disk_usage(d).free
            if f > free:
                best, free = d, f
        except Exception:
            pass
    return best, free


def extract():
    global RED
    base, free = pick_dir()
    log(f"workdir {base} free {free / 1e9:.0f} GB")
    RED = f"{base}/kalshi_red"
    shutil.rmtree(RED, ignore_errors=True)
    os.makedirs(RED)
    # Kaggle's resolver failed on s3.jbecker.dev in attempt 1: probe plain DNS, then pinned Cloudflare IPs
    opts = None
    for cand in ["", "--resolve s3.jbecker.dev:443:172.67.73.34", "--resolve s3.jbecker.dev:443:104.26.10.33",
                 "--resolve s3.jbecker.dev:443:104.26.11.33"]:
        r = subprocess.run(f"curl -sSI -m 25 {cand} {URL} | head -3", shell=True, capture_output=True, text=True)
        log("probe", repr(cand), "->", (r.stdout + r.stderr).strip().replace("\n", " | ")[:200])
        if "200" in r.stdout:
            opts = cand
            break
    if opts is None:
        raise SystemExit("cannot reach s3.jbecker.dev from this kernel (DNS and pinned-IP probes failed)")
    # stream straight through a pipe (download overlaps extraction); disk is not needed for the archive
    src_cmd = ["bash", "-c", f"curl -L -sS {opts} --retry 10 --retry-all-errors {URL} | zstd -dc -T0"]
    use_file = False
    arc = None
    if not shutil.which("zstd"):
        sh("apt-get install -y -q zstd 2>&1 | tail -1")
    if not shutil.which("zstd"):
        raise SystemExit("zstd missing")
    proc = subprocess.Popen(src_cmd, stdout=subprocess.PIPE, bufsize=1 << 22)
    tar = tarfile.open(fileobj=proc.stdout, mode="r|")
    mk_parts, tr_buf, tr_rows, part_i, n_files, n_trade_rows = [], [], 0, 0, 0, 0
    sizes = {"markets": 0, "trades": 0}
    TRCOLS = ["ticker", "count", "yes_price", "taker_side", "created_time"]
    t_last = time.time()

    def flush():
        nonlocal tr_buf, tr_rows, part_i
        if tr_buf:
            pq.write_table(pa.concat_tables(tr_buf), f"{RED}/p{part_i:05d}.parquet", compression="zstd")
            part_i += 1
            tr_buf, tr_rows = [], 0

    for m in tar:
        if not m.isfile() or not m.name.endswith(".parquet"):
            continue
        n = m.name
        if "/kalshi/markets/" in n:
            b = tar.extractfile(m).read()
            t = pq.read_table(io.BytesIO(b))
            mk_parts.append(t.select([c for c in MKCOLS if c in t.column_names]).to_pandas())
            sizes["markets"] += 1
        elif "/kalshi/trades/" in n:
            b = tar.extractfile(m).read()
            t = pq.read_table(io.BytesIO(b), columns=TRCOLS)
            keep = pc.invert(pc.starts_with(t["ticker"], "KXMVE"))
            t = t.filter(keep)
            ts = pc.cast(pc.cast(t["created_time"], pa.timestamp("s")), pa.int64())
            r = pa.table({"ticker": t["ticker"], "ts": ts,
                          "price": pc.cast(t["yes_price"], pa.int16()),
                          "cnt": pc.cast(t["count"], pa.int32()),
                          "tyes": pc.cast(pc.equal(t["taker_side"], "yes"), pa.int8())})
            tr_buf.append(r)
            tr_rows += r.num_rows
            n_trade_rows += r.num_rows
            sizes["trades"] += 1
            if tr_rows > 4_000_000:
                flush()
        n_files += 1
        if time.time() - t_last > 60:
            t_last = time.time()
            log(f"stream: {n_files} parquet members, market files {sizes['markets']}, trade files {sizes['trades']}, "
                f"{n_trade_rows / 1e6:.1f}M trades kept")
    flush()
    proc.wait()
    log(f"extraction done: {sizes}, {n_trade_rows} trades")
    assert mk_parts and n_trade_rows > 0, "no kalshi data found in archive"
    return pd.concat(mk_parts, ignore_index=True), n_trade_rows


HF = "https://huggingface.co/datasets/TrevorJS/kalshi-trades/resolve/main"
HF_FILES = [f"markets-{i:04d}.parquet" for i in range(4)] + [f"trades-{i:04d}.parquet" for i in range(16)]


def extract_hf():
    """s3.jbecker.dev is unreachable from Kaggle kernels (egress block). Fallback: TrevorJS/kalshi-trades on Hugging Face
    (CC-BY-4.0, built on Andrew Becker's Kalshi dump, 154.5M trades / 17.5M markets, Jun 2021 - Jan 2026)."""
    global RED
    from concurrent.futures import ThreadPoolExecutor
    base, free = pick_dir()
    RED = f"{base}/kalshi_red"
    shutil.rmtree(RED, ignore_errors=True)
    os.makedirs(RED)
    dl = f"{base}/hf"
    os.makedirs(dl, exist_ok=True)
    r = subprocess.run(f"curl -sSI -m 30 {HF}/markets-0000.parquet | head -1", shell=True, capture_output=True, text=True)
    log("HF probe:", (r.stdout + r.stderr).strip())
    if not any(k in r.stdout for k in ("200", "302", "307")):
        raise SystemExit("huggingface unreachable too")
    def get(f):
        try:
            pq.ParquetFile(f"{dl}/{f}")
            return f
        except Exception:
            pass
        for a in range(5):
            if subprocess.run(f"curl -L -sS --retry 5 --retry-all-errors -o {dl}/{f} {HF}/{f}", shell=True).returncode == 0:
                return f
        raise RuntimeError("download failed " + f)
    with ThreadPoolExecutor(6) as ex:
        for f in ex.map(get, HF_FILES):
            log("downloaded", f, f"{os.path.getsize(dl + '/' + f) / 1e6:.0f} MB")
    MK = ["ticker", "event_ticker", "market_type", "status", "last_price", "volume", "open_interest", "result", "created_time", "open_time", "close_time"]
    mk_parts = []
    for f in HF_FILES[:4]:
        t = pq.read_table(f"{dl}/{f}", columns=MK)
        t = t.filter(pc.is_in(t["result"], value_set=pa.array(["yes", "no"])))
        t = t.filter(pc.invert(pc.starts_with(t["ticker"], "KXMVE")))
        d_ = t.to_pandas()
        if MOD > 1:
            d_ = d_[pd.util.hash_pandas_object(d_["ticker"], index=False).values % MOD == 0]
        mk_parts.append(d_)
        log("markets", f, len(mk_parts[-1]))
    n_rows = 0
    for i, f in enumerate(HF_FILES[4:]):
        t = pq.read_table(f"{dl}/{f}", columns=["ticker", "count", "yes_price", "taker_side", "created_time"])
        t = t.filter(pc.invert(pc.starts_with(t["ticker"], "KXMVE")))
        ts = pc.divide(pc.cast(pc.cast(t["created_time"], pa.timestamp("us", tz="UTC")), pa.int64()), 1_000_000)
        r = pa.table({"ticker": t["ticker"], "ts": ts, "price": pc.cast(t["yes_price"], pa.int16()),
                      "cnt": pc.cast(t["count"], pa.int32()), "tyes": pc.cast(pc.equal(t["taker_side"], "yes"), pa.int8())})
        pq.write_table(r, f"{RED}/p{i:05d}.parquet", compression="zstd")
        n_rows += r.num_rows
        os.remove(f"{dl}/{f}")
        log("trades", f, r.num_rows)
    return pd.concat(mk_parts, ignore_index=True), n_rows


def synth():
    """Small synthetic stand-in with the same schemas (for smoke tests only)."""
    global RED
    rng = np.random.default_rng(0)
    RED = "/tmp/xm_smoke_red"
    shutil.rmtree(RED, ignore_errors=True)
    os.makedirs(RED)
    N = 6000
    t0 = pd.Timestamp("2024-01-01", tz="UTC")
    series = ["KXNBAGAME", "KXHIGHNY", "KXBTCD", "KXFED", "NFLGAME", "KXMVEFOO", "INXD"]
    rows, trs = [], []
    for i in range(N):
        s = series[i % len(series)]
        ev = f"{s}-{i // 3}"
        close = t0 + pd.Timedelta(hours=float(i) * 0.9 + 3)
        q = rng.beta(0.6, 0.6)
        y = rng.random() < (0.5 + 1.15 * (q - 0.5))  # longshot-biased price
        y = bool(np.clip(y, 0, 1))
        rows.append(dict(ticker=f"{ev}-{i}", event_ticker=ev, market_type="binary", title="x", status="finalized",
                         last_price=int(q * 100), volume=100, open_interest=1, result="yes" if y else "no",
                         created_time=close - pd.Timedelta(days=5), open_time=close - pd.Timedelta(days=4),
                         close_time=close, _fetched_at=close))
        k = rng.integers(5, 40)
        tt = close - pd.to_timedelta(rng.uniform(0, 4 * 86400, k), unit="s")
        p = np.clip(np.round(100 * np.clip(q + rng.normal(0, 0.05, k), 0.02, 0.98)), 1, 99)
        trs.append(pd.DataFrame(dict(ticker=rows[-1]["ticker"], ts=(tt.astype("int64") // 10**9).astype("int64"),
                                     price=p.astype("int16"), cnt=rng.integers(1, 50, k).astype("int32"),
                                     tyes=rng.integers(0, 2, k).astype("int8"))))
        if s == "KXMVEFOO":
            trs.pop()
    tr = pd.concat(trs)
    for j in range(0, len(tr), 50000):
        pq.write_table(pa.Table.from_pandas(tr.iloc[j:j + 50000], preserve_index=False), f"{RED}/p{j // 50000:05d}.parquet")
    return pd.DataFrame(rows), len(tr)


mk_raw, n_trades_kept = synth() if SMOKE else extract_hf()
log("raw market rows:", len(mk_raw))

# ---------------------------------------------------------------- 2. settled binary markets + categories
mk = mk_raw.copy()
for c in ["created_time", "open_time", "close_time"]:
    mk[c] = pd.to_datetime(mk[c], utc=True, errors="coerce")
mk = mk.drop_duplicates("ticker", keep="last")
n_all = len(mk)
mk = mk[mk["result"].isin(["yes", "no"])]
n_settled = len(mk)
mve = mk["ticker"].str.upper().str.startswith("KXMVE") | mk["event_ticker"].fillna("").str.upper().str.contains("MVE")
n_mve = int(mve.sum())
mk = mk[~mve]
if "market_type" in mk:
    mk = mk[mk["market_type"].fillna("binary") == "binary"]
mk = mk[mk["close_time"].notna()].copy()
mk["event_ticker"] = mk["event_ticker"].fillna(mk["ticker"]).replace("", np.nan).fillna(mk["ticker"])
mk["series"] = mk["event_ticker"].str.extract(r"^([A-Z0-9]+)", expand=False).fillna("independent")
mk["y"] = (mk["result"] == "yes").astype("int8")
mk["close_ts"] = ((mk["close_time"] - pd.Timestamp("1970-01-01", tz="UTC")) // pd.Timedelta(seconds=1)).astype("int64")
mk["open_ts"] = ((mk["open_time"] - pd.Timestamp("1970-01-01", tz="UTC")) // pd.Timedelta(seconds=1))
log(f"markets: all {n_all}, settled yes/no {n_settled}, multivariate dropped {n_mve}, kept binary {len(mk)}")

# category hierarchy from the dataset repo's own util (fallback: Other)
hier = {}
try:
    src = urllib.request.urlopen("https://raw.githubusercontent.com/Jon-Becker/prediction-market-analysis/main/src/analysis/kalshi/util/categories.py", timeout=30).read().decode()
    ns = {}
    exec(src, ns)
    for s in mk["series"].unique():
        hier[s] = ns["get_hierarchy"](s)[:2]
    log("category map from repo util OK")
except Exception as e:
    log("category util fetch failed, using Other:", e)
    for s in mk["series"].unique():
        hier[s] = ("Other", "Other")
mk["group"] = mk["series"].map(lambda s: hier[s][0])
mk["cat"] = mk["series"].map(lambda s: hier[s][1])
log("groups:", mk["group"].value_counts().head(15).to_dict())

# ---------------------------------------------------------------- price features from trades BEFORE each cutoff
con = duckdb.connect()
con.execute(f"PRAGMA memory_limit='{'4GB' if (SMOKE or LOCAL) else '22GB'}'; PRAGMA temp_directory='{RED}/_tmp';")
con.register("mk", mk[["ticker", "close_ts", "open_ts"]].assign(open_ts=lambda d: d["open_ts"].astype("float64")))
aggs = []
for tag, S in H:
    c = f"(t.ts < m.close_ts - {S})"
    w = f"(t.ts < m.close_ts - {S} AND t.ts >= m.close_ts - {S} - 86400)"
    aggs += [
        f"arg_max(t.price, t.ts) FILTER (WHERE {c}) AS p_last_{tag}",
        f"arg_max(t.price, t.ts) FILTER (WHERE t.ts < m.close_ts - {S} - 21600) AS p_prev6_{tag}",
        f"arg_max(t.price, t.ts) FILTER (WHERE t.ts < m.close_ts - {S} - 86400) AS p_prev24_{tag}",
        f"sum(t.price * t.cnt) FILTER (WHERE {w}) / nullif(sum(t.cnt) FILTER (WHERE {w}), 0) AS vwap24_{tag}",
        f"sum(t.price * t.cnt) FILTER (WHERE {c}) / nullif(sum(t.cnt) FILTER (WHERE {c}), 0) AS vwap_all_{tag}",
        f"stddev_pop(t.price) FILTER (WHERE {w}) AS std24_{tag}",
        f"count(*) FILTER (WHERE {c}) AS n_tr_{tag}",
        f"count(*) FILTER (WHERE {w}) AS n_tr24_{tag}",
        f"sum(t.cnt) FILTER (WHERE {c}) AS ct_{tag}",
        f"sum(t.cnt) FILTER (WHERE {w}) AS ct24_{tag}",
        f"sum(t.cnt * t.tyes) FILTER (WHERE {w}) / nullif(sum(t.cnt) FILTER (WHERE {w}), 0) AS yes_share24_{tag}",
        f"max(t.ts) FILTER (WHERE {c}) AS last_ts_{tag}",
    ]
aggs += ["min(t.ts) AS first_ts", "max(t.ts) AS last_trade_ts_all", "count(*) AS n_trades_all"]
q = f"SELECT t.ticker, {', '.join(aggs)} FROM read_parquet('{RED}/p*.parquet') t JOIN mk m ON t.ticker = m.ticker GROUP BY t.ticker"
log("running feature aggregation in DuckDB ...")
feat = con.execute(q).df()
feat = feat.astype({c: "float64" for c in feat.columns if c != "ticker"})
log("feature rows:", len(feat))
w = mk.merge(feat, on="ticker", how="inner")
w = w[w[[f"p_last_{t}" for t, _ in H]].notna().any(axis=1)].reset_index(drop=True)
log("settled binary markets with trades before a cutoff:", len(w))
for c in w.columns:
    if w[c].dtype == "float64" and c not in ("close_ts", "open_ts", "first_ts", "last_trade_ts_all") and not c.startswith("last_ts"):
        w[c] = w[c].astype("float32")

# compact reusable table (wide) as a kernel output
keep_cols = ["ticker", "event_ticker", "series", "group", "cat", "created_time", "open_time", "close_time", "volume",
             "open_interest", "result", "y", "first_ts", "last_trade_ts_all", "n_trades_all"] + [c for c in w.columns if re.search(r"_(24h|6h|1h)$", c)]
w[keep_cols].to_parquet(f"{OUT}/kalshi_settled_markets.parquet", compression="zstd", index=False)
log(f"saved settled table {os.path.getsize(OUT + '/kalshi_settled_markets.parquet') / 1e6:.0f} MB, {len(w)} rows")

# ---------------------------------------------------------------- 3. long table
top_series = w["series"].value_counts().head(300).index
SER = pd.CategoricalDtype(list(top_series) + ["_rare"])
GRP = pd.CategoricalDtype(sorted(w["group"].unique()))
CAT = pd.CategoricalDtype(sorted(w["cat"].unique()))
parts = []
for tag, S in H:
    d = w[w[f"p_last_{tag}"].notna()]
    cut = d["close_ts"].values - S
    p = (d[f"p_last_{tag}"].values / 100).clip(0.01, 0.99)
    o = pd.DataFrame({
        "ticker": d["ticker"].values, "event": d["event_ticker"].values, "y": d["y"].values,
        "close_ts": d["close_ts"].values, "h": np.float32(S / 3600), "price": p.astype("float32"),
        "vwap24": (d[f"vwap24_{tag}"].values / 100), "vwap_all": (d[f"vwap_all_{tag}"].values / 100),
        "mom6": p - d[f"p_prev6_{tag}"].values / 100, "mom24": p - d[f"p_prev24_{tag}"].values / 100,
        "std24": d[f"std24_{tag}"].values / 100,
        "n_tr": d[f"n_tr_{tag}"].values, "n_tr24": d[f"n_tr24_{tag}"].values,
        "ct": d[f"ct_{tag}"].values, "ct24": d[f"ct24_{tag}"].values,
        "yes_share24": d[f"yes_share24_{tag}"].values,
        "hrs_since_last": (cut - d[f"last_ts_{tag}"].values) / 3600,
        "lifetime_h": (cut - d["open_ts"].fillna(d["first_ts"]).values) / 3600,
        "close_hour": ((d["close_ts"].values // 3600) % 24), "close_dow": ((d["close_ts"].values // 86400 + 4) % 7),
        "group": d["group"].values, "cat": d["cat"].values, "series": d["series"].values,
    })
    parts.append(o)
L = pd.concat(parts, ignore_index=True)
del parts
L["vwap24"] = L["vwap24"].fillna(L["price"])
L["vwap_all"] = L["vwap_all"].fillna(L["price"])
L["price_vs_vwap"] = L["price"] - L["vwap24"]
L["mom6_missing"] = L["mom6"].isna().astype("int8")
L["mom6"] = L["mom6"].fillna(0)
L["mom24"] = L["mom24"].fillna(0)
L["std24"] = L["std24"].fillna(0)
L["yes_share24"] = L["yes_share24"].fillna(0.5)
for c in ["n_tr", "n_tr24", "ct", "ct24"]:
    L["raw_" + c] = L[c].fillna(0)
    L[c] = np.log1p(L[c].fillna(0))
L["hrs_since_last"] = np.log1p(L["hrs_since_last"].clip(lower=0).fillna(0))
L["lifetime_h"] = np.log1p(L["lifetime_h"].clip(lower=0).fillna(0))
L["logit_p"] = np.log(L["price"] / (1 - L["price"])).astype("float32")
L["series_c"] = pd.Categorical(np.where(L["series"].isin(top_series), L["series"], "_rare"), dtype=SER)
L["group_c"] = pd.Categorical(L["group"], dtype=GRP)
L["cat_c"] = pd.Categorical(L["cat"], dtype=CAT)
for c in L.select_dtypes("float64").columns:
    L[c] = L[c].astype("float32")
log("long table:", L.shape)

# time split on MARKET close time (older -> train, newest ~20% -> test) with a 2-day embargo, and every event that has any
# market on the newer side is removed from the older side (no same-event leakage)
t_test = np.quantile(w["close_ts"].values, 0.80)
EMB = 2 * 86400
test = L[L["close_ts"] >= t_test]
older = L[(L["close_ts"] < t_test - EMB) & ~L["event"].isin(set(test["event"]))]
t_val = np.quantile(older["close_ts"].values, 0.85)
val = older[older["close_ts"] >= t_val]
fit = older[(older["close_ts"] < t_val - EMB) & ~older["event"].isin(set(val["event"]))]
ts_fmt = lambda t: pd.to_datetime(int(t), unit="s").strftime("%Y-%m-%d")
SPLIT = {"fit_rows": len(fit), "val_rows": len(val), "test_rows": len(test),
         "fit_markets": int(fit.ticker.nunique()), "val_markets": int(val.ticker.nunique()), "test_markets": int(test.ticker.nunique()),
         "fit_start": ts_fmt(fit["close_ts"].min()), "fit_end": ts_fmt(fit["close_ts"].max()),
         "val_start": ts_fmt(val["close_ts"].min()), "val_end": ts_fmt(val["close_ts"].max()),
         "test_start": ts_fmt(test["close_ts"].min()), "test_end": ts_fmt(test["close_ts"].max())}
log("split:", SPLIT)

import xgboost as xgb
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

eps = 1e-4
lg = lambda p: np.log(np.clip(p, 1e-4, 1 - 1e-4) / (1 - np.clip(p, 1e-4, 1 - 1e-4)))
sig = lambda z: 1 / (1 + np.exp(-z))
brier = lambda y, p: float(np.mean((p - y) ** 2))
def logloss(y, p):
    p = np.clip(p, eps, 1 - eps)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))
rng = np.random.default_rng(1)

# ---- models
PRED = {}                      # name -> predictions on test, val
def put(name, pv, pt):
    PRED[name] = (np.asarray(pv, "float64"), np.asarray(pt, "float64"))
put("market", val["price"], test["price"])

def sub(df, n):
    return df if len(df) <= n else df.sample(n, random_state=0)

# global Platt (logit-linear) and isotonic
sf = sub(fit, 1_500_000)
lr = LogisticRegression(C=1e6, max_iter=300).fit(sf[["logit_p"]].values, sf["y"].values)
put("platt_global", lr.predict_proba(val[["logit_p"]].values)[:, 1], lr.predict_proba(test[["logit_p"]].values)[:, 1])
iso = IsotonicRegression(y_min=0.001, y_max=0.999, out_of_bounds="clip").fit(sf["price"].values, sf["y"].values)
put("isotonic_global", iso.predict(val["price"].values), iso.predict(test["price"].values))
log("global calibrators done")

# per-category calibration: Platt on logit(price) + horizon dummies per group, isotonic per group
def per_group(col, minrows=3000):
    pv, pt = put_arrays = np.array(PRED["platt_global"][0]), np.array(PRED["platt_global"][1])
    ivv, ivt = np.array(PRED["isotonic_global"][0]), np.array(PRED["isotonic_global"][1])
    gl_v, gl_t = pv.copy(), pt.copy()
    iso_v, iso_t = ivv.copy(), ivt.copy()
    for g, d in fit.groupby(col, observed=True):
        if len(d) < minrows or d["y"].nunique() < 2:
            continue
        d = sub(d, 1_000_000)
        mv = (val[col] == g).values
        mt = (test[col] == g).values
        X = lambda df: np.c_[df["logit_p"].values, (df["h"].values == 6), (df["h"].values == 1)]
        m = LogisticRegression(C=1e3, max_iter=300).fit(X(d), d["y"].values)
        if mv.any():
            gl_v[mv] = m.predict_proba(X(val[mv]))[:, 1]
        if mt.any():
            gl_t[mt] = m.predict_proba(X(test[mt]))[:, 1]
        im = IsotonicRegression(y_min=0.001, y_max=0.999, out_of_bounds="clip").fit(d["price"].values, d["y"].values)
        if mv.any():
            iso_v[mv] = im.predict(val.loc[mv, "price"].values)
        if mt.any():
            iso_t[mt] = im.predict(test.loc[mt, "price"].values)
    return (gl_v, gl_t), (iso_v, iso_t)
(pl_v, pl_t), (is_v, is_t) = per_group("cat")
put("platt_per_cat", pl_v, pl_t)
put("isotonic_per_cat", is_v, is_t)
log("per-category calibrators done")

# multi-feature logistic
LRF = ["logit_p", "mom6", "mom24", "price_vs_vwap", "std24", "n_tr", "ct", "hrs_since_last", "lifetime_h", "yes_share24", "mom6_missing"]
def lrX(df):
    X = df[LRF].astype("float64").copy()
    X["h6"] = (df["h"] == 6).astype("float64"); X["h1"] = (df["h"] == 1).astype("float64")
    G = pd.get_dummies(df["group"].astype(str)).reindex(columns=sorted(fit["group"].unique()), fill_value=0).astype("float64")
    for g in G.columns:
        X["g_" + g] = G[g].values
        X["lp_" + g] = G[g].values * df["logit_p"].values
    return X
sf2 = sub(fit, 1_000_000)
Xf = lrX(sf2)
mu, sd = Xf.mean(), Xf.std().replace(0, 1)
lrm = LogisticRegression(C=1.0, max_iter=400).fit(((Xf - mu) / sd).values, sf2["y"].values)
put("logit_multi", lrm.predict_proba(((lrX(val) - mu) / sd).values)[:, 1], lrm.predict_proba(((lrX(test) - mu) / sd).values)[:, 1])
log("multi logistic done")

# XGBoost: residual on logit(price) via base_margin
XF = ["price", "logit_p", "h", "vwap24", "vwap_all", "mom6", "mom24", "price_vs_vwap", "std24", "n_tr", "n_tr24", "ct", "ct24",
      "yes_share24", "hrs_since_last", "lifetime_h", "close_hour", "close_dow", "mom6_missing", "group_c", "cat_c", "series_c"]
def dm(df):
    return xgb.DMatrix(df[XF], label=df["y"].values, base_margin=lg(df["price"].values), enable_categorical=True)
HAVE_GPU = "GPU" in sh("nvidia-smi -L 2>&1")
log("have gpu:", HAVE_GPU)
dfit = sub(fit, 25_000_000 if HAVE_GPU else 3_000_000)
dtr, dva, dte = dm(dfit), dm(val), dm(test)
base = dict(objective="binary:logistic", eval_metric="logloss", eta=0.05 if HAVE_GPU else 0.15, max_depth=6, min_child_weight=50, subsample=0.8,
            colsample_bytree=0.8, reg_lambda=5.0, tree_method="hist", max_cat_to_onehot=8, max_bin=256)
def train_xgb(dev):
    p = dict(base, device=dev)
    return xgb.train(p, dtr, num_boost_round=300 if SMOKE else (3000 if HAVE_GPU else 500), evals=[(dtr, "fit"), (dva, "val")],
                     early_stopping_rounds=100, verbose_eval=100)
try:
    bst = train_xgb("cuda" if HAVE_GPU else "cpu")
except Exception as e:
    log("cuda failed, falling back to cpu:", repr(e)[:200])
    bst = train_xgb("cpu")
log("xgb best iteration", bst.best_iteration, "val logloss", bst.best_score)
put("xgboost", bst.predict(dva, iteration_range=(0, bst.best_iteration + 1)), bst.predict(dte, iteration_range=(0, bst.best_iteration + 1)))
bst.save_model(f"{OUT}/xmarket_xgb.json")
imp = pd.Series(bst.get_score(importance_type="gain")).sort_values(ascending=False)
imp.to_csv(f"{OUT}/xgb_feature_gain.csv", header=["gain"])
# XGBoost with NO market-price information except base margin removed -> shows how much is price itself (skip: not needed)

# ---------------------------------------------------------------- 4. evaluation
yv, yt = val["y"].values.astype(float), test["y"].values.astype(float)
M = {"split": SPLIT, "n_markets_all_rows": len(mk_raw), "n_settled_markets": n_settled, "n_multivariate_dropped": n_mve,
     "n_binary_kept": int(len(mk)), "n_with_trades": int(len(w)), "trades_kept_for_binary_nonmve": int(n_trades_kept)}
def ev_table(mask, models):
    rows = []
    for n in models:
        p = PRED[n][1][mask]
        rows.append({"model": n, "brier": brier(yt[mask], p), "logloss": logloss(yt[mask], p), "n": int(mask.sum())})
    return rows
models = list(PRED)
tst = test.reset_index(drop=True)
allm = np.ones(len(tst), bool)
M["overall"] = ev_table(allm, models)
cont = ((tst["price"] >= 0.05) & (tst["price"] <= 0.95)).values
M["contested_5_95"] = ev_table(cont, models)
M["by_horizon"] = {}
for tag, S in H:
    mk_ = (tst["h"].values == S / 3600)
    M["by_horizon"][tag] = {"all": ev_table(mk_, models), "contested": ev_table(mk_ & cont, models)}
byg = []
for lvl in ["group", "cat"]:
    for g, idx in tst.groupby(lvl).indices.items():
        if len(idx) < (200 if SMOKE else 3000):
            continue
        mask = np.zeros(len(tst), bool); mask[idx] = True
        mb = brier(yt[mask], PRED["market"][1][mask])
        mbc = brier(yt[mask & cont], PRED["market"][1][mask & cont]) if (mask & cont).sum() > 50 else np.nan
        for n in ["market", "platt_per_cat", "isotonic_per_cat", "logit_multi", "xgboost"]:
            p = PRED[n][1][mask]
            byg.append({"level": lvl, "name": g, "model": n, "n_rows": int(mask.sum()), "brier": brier(yt[mask], p), "logloss": logloss(yt[mask], p),
                        "brier_market": mb, "brier_gain_pct": 100 * (mb - brier(yt[mask], p)) / mb,
                        "contested_brier": brier(yt[mask & cont], p[cont[mask]]) if (mask & cont).sum() > 50 else np.nan,
                        "contested_brier_market": mbc})
pd.DataFrame(byg).to_csv(f"{OUT}/metrics_by_category.csv", index=False)
M["by_category_xgb_vs_market"] = [r for r in byg if r["model"] == "xgboost"]

# cluster bootstrap of the Brier gain of xgboost vs market (resample events)
def cluster_boot(df_idx_events, a, nboot=500):
    ev = pd.factorize(df_idx_events)[0]
    k = ev.max() + 1
    s = np.bincount(ev, weights=a, minlength=k); c = np.bincount(ev, minlength=k).astype(float)
    out = []
    for _ in range(nboot):
        j = rng.integers(0, k, k)
        out.append(s[j].sum() / c[j].sum())
    return float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))
for n in ["platt_per_cat", "isotonic_per_cat", "logit_multi", "xgboost"]:
    d = (PRED["market"][1] - yt) ** 2 - (PRED[n][1] - yt) ** 2
    M.setdefault("brier_gain_vs_market_ci", {})[n] = {"mean": float(d.mean()), "ci95": cluster_boot(tst["event"].values, d)}
    dc = d[cont]
    M["brier_gain_vs_market_ci"][n + "_contested"] = {"mean": float(dc.mean()), "ci95": cluster_boot(tst["event"].values[cont], dc)}

# reliability by price decile (h=24h, test) for the market and xgboost
rel = []
h24 = (tst["h"].values == 24)
bins = np.minimum((tst["price"].values * 10).astype(int), 9)
for name in ["market", "xgboost", "isotonic_per_cat"]:
    for b in range(10):
        mm = h24 & (bins == b)
        if mm.sum() == 0:
            continue
        rel.append({"model": name, "decile": b, "price_lo": b / 10, "n": int(mm.sum()), "mean_price": float(tst["price"].values[mm].mean()),
                    "mean_pred": float(PRED[name][1][mm].mean()), "win_rate": float(yt[mm].mean()),
                    "gap_win_minus_price_pp": float(100 * (yt[mm].mean() - tst["price"].values[mm].mean()))})
pd.DataFrame(rel).to_csv(f"{OUT}/reliability_deciles_h24.csv", index=False)
M["reliability_h24"] = rel

# favorite-longshot bias by category: realised win rate minus price in longshot / favorite zones + logit slope
def flb(df, key):
    rows = []
    d24 = df[df["h"] == 24]
    for g, d in d24.groupby(key, observed=True):
        if len(d) < (100 if SMOKE else 1500) or d["y"].nunique() < 2:
            continue
        p, y = d["price"].values, d["y"].values
        zl, zf, zm = p <= 0.15, p >= 0.85, (p > 0.15) & (p < 0.85)
        m = LogisticRegression(C=1e6, max_iter=200).fit(d[["logit_p"]].values, y)
        rows.append({"name": g, "n": len(d), "longshot_n": int(zl.sum()), "longshot_gap_pp": float(100 * (y[zl].mean() - p[zl].mean())) if zl.sum() > 30 else np.nan,
                     "mid_gap_pp": float(100 * (y[zm].mean() - p[zm].mean())) if zm.sum() > 30 else np.nan,
                     "favorite_n": int(zf.sum()), "favorite_gap_pp": float(100 * (y[zf].mean() - p[zf].mean())) if zf.sum() > 30 else np.nan,
                     "logit_slope": float(m.coef_[0][0]), "logit_intercept": float(m.intercept_[0])})
    return pd.DataFrame(rows, columns=["name","n","longshot_n","longshot_gap_pp","mid_gap_pp","favorite_n","favorite_gap_pp","logit_slope","logit_intercept"]).sort_values("n", ascending=False)
fl_te = flb(test, "group"); fl_te["period"] = "test"
fl_tr = flb(fit, "group"); fl_tr["period"] = "fit"
flc_te = flb(test, "cat"); flc_te["period"] = "test"
fl_all = pd.concat([fl_tr, fl_te, flc_te])
fl_all.to_csv(f"{OUT}/favorite_longshot_by_category.csv", index=False)
M["favorite_longshot_group_test"] = fl_te.to_dict("records")
M["favorite_longshot_group_fit"] = fl_tr.to_dict("records")
log("evaluation tables done")

# ---------------------------------------------------------------- paper strategy net of Kalshi taker fee
def fee_pc(P, C=10):
    """Kalshi taker fee ceil(0.07*C*P*(1-P)) in dollars, rounded UP to the cent, per contract at C contracts per order."""
    return np.ceil(0.07 * C * P * (1 - P) * 100 - 1e-9) / 100 / C
def strat(df, pred, thr, slip=0.0, elig=None):
    price, y = df["price"].values.astype(float), df["y"].values.astype(float)
    ok = (df["raw_n_tr"].values >= 5) & (df["raw_ct"].values >= 50) & (price >= 0.03) & (price <= 0.97)
    if elig is not None:
        ok &= elig
    edge_y, edge_n = pred - price, price - pred
    buy_y, buy_n = ok & (edge_y > thr), ok & (edge_n > thr)
    side_y = buy_y
    bet = buy_y | buy_n
    P = np.where(side_y, price, 1 - price)           # price of the contract we buy
    Pm = np.clip(P + slip, 0.01, 0.99)               # slippage: pay `slip` above last price
    win = np.where(side_y, y, 1 - y)
    fee = fee_pc(Pm)
    pnl = np.where(bet, win - Pm - fee, 0.0)
    gross = np.where(bet, win - Pm, 0.0)
    return bet, pnl, gross, Pm, win
def summarize(df, bet, pnl, gross, Pm, win, nboot=1000):
    n = int(bet.sum())
    if n == 0:
        return {"n_bets": 0}
    ev = pd.factorize(df["event"].values[bet])[0]
    k = ev.max() + 1
    sp = np.bincount(ev, weights=pnl[bet], minlength=k); sc = np.bincount(ev, weights=Pm[bet], minlength=k); sn = np.bincount(ev, minlength=k).astype(float)
    sw = np.bincount(ev, weights=win[bet], minlength=k)
    avg, roi, hit = [], [], []
    for _ in range(nboot):
        j = rng.integers(0, k, k)
        avg.append(sp[j].sum() / sn[j].sum()); roi.append(sp[j].sum() / sc[j].sum()); hit.append(sw[j].sum() / sn[j].sum())
    ci = lambda a: [float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5))]
    return {"n_bets": n, "hit_rate": float(win[bet].mean()), "hit_rate_ci95": ci(hit), "avg_price_paid": float(Pm[bet].mean()),
            "avg_pnl_cents_per_contract": float(100 * pnl[bet].mean()), "avg_pnl_ci95_cents": [100 * x for x in ci(avg)],
            "avg_gross_pnl_cents": float(100 * gross[bet].mean()), "roi_on_cost": float(pnl[bet].sum() / Pm[bet].sum()), "roi_ci95": ci(roi),
            "total_pnl_dollars_1_contract_each": float(pnl[bet].sum()), "p_roi_positive": float(np.mean(np.array(roi) > 0))}
STRAT = {}
THR = [0.01, 0.02, 0.03, 0.05, 0.08, 0.10, 0.15]
vsl = val.reset_index(drop=True)
for model in ["isotonic_per_cat", "platt_per_cat", "logit_multi", "xgboost"]:
    for hz in (24, 6):
        hv = (vsl["h"].values == hz); ht = (tst["h"].values == hz)
        # choose threshold on the VALIDATION period only (best total net P&L, >=200 bets)
        best, bestv = None, -1e18
        for thr in THR:
            b, pn, g, Pm, wn = strat(vsl, PRED[model][0], thr, elig=hv)
            if b.sum() >= (20 if SMOKE else 200) and pn.sum() > bestv:
                best, bestv = thr, pn.sum()
        rec = {"chosen_threshold_on_val": best, "grid": {}}
        for thr in THR:
            b, pn, g, Pm, wn = strat(tst, PRED[model][1], thr, elig=ht)
            rec["grid"][str(thr)] = summarize(tst, b, pn, g, Pm, wn, nboot=300)
        if best is not None:
            for slip, nm in [(0.0, "headline"), (0.01, "slip_1c")]:
                b, pn, g, Pm, wn = strat(tst, PRED[model][1], best, slip=slip, elig=ht)
                rec[nm] = summarize(tst, b, pn, g, Pm, wn)
            # per group at the chosen threshold
            b, pn, g, Pm, wn = strat(tst, PRED[model][1], best, elig=ht)
            pg = []
            for gname, idx in tst.groupby("group").indices.items():
                bm = np.zeros(len(tst), bool); bm[idx] = True; bm &= b
                if bm.sum() >= 50:
                    pg.append({"group": gname, "n_bets": int(bm.sum()), "hit_rate": float(wn[bm].mean()), "avg_pnl_cents": float(100 * pn[bm].mean()),
                               "roi": float(pn[bm].sum() / Pm[bm].sum())})
            rec["per_group"] = pg
        STRAT[f"{model}@{hz}h"] = rec
M["strategy"] = STRAT
# control: random bets with the same count on the same rows (should be ~ -fee)
json.dump(M, open(f"{OUT}/metrics.json", "w"), indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))
log("metrics.json written")

# headline print
ov = pd.DataFrame(M["overall"]).set_index("model")
print("\nOVERALL TEST (all rows):\n", ov)
print("\nCONTESTED 5-95c:\n", pd.DataFrame(M["contested_5_95"]).set_index("model"))
print("\nBrier gain vs market (cluster-bootstrap 95% CI):\n", json.dumps(M["brier_gain_vs_market_ci"], indent=1))
print("\nSTRATEGY (xgboost@24h):", json.dumps({k: v for k, v in STRAT["xgboost@24h"].items() if k != "grid"}, indent=1, default=str))

# sampled predictions for reuse
cols = ["ticker", "event", "h", "price", "y", "close_ts", "group", "cat"]
smp = tst[cols].copy()
for n in ["isotonic_per_cat", "logit_multi", "xgboost"]:
    smp["pred_" + n] = PRED[n][1].astype("float32")
smp.sample(min(len(smp), 500_000), random_state=0).to_parquet(f"{OUT}/test_predictions_sample.parquet", index=False)

# ---------------------------------------------------------------- W&B (offline)
try:
    import wandb
    run = wandb.init(project="kalshi-knows", name=f"xmarket-{time.strftime('%m%d-%H%M')}", mode="offline", dir=os.environ["WANDB_DIR"],
                     config={"split": SPLIT, "horizons": [t for t, _ in H], "xgb": base, "n_settled": n_settled, "n_kept": int(len(mk)), "n_with_trades": int(len(w))})
    for r in M["overall"]:
        wandb.summary[f"test_brier/{r['model']}"] = r["brier"]; wandb.summary[f"test_logloss/{r['model']}"] = r["logloss"]
    for r in M["contested_5_95"]:
        wandb.summary[f"contested_brier/{r['model']}"] = r["brier"]
    for k, v in M["brier_gain_vs_market_ci"].items():
        wandb.summary[f"brier_gain/{k}"] = v["mean"]
    for k, v in STRAT.items():
        if "headline" in v and v["headline"].get("n_bets"):
            wandb.summary[f"strategy/{k}/avg_pnl_cents"] = v["headline"]["avg_pnl_cents_per_contract"]
            wandb.summary[f"strategy/{k}/n_bets"] = v["headline"]["n_bets"]
    for fn in ["metrics_by_category.csv", "reliability_deciles_h24.csv", "favorite_longshot_by_category.csv", "xgb_feature_gain.csv"]:
        wandb.log({fn: wandb.Table(dataframe=pd.read_csv(f"{OUT}/{fn}"))})
    run.finish()
except Exception as e:
    log("wandb offline logging failed:", repr(e)[:300])
if not SMOKE and not LOCAL:
    for d in glob.glob("/kaggle/working/wandb/offline-run-*"):
        log("offline run dir:", d)
shutil.rmtree(RED, ignore_errors=True)
log(f"DONE in {time.time() - T0:.0f}s; outputs:", sh(f"ls -la {OUT}"))
