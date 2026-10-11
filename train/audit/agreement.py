"""Merge manual labels with the sample key and score OLD / NEW auto labels against them (overall, by class, live)."""
import sys
from pathlib import Path
import numpy as np, pandas as pd
A = Path(__file__).parent; ROOT = A.parents[1]
K = pd.read_csv(A / "sample_key.csv", dtype={"game_id": str, "play_id": str})
M = pd.concat([pd.read_csv(A / f"labels_part{i}.csv", dtype=str) for i in (1, 2, 3)]).fillna("")
M = M.merge(K, on="sid", how="left").rename(columns={"category": "auto_old"})
R = pd.read_parquet(ROOT / "pipeline/out/fires_relabeled.parquet")
M = M.merge(R[["fire_id", "category_new", "category7", "new_play_id", "carry_in"]], on="fire_id", how="left")
tag = M.subtags.str
stopish = tag.contains("missed_fg|blocked_punt|4th_down_stop")
P = pd.read_parquet(ROOT / "pipeline/out/audit_plays.parquet", columns=["play_id", "type_text"]).drop_duplicates("play_id")
M = M.merge(P.rename(columns={"play_id": "causal_play_id", "type_text": "causal_type"}), on="causal_play_id", how="left")
downs = (M.manual_category == "TURNOVER") & tag.contains("4th_down_stop") & M.causal_type.isin(
    ["Rush", "Pass Reception", "Pass Incompletion", "Sack"])                     # failed 4th down, not an INT/fumble
M["manual7"] = np.where((stopish & (M.manual_category == "OTHER")) | downs, "STOP", M.manual_category)
M.to_csv(A / "labels_manual.csv", index=False)


def rate(m, a, b):
    return f"{(m[a] != m[b]).mean():.3f} ({int((m[a] != m[b]).sum())}/{len(m)})"


if __name__ == "__main__":
    for nm, m in [("ALL", M), ("LIVE >=0.08", M[M.live]), ("high-confidence manual", M[M.confidence == "high"])]:
        print(f"{nm:24s} noise OLD {rate(m,'auto_old','manual_category')}  NEW {rate(m,'category_new','manual_category')}"
              f"  7cls NEW {rate(m,'category7','manual7')}")
    print("\nby auto-OLD class: noise OLD vs NEW (NEW scored on same rows)")
    for c, m in M.groupby("auto_old"):
        print(f"  {c:9s} n={len(m):3d} OLD {rate(m,'auto_old','manual_category')}  NEW {rate(m,'category_new','manual_category')}")
    print("\nby manual class (recall of auto):")
    for c, m in M.groupby("manual_category"):
        print(f"  {c:9s} n={len(m):3d} OLD-correct {(m.auto_old==c).mean():.2f}  NEW-correct {(m.category_new==c).mean():.2f}")
    print("\nOLD confusion (rows auto, cols manual)"); print(pd.crosstab(M.auto_old, M.manual_category))
    print("\nNEW confusion"); print(pd.crosstab(M.category_new, M.manual_category))
    print("\nsubtags among OLD errors:"); e = M[M.auto_old != M.manual_category]
    print(pd.Series("|".join(e.subtags).split("|")).value_counts().to_dict())
    print("subtags overall:", pd.Series("|".join(M.subtags).split("|")).value_counts().to_dict())
    print("anchor play == manual causal play: %.2f ; NEW play == manual causal: %.2f" % (
        (M.play_id == M.causal_play_id).mean(), (M.new_play_id == M.causal_play_id).mean()))
    print("manual7 counts", M.manual7.value_counts().to_dict())
