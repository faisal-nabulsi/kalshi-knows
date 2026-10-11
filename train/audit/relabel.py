"""Rule-based relabel of the stage-2 detector fires -> pipeline/out/fires_relabeled.parquet.
Rows/features are identical to train/finetune_real.build_rows(FIRE_TRAIN=0.05) (same order as train/out/stage2_matrix.npz);
only labels change. Fixes (evidence: train/audit/agreement.txt, eval_relabel.txt, eval_extra.txt):
  F1 turnover on downs: nfl_build_plays' rule never fires (its `not end.down==1` test is always false for a change of
     possession), so 0 of ~430 failed 4th downs were TURNOVER. Re-derived from the next scrimmage snap.
  F2 penalty-nullified gains ('No Play') are not BIG_PLAY.
  F3 re-anchor: the label comes from the play that caused THIS jump, not from the window's anchor play. Jump start js is
     the price extremum before the move (walked back if the move began before the window edge); ESPN wallclock lands
     ~6 s after js (median for TD/turnover windows), so candidates are plays with wallclock in [js+LO, js+HI]; take the
     highest-priority category whose beneficiary matches the move direction, else OTHER.
  F4 category7: STOP (missed/blocked FG, blocked punt, turnover on downs) split out as a 7th class.
"""
import sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).parent)); from common import *

LO, HI = -10_000, 20_000
PRI = ["TD", "SAFETY", "TURNOVER", "FG", "BIG_PLAY", "STOP_ONLY", "OTHER"]
NONPLAY = {"Official Timeout", "Timeout", "End Period", "Two-minute warning", "End of Game", "End of Half",
           "End of Regulation"}
SCRIM = {"Rush", "Pass Reception", "Pass Incompletion", "Sack", "Passing Touchdown", "Rushing Touchdown"}
SKIP_NEXT = NONPLAY | {"Penalty"}


def fixed_plays():
    P = plays_table().sort_values(["game_id", "seq"]).reset_index(drop=True)
    P["cat_fixed"] = P.category; P["benef"] = P.team; P["stop"] = False; P["downs"] = False
    noplay = P.text.str.contains(r"No Play", case=False, na=False)
    P.loc[noplay & (P.category == "BIG_PLAY"), "cat_fixed"] = "OTHER"                       # F2
    opp = np.where(P.posteam == P.home, P.away, P.home)
    for g, d in P.groupby("game_id", sort=False):                                             # F1
        idx = d.index.to_list()
        for k, i in enumerate(idx):
            a = P.loc[i]
            if a.type_text not in SCRIM or a.down != 4 or a.category != "OTHER" or not a.posteam or noplay[i]:
                continue
            for j in idx[k + 1:k + 6]:
                b = P.loc[j]
                if b.type_text in SKIP_NEXT or noplay[j]:
                    continue
                if b.type_text in SCRIM and b.posteam and b.posteam != a.posteam and b.down == 1:
                    P.loc[i, ["cat_fixed", "benef", "downs", "stop"]] = ["TURNOVER", b.posteam, True, True]
                break
    st = P.type_text.isin({"Field Goal Missed", "Blocked Field Goal", "Blocked Punt"})
    P.loc[st, "stop"] = True
    P.loc[st, "benef"] = opp[st.to_numpy()]                                                    # defense benefits
    P.loc[P.cat_fixed == "BIG_PLAY", "benef"] = P.posteam
    return P


def true_start(t, p, i_ext, up, max_back=15):
    """Walk back from the window-edge extremum while the price was already moving the same way (carry-in jumps);
    one flat 2 s bin is tolerated mid-move."""
    sgn = 1 if up else -1; j = i_ext
    while j > 1 and i_ext - j < max_back:
        s1 = sgn * (p[j] - p[j - 1]); s2 = sgn * (p[j - 1] - p[j - 2])
        if s1 > 0.004 or (abs(s1) <= 0.004 and s2 > 0.004):
            j -= 1
        else:
            break
    return j


