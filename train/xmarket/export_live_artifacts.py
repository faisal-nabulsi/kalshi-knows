"""Export the cross-market Picks XGBoost for live scoring, and prove the live encoding matches training.

Rebuilds the categorical dtypes (group / cat / top-300 series) exactly as kaggle/xmarket/train_xmarket.py did,
rebuilds the long feature table from the saved settled-markets parquet the same way, re-predicts the rows in
test_predictions_sample.parquet and compares with the predictions saved at training time.

Writes engine/model/xmarket_xgb.json (copy of the trained model) and engine/model/xmarket_meta.json.
Usage: .venv/bin/python train/xmarket/export_live_artifacts.py
"""
import json, shutil, time
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / "kaggle/xmarket/out_local"
DST = ROOT / "engine/model"
H = [("24h", 86400), ("6h", 21600), ("1h", 3600)]
XF = ["price", "logit_p", "h", "vwap24", "vwap_all", "mom6", "mom24", "price_vs_vwap", "std24", "n_tr", "n_tr24", "ct", "ct24",
      "yes_share24", "hrs_since_last", "lifetime_h", "close_hour", "close_dow", "mom6_missing", "group_c", "cat_c", "series_c"]
BEST_ITER = 98


def lg(p):
    return np.log(np.clip(p, 1e-4, 1 - 1e-4) / (1 - np.clip(p, 1e-4, 1 - 1e-4)))


