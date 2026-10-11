"""Shared helpers for the label audit: full ESPN play tables (both seasons) and detector fires with jump timing.
Fires are produced exactly as train/finetune_real.build_rows (same detector, same features, same order)."""
import os, sys, json
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "train")); sys.path.insert(0, str(ROOT / "pipeline"))
OUTD = ROOT / "pipeline/out"
PLAYS = OUTD / "audit_plays.parquet"
FIRES = OUTD / "audit_fires.parquet"


def plays_table():
    """Every ESPN play (all categories) for every game in both window files, built with pipeline/nfl_build_plays rules."""
    if PLAYS.exists():
        return pd.read_parquet(PLAYS)
    import nfl_build_plays as bp
    out = []
    for stem, sub in [("real_windows", "."), ("real_windows_2025", "_e25")]:
        gids = pd.read_parquet(OUTD / f"{stem}.parquet", columns=["game_id"]).game_id.astype(str).unique()
        bp.D = str(OUTD / sub) if sub != "." else str(OUTD)
        for g in gids:
            try:
                out += bp.build_game(g)
            except Exception as e:
                print("skip", g, e)
    df = pd.DataFrame(out).dropna(subset=["wallclock_ms"])
    df["wallclock_ms"] = df.wallclock_ms.astype("int64"); df["game_id"] = df.game_id.astype(str)
    df["play_id"] = df.play_id.astype(str)
    df = df.drop_duplicates(["game_id", "play_id"])
    df.to_parquet(PLAYS)
    return df


def fires(thresh=0.05):
    """One row per detector fire (same rows/features as build_rows) + jump timing in absolute ms."""
    if FIRES.exists() and thresh == 0.05:
        return pd.read_parquet(FIRES)
    import finetune_real as fr
    df = fr.load_windows()
    W = int(fr.WINDOW_S / fr.STEP)
    meta = []
    keep = []
    for k, r in enumerate(df.itertuples(index=False)):
        t = np.asarray(r.path_t, float); p = pd.Series(np.asarray(r.path_p, float)).ffill().to_numpy()
        if np.isnan(p).all():
            continue
        hit = fr.detect(t, p, thresh)
        if hit is None:
            continue
        i_f = hit[0]; i = i_f - fr.HOLD_BINS - fr.CALL_DELAY_BINS
        seg = p[i - W:i + 1]
        i_ext = i - W + int(np.nanargmin(seg) if p[i] >= p[i - W] else np.nanargmax(seg))
        # first bin after the extremum where >=50% of the move is done
        half = p[i_ext] + 0.5 * (p[i] - p[i_ext])
        j = i_ext
        while j < i and (p[j] - half) * np.sign(p[i] - p[i_ext]) < 0:
            j += 1
        wc = int(r.wallclock_ms)
        meta.append(dict(win_idx=k, play_id=str(r.play_id), wallclock_ms=wc, window_kind=r.window_kind,
                         text=r.text, t_detect=float(t[i]), t_start=float(t[i_ext]), t_half=float(t[j]),
                         jump_start_ms=wc + int(t[i_ext] * 1000), jump_half_ms=wc + int(t[j] * 1000),
                         detect_ms=wc + int(t[i] * 1000), call_ms=wc + int(t[i_f] * 1000)))
        keep.append(k)
    rows = fr.build_rows(df, thresh)
    assert len(rows) == len(meta), (len(rows), len(meta))
    m = pd.DataFrame(meta)
    rows = pd.concat([rows.reset_index(drop=True), m], axis=1)
    rows["game_id"] = rows.game_id.astype(str)
    if thresh == 0.05:
        rows.drop(columns=["crop"]).to_parquet(FIRES)
    return rows


if __name__ == "__main__":
    P = plays_table(); print("plays", P.shape, P.game_id.nunique())
    F = fires(); print("fires", F.shape, F.category.value_counts().to_dict())