def relabel(F=None, P=None, lo=LO, hi=HI, walkback=True):
    import finetune_real as fr
    F = fires() if F is None else F
    P = fixed_plays() if P is None else P
    W = fr.load_windows() if walkback else None
    Pg = {g: d[~d.type_text.isin(NONPLAY)].sort_values("wallclock_ms") for g, d in P.groupby("game_id")}
    out = []
    for r in F.itertuples():
        js = r.jump_start_ms; up = r.delta_home > 0; carry = False
        if walkback and r.t_start <= -28:
            w = W.iloc[r.win_idx]; t = np.asarray(w.path_t, float); p = pd.Series(np.asarray(w.path_p, float)).ffill().to_numpy()
            i_ext = int(np.searchsorted(t, r.t_start)); j = true_start(t, p, i_ext, up)
            if j < i_ext:
                js = r.wallclock_ms + int(t[j] * 1000); carry = True
        g = Pg.get(r.game_id)
        c = g[(g.wallclock_ms >= js + lo) & (g.wallclock_ms <= js + hi)]
        home = g.home.iloc[0]
        ok = c[(c.benef == home) == up]
        best, pid, stop = "OTHER", None, False
        for cat in ["TD", "SAFETY", "TURNOVER", "FG", "BIG_PLAY"]:
            h = ok[ok.cat_fixed == cat]
            if len(h):
                best = cat; pid = h.iloc[0].play_id; stop = bool(h.iloc[0].stop); break
        if best == "OTHER":
            s = ok[ok.stop]
            if len(s):
                pid, stop = s.iloc[0].play_id, True
            elif len(c):
                pid = c.iloc[(c.wallclock_ms - (js + 6000)).abs().argmin()].play_id
        near = g[(g.wallclock_ms >= js - 30000) & (g.wallclock_ms <= js + 40000)]
        out.append(dict(category_new=best, category7=("STOP" if stop else best), new_play_id=pid, js_new=js,
                        carry_in=carry, no_play_nearby=len(near) == 0, anchor_changed=(pid != r.play_id)))
    return pd.concat([F.reset_index(drop=True), pd.DataFrame(out)], axis=1)


if __name__ == "__main__":
    F = fires()
    F["fire_id"] = F.season.astype(str) + "_" + F.game_id + "_" + F.win_idx.astype(str)
    R = relabel(F)
    R = R.rename(columns={"category": "category_old"})
    R["jump_id"] = 0
    o = R.sort_values(["game_id", "detect_ms"])
    o["jump_id"] = (o.game_id.ne(o.game_id.shift()) | (o.detect_ms.diff() > 8000)).cumsum()
    R["jump_id"] = o.jump_id.sort_index()
    # one row per physical jump (for the dedup evaluation): prefer the fire whose window anchor IS the causal play
    R["rep"] = False
    pref = R.assign(_k=(~R.anchor_changed).astype(int)).sort_values(["jump_id", "_k", "detect_ms"], ascending=[True, False, True])
    R.loc[pref.drop_duplicates("jump_id").index, "rep"] = True
    import finetune_real as fr
    _, Z, _ = fr.sim_logprobs(R)                                   # stage-1 log-probs, as in stage2_matrix.npz
    for k, c in enumerate(fr.CLASSES):
        R[f"sim_{c}"] = Z[:, k]
    R.to_parquet(OUTD / "fires_relabeled.parquet")
    print(pd.crosstab(R.category_old, R.category_new, margins=True))
    print("category7", R.category7.value_counts().to_dict())
    L = R[R.delta_home.abs() >= 0.08]
    print("label changed: all %.3f live %.3f | carry-in %d | no play nearby %d | physical jumps %d" % (
        (R.category_old != R.category_new).mean(), (L.category_old != L.category_new).mean(), R.carry_in.sum(),
        R.no_play_nearby.sum(), R.rep.sum()))