def epoch_s(col):
    return ((col - pd.Timestamp("1970-01-01", tz="UTC")) // pd.Timedelta(seconds=1))


def long_table(w, SER, GRP, CAT, top_series):
    """Same construction as train_xmarket.py section 3 (one row per market x horizon)."""
    parts = []
    for tag, S in H:
        d = w[w[f"p_last_{tag}"].notna()]
        cut = d["close_ts"].values - S
        p = (d[f"p_last_{tag}"].values / 100).clip(0.01, 0.99)
        parts.append(pd.DataFrame({
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
        }))
    L = pd.concat(parts, ignore_index=True)
    L["vwap24"] = L["vwap24"].fillna(L["price"])
    L["vwap_all"] = L["vwap_all"].fillna(L["price"])
    L["price_vs_vwap"] = L["price"] - L["vwap24"]
    L["mom6_missing"] = L["mom6"].isna().astype("int8")
    L["mom6"] = L["mom6"].fillna(0)
    L["mom24"] = L["mom24"].fillna(0)
    L["std24"] = L["std24"].fillna(0)
    L["yes_share24"] = L["yes_share24"].fillna(0.5)
    for c in ["n_tr", "n_tr24", "ct", "ct24"]:
        L[c] = np.log1p(L[c].fillna(0))
    L["hrs_since_last"] = np.log1p(L["hrs_since_last"].clip(lower=0).fillna(0))
    L["lifetime_h"] = np.log1p(L["lifetime_h"].clip(lower=0).fillna(0))
    L["logit_p"] = np.log(L["price"] / (1 - L["price"])).astype("float32")
    L["series_c"] = pd.Categorical(np.where(L["series"].isin(top_series), L["series"], "_rare"), dtype=SER)
    L["group_c"] = pd.Categorical(L["group"], dtype=GRP)
    L["cat_c"] = pd.Categorical(L["cat"], dtype=CAT)
    for c in L.select_dtypes("float64").columns:
        L[c] = L[c].astype("float32")
    return L


def main():
    w = pd.read_parquet(ART / "kalshi_settled_markets.parquet")
    w["close_ts"] = epoch_s(w["close_time"]).astype("int64")
    w["open_ts"] = epoch_s(w["open_time"]).astype("float64")          # NaN when open_time is missing (as in training)
    # Training ran value_counts() on a pyarrow-string column, which breaks count ties by first appearance.
    # object-dtype value_counts() orders ties differently and scrambles 36 series codes, so sort explicitly.
    vc = w["series"].value_counts()
    first = {s: i for i, s in enumerate(pd.unique(w["series"]))}
    top_series = pd.Index(sorted(vc.index, key=lambda s: (-vc[s], first[s]))[:300])
    SER = pd.CategoricalDtype(list(top_series) + ["_rare"])
    GRP = pd.CategoricalDtype(sorted(w["group"].unique()))
    CAT = pd.CategoricalDtype(sorted(w["cat"].unique()))

    model = json.loads((ART / "xmarket_xgb.json").read_text())
    seg = model["learner"]["gradient_booster"]["model"]["cats"]["feature_segments"]
    sizes = {"group": seg[20] - seg[19], "cat": seg[21] - seg[20], "series": seg[22] - seg[21]}
    ours = {"group": len(GRP.categories), "cat": len(CAT.categories), "series": len(SER.categories)}
    print("category counts model:", sizes, "rebuilt:", ours)
    assert sizes == ours, "category counts differ from the trained model"
    assert model["learner"]["feature_names"] == XF

    L = long_table(w, SER, GRP, CAT, top_series)
    smp = pd.read_parquet(ART / "test_predictions_sample.parquet", columns=["ticker", "h", "price", "pred_xgboost"])
    m = smp.merge(L, on=["ticker", "h"], how="inner", suffixes=("_saved", ""))
    bst = xgb.Booster(); bst.load_model(str(ART / "xmarket_xgb.json"))
    dm = xgb.DMatrix(m[XF], base_margin=lg(m["price"].values), enable_categorical=True)
    pred = bst.predict(dm, iteration_range=(0, BEST_ITER + 1))
    diff = np.abs(pred - m["pred_xgboost"].values)
    ver = {"n_sample_rows": int(len(smp)), "n_compared": int(len(m)), "max_abs_diff": float(diff.max()),
           "median_abs_diff": float(np.median(diff)), "p99_abs_diff": float(np.quantile(diff, 0.99)),
           "corr": float(np.corrcoef(pred, m["pred_xgboost"].values)[0, 1]),
           "price_max_abs_diff": float(np.abs(m["price_saved"].values - m["price"].values).max()),
           "rows_rare_series": int((m["series_c"] == "_rare").sum()),
           "checked": time.strftime("%Y-%m-%d %H:%M %Z")}
    print("verify:", json.dumps(ver, indent=1))
    if ver["max_abs_diff"] >= 1e-4:
        bad = m.assign(pred=pred, diff=diff).sort_values("diff", ascending=False).head(10)
        print(bad[["ticker", "h", "series", "series_c", "group", "cat", "price", "pred", "pred_xgboost", "diff"]].to_string())

    smap = w.drop_duplicates("series").set_index("series")[["group", "cat"]]
    meta = {
        "features": XF,
        "group_cats": [str(c) for c in GRP.categories], "cat_cats": [str(c) for c in CAT.categories],
        "series_cats": [str(c) for c in SER.categories],
        "series_map": {s: [g, c] for s, g, c in zip(smap.index, smap["group"], smap["cat"])},
        "best_iteration": BEST_ITER,
        "horizons": {"24h": {"h": 24, "threshold": 0.08}, "6h": {"h": 6, "threshold": 0.05}},
        "base_margin": "logit(clip(price, 1e-4, 1-1e-4)); price = last trade before the cutoff, clipped to [0.01, 0.99]",
        "trained": ("kaggle/xmarket/train_xmarket.py (XM_LOCAL=1, Mac CPU), 351,244 settled Kalshi markets from the "
                    "TrevorJS/kalshi-trades mirror; fit 2021-07..2025-12-11, val 2025-12-13..2026-01-03 (early stopping), "
                    "test 2026-01-05..2026-01-30"),
        "verify": ver,
        "live_notes": [
            "close_ts in training is the ACTUAL close of a settled market. Markets with can_close_early (sports games) close "
            "right after the event, but an open market's close_time is the latest expiration (days later). Live: use "
            "expected_expiration_time when can_close_early, else close_time.",
            "h only took the values 24, 6 and 1 in training: score live markets near those horizons and pass the snapped value.",
            "price = last TRADE price (not a quote); n_tr/ct/vwap_all use every trade since the market opened, so paginate "
            "/markets/trades (cursor) instead of stopping at 1,000 trades.",
            "series not in series_cats -> '_rare'; series not in series_map -> engine/vendor/jb_categories.get_hierarchy(series)[:2] "
            "(it reproduces series_map exactly); a category not in cat_cats -> missing (NaN).",
            "close_hour = (close_ts // 3600) % 24 and close_dow = (close_ts // 86400 + 4) % 7, both UTC.",
        ],
    }
    DST.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ART / "xmarket_xgb.json", DST / "xmarket_xgb.json")
    (DST / "xmarket_meta.json").write_text(json.dumps(meta, indent=1))
    print("wrote", DST / "xmarket_xgb.json", DST / "xmarket_meta.json", f"({len(meta['series_map'])} series in map)")


if __name__ == "__main__":
    main()
