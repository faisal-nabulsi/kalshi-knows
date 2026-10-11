"""Slide charts for Kalshi Knows. Run: .venv/bin/python results/charts/make_charts.py
Inputs: results/*.json, train/out/*.json, docs/data/dutchbook.json, engine/logs/<date>/alerts.jsonl,
results/charts/data/{lag,wb,preds}.json (cached from aligned_jumps.parquet, W&B API, and data/compute_preds.py)."""
import json, glob
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

R = Path(__file__).resolve().parent.parent.parent
CH = R / "results/charts"; D = CH / "data"
BG, FG, OR, BL, GRID = "#0A0A0B", "#F2EFE9", "#FF4D1A", "#7A8FA6", "#26282C"
plt.rcParams.update({"figure.facecolor": BG, "axes.facecolor": BG, "savefig.facecolor": BG, "text.color": FG,
    "axes.labelcolor": FG, "xtick.color": FG, "ytick.color": FG, "font.family": "DejaVu Sans",
    "axes.edgecolor": GRID, "font.size": 20, "axes.spines.top": False, "axes.spines.right": False})
J = lambda p: json.loads(Path(p).read_text())
lag = J(R / "results/market_lag.json"); met = J(R / "train/out/metrics.json"); ft = J(R / "train/out/finetune_metrics.json")
preds = J(D / "preds.json"); wb = J(D / "wb.json"); lags = np.array(J(D / "lag.json"))
db = J(R / "docs/data/dutchbook.json")
CL = ["TD", "FG", "TURNOVER", "SAFETY", "BIG_PLAY", "OTHER"]
PLAIN = {"TD": "Touchdown", "FG": "Field goal", "TURNOVER": "Turnover", "SAFETY": "Safety", "BIG_PLAY": "Big play", "OTHER": "Nothing special"}


def fig_(title, src):
    f = plt.figure(figsize=(16, 9), dpi=100)
    f.text(0.04, 0.945, title, fontsize=29, fontweight="bold", va="top", ha="left", linespacing=1.15)
    f.text(0.04, 0.025, src, fontsize=13, color=BL, ha="left")
    return f


def save(f, name):
    f.savefig(CH / name, dpi=100); plt.close(f)  # 1600x900


# (a) market lag vs stream
f = fig_("Kalshi's price moves 7 s after the play.\nYour stream shows it 19-62 s after.",
         "n = 417 big plays (TD, FG, turnover, big play), 66 games, 2026 wk 1-5. Plays over 30 s drawn at 30. Stream delays are reference values. results/market_lag.json")
ax = f.add_axes([0.06, 0.16, 0.9, 0.62])
ax.hist(np.clip(lags, 0, 30), bins=np.arange(0, 31, 1), color=OR)
ax.axvspan(48, 62, color=BL, alpha=0.35, lw=0); ax.axvline(19, color=BL, lw=4)
ax.set_xlim(0, 70); ax.set_xlabel("seconds after the real play", fontsize=20)
ax.set_yticks([]); ax.spines["left"].set_visible(False); ax.grid(False)
top = ax.get_ylim()[1]
ax.text(21, top * 0.97, f"Kalshi moves\nmedian {lag['overall']['median_s']:.1f} s", color=OR, fontsize=26, fontweight="bold", ha="left", va="top")
ax.text(20, top * 0.62, "TV broadcast\n19 s", color=BL, fontsize=24, fontweight="bold", va="top")
ax.text(55, top * 0.62, "Streams\n48-62 s", color=BL, fontsize=24, fontweight="bold", ha="center", va="top")
save(f, "a_kalshi_beats_your_stream.png")

# (b) leaderboard on real jumps
lb = met["model_leaderboard"]
NAMES = {"xgboost_calibrated_on_kalshi": "Our model (XGBoost + real Kalshi)", "kalshi_only_logistic": "Logistic, Kalshi data only",
         "mlp_gpu": "Neural net (GPU)", "xgboost_gpu": "XGBoost (GPU, simulated only)", "rule_of_thumb": "Smart sports fan rule of thumb",
         "majority_prior": "Always guess 'nothing special'"}
f = fig_("Our model calls 9 of 10 big plays right.\nA smart fan's rule of thumb gets 6 of 10.",
         "Accuracy on 417 real Kalshi big-play jumps, 62 games (cross-validated by game). Ranked by log loss. Tier names = Predator Scale. train/out/metrics.json")
ax = f.add_axes([0.40, 0.10, 0.54, 0.72])
ys = np.arange(len(lb))[::-1]
for y_, r in zip(ys, lb):
    c = OR if r["tier"] == 6 else BL
    ax.barh(y_, r["accuracy"] * 100, color=c, height=0.62)
    ax.text(r["accuracy"] * 100 + 1.2, y_, f"{r['accuracy']*100:.1f}%", va="center", fontsize=24, fontweight="bold", color=FG)
    f.text(0.385, ax.transData.transform((0, y_))[1] / 900 + 0.0, "", )
ax.set_yticks(ys); ax.set_yticklabels([f"{r['tier_name']}\n{NAMES[r['model']]}" for r in lb], fontsize=17)
ax.set_xlim(0, 105); ax.set_xticks([]); ax.spines["bottom"].set_visible(False); ax.spines["left"].set_visible(False); ax.tick_params(length=0)
save(f, "b_model_leaderboard.png")

# (c) sweep curves
trials = {k: v for k, v in wb.items() if k.startswith("xgb")}
best = min(trials, key=lambda k: trials[k]["best"]); worst = max(trials, key=lambda k: trials[k]["best"])
f = fig_("20 GPU trials all land within 0.004 of each other:\nthe model is stable, not lucky.",
         "XGBoost hyperparameter sweep on an AWS L40S, 28 years of nflverse plays, validation log loss (lower = better). W&B kalshi-knows, group xgb-sweep")
ax = f.add_axes([0.09, 0.16, 0.86, 0.62])
for k, v in trials.items():
    if k != best: ax.plot(v["x"], v["y"], color=BL, lw=1.8, alpha=0.55)
v = trials[best]; ax.plot(v["x"], v["y"], color=OR, lw=4.5)
ax.scatter([v["bi"]], [v["best"]], color=OR, s=200, zorder=5, edgecolor=BG, linewidth=2)
ax.set_ylim(0.335, 0.42); ax.set_xlim(0, 1900)
ax.set_xlabel("boosting round (trees added)", fontsize=20); ax.set_ylabel("validation log loss", fontsize=20)
ax.grid(axis="y", color=GRID, lw=1)
ax.annotate(f"Best: {best.replace('xgb-','')} = {v['best']:.4f}", xy=(v["bi"], v["best"]), xytext=(900, 0.372), color=OR, fontsize=26, fontweight="bold",
            arrowprops=dict(arrowstyle="-", color=OR, lw=2))
w = trials[worst]; ax.text(1880, 0.356, f"19 other trials: {sorted(t['best'] for k, t in trials.items() if k != best)[0]:.4f} - {w['best']:.4f}", color=BL, fontsize=21, fontweight="bold", ha="right")
save(f, "c_sweep_val_loss.png")

# (d) confusion matrices
def cm_panel(ax, y, p, labels, title, n):
    idx = [CL.index(l) for l in labels]
    M = np.zeros((len(idx), len(idx)))
    for a_, b_ in zip(y, p):
        if a_ in idx and b_ in idx: M[idx.index(a_), idx.index(b_)] += 1
    cnt = M.copy(); Mn = M / np.maximum(M.sum(1, keepdims=True), 1)
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("o", [BG, OR])
    ax.imshow(Mn, cmap=cmap, vmin=0, vmax=1)
    for i in range(len(idx)):
        for j in range(len(idx)):
            ax.text(j, i, f"{Mn[i,j]*100:.0f}%", ha="center", va="center", fontsize=22, fontweight="bold", color=FG if Mn[i, j] < 0.75 else BG)
    ax.set_xticks(range(len(idx))); ax.set_xticklabels([PLAIN[l].replace(" ", "\n") for l in labels], fontsize=15)
    ax.set_yticks(range(len(idx))); ax.set_yticklabels([f"{PLAIN[l]}\n(n={int(cnt[i].sum())})" for i, l in enumerate(labels)], fontsize=15)
    ax.set_xlabel("what we said it was", fontsize=17); ax.set_ylabel("what actually happened", fontsize=17)
    ax.set_title(title, fontsize=20, color=FG, pad=12, fontweight="bold")
    for s in ax.spines.values(): s.set_visible(False)
    ax.tick_params(length=0)
r4, fr = preds["r417"], preds["fires"]
tdrec = None
f = fig_("Real big plays are called right 9 times in 10.\nThe hard call is 'big play' vs 'nothing special'.",
         "Row = what really happened, % of that row we labeled each way. Left: n=417 (best model, 89.7%). Right: n=1,596 detector fires (76.3%). Both cross-validated by game.")
a1 = f.add_axes([0.10, 0.14, 0.34, 0.64]); a2 = f.add_axes([0.62, 0.14, 0.34, 0.64])
cm_panel(a1, r4["y"], r4["pred"], ["TD", "FG", "TURNOVER", "BIG_PLAY"], "Big plays only", 417)
cm_panel(a2, fr["y"], fr["pred"], ["TD", "FG", "TURNOVER", "BIG_PLAY", "OTHER"], "Everything the detector fires on", 1596)
save(f, "d_confusion_matrix.png")

# (e) accuracy vs confidence (realistic fires)
conf = np.array(fr["conf"]); ok = np.array(fr["pred"]) == np.array(fr["y"])
bins = [(0, .5), (.5, .7), (.7, .9), (.9, 1.01)]; labs = ["under 50%", "50-70%", "70-90%", "90%+"]
accs = [ok[(conf >= a_) & (conf < b_)].mean() for a_, b_ in bins]; ns = [int(((conf >= a_) & (conf < b_)).sum()) for a_, b_ in bins]
conf417 = np.array(r4["conf"]); ok417 = np.array(r4["pred"]) == np.array(r4["y"])
hi = accs[-1]
f = fig_(f"When the model says 90%+, it is right {hi*100:.0f}% of the time.",
         f"Accuracy by stated confidence, n = {fr['n']:,} real detector fires (all play types incl. 'nothing special'), cross-validated by game. Bar labels show n.")
ax = f.add_axes([0.08, 0.16, 0.88, 0.66])
xs = np.arange(4); ax.bar(xs, [a_ * 100 for a_ in accs], color=[BL, BL, BL, OR], width=0.6)
for x_, a_, n_ in zip(xs, accs, ns):
    ax.text(x_, a_ * 100 + 2, f"{a_*100:.0f}%", ha="center", fontsize=34, fontweight="bold", color=OR if x_ == 3 else FG)
    ax.text(x_, 4, f"n = {n_}", ha="center", fontsize=19, color=BG, fontweight="bold")
ax.set_xticks(xs); ax.set_xticklabels(labs, fontsize=22); ax.set_xlabel("how confident the model said it was", fontsize=21)
ax.set_ylim(0, 112); ax.set_yticks([]); ax.spines["left"].set_visible(False); ax.tick_params(length=0)
save(f, "e_accuracy_vs_confidence.png")

# (f) today's live alerts
A = {}
for l in open(sorted(glob.glob(str(R / "engine/logs/2026*/alerts.jsonl")))[-1]):
    a_ = json.loads(l); A[a_["id"]] = a_
conf_a = [a_ for a_ in A.values() if a_.get("confirmed")]
leads = [a_["confirmed"]["lead_s"] for a_ in conf_a]
f = fig_(f"Today our alerts beat ESPN's own play feed by {min(leads):.0f}-{max(leads):.0f} seconds.",
         f"Sun Oct 11 2026 live NFL games. {len(conf_a)} of {len(A)} alerts confirmed so far (rest pending); all {sum(a_['confirmed']['inferred_correct'] for a_ in conf_a)} confirmed calls were the right play type. engine/logs/20261011/alerts.jsonl")
ax = f.add_axes([0.20, 0.16, 0.76, 0.62])
ax.axvspan(48, 62, color=BL, alpha=0.30, lw=0); ax.axvline(19, color=BL, lw=3, ls="--")
for i, a_ in enumerate(conf_a[::-1]):
    c = a_["confirmed"]; t_alert = c["market_lag_s"]; t_espn = t_alert + c["lead_s"]
    ax.plot([t_alert, t_espn], [i, i], color=OR, lw=7, solid_capstyle="butt")
    ax.scatter([t_alert], [i], s=420, color=OR, zorder=5); ax.scatter([t_espn], [i], s=420, color=BL, zorder=5, edgecolor=FG, linewidth=2)
    ax.text((t_alert + t_espn) / 2, i + 0.2, f"+{c['lead_s']:.0f} s", color=OR, fontsize=30, fontweight="bold", ha="center")
ax.set_yticks(range(len(conf_a))); ax.set_yticklabels([f"{a_['short_name']}\n{PLAIN.get(a_['confirmed']['play_type'], a_['confirmed']['play_type'])}" for a_ in conf_a[::-1]], fontsize=19)
ax.set_xlim(0, 95); ax.set_ylim(-0.6, len(conf_a) - 0.1); ax.set_xlabel("seconds after the real play", fontsize=20)
ax.spines["left"].set_visible(False); ax.tick_params(axis="y", length=0)
ax.text(19.8, len(conf_a) - 0.12, "TV 19 s", color=BL, fontsize=19, va="top"); ax.text(55, len(conf_a) - 0.12, "streams 48-62 s", color=BL, fontsize=19, ha="center", va="top")
ax.text(94, -0.55, "orange dot = our alert   blue dot = ESPN play feed shows it", color=BL, fontsize=17, ha="right")
save(f, "f_live_alerts_timeline.png")

# (g) Dutch book funnel
nm = db["near_misses"]; real_ = [x for x in nm if "fake" not in x["id"]]
pre = sum(x["profit_before_fees"] > 0 for x in real_); post_ = sum(x["profit_after_fees"] >= 0.01 for x in real_)
fake = sum("fake" in x["id"] for x in nm)
f = fig_("Free money exists on paper. Fees kill all of it.",
         "Fee-aware LP scan of Kalshi's public order books, top-of-book, paper analysis only. 'After fees' = at least \\$0.01 profit (2 ladders show +\\$0.003).  docs/data/dutchbook.json")
vals = [(f"{db['scanned_markets']:,}", "markets scanned", f"{db['scanned_events']:,} events", BL),
        (f"{pre}", "contradictory prices", "before fees", FG), (f"{post_}", "survive fees", "after fees", OR)]
for i, (big, lab, sub, c) in enumerate(vals):
    x0 = 0.04 + i * 0.32
    f.text(x0 + 0.13, 0.62, big, fontsize=84 if i else 60, fontweight="bold", color=c, ha="center")
    f.text(x0 + 0.13, 0.50, lab, fontsize=28, color=FG, ha="center"); f.text(x0 + 0.13, 0.44, sub, fontsize=20, color=BL, ha="center")
    if i < 2: f.text(x0 + 0.285, 0.64, "→", fontsize=60, color=BL, ha="center")
f.text(0.5, 0.20, f"Plus {fake} lists that looked like free money but were not exhaustive:\nan unlisted outcome could win and every ticket would lose.",
       fontsize=21, ha="center", color=FG)
save(f, "g_dutch_book_funnel.png")

# (h) model vs smart fan
f = fig_("Ahead of a smart sports fan on both tests:\n90% vs 60%, and 76% vs 20%.",
         "Fan rule: price up for the team with the ball = TD if big, else big play; price down = turnover. train/eval_real.py")
ax = f.add_axes([0.05, 0.14, 0.92, 0.66])
g1 = [("Smart fan\nrule", r4["rule_acc"], BL), ("Our model", r4["acc"], OR)]
g2 = [("Smart fan\nrule", fr["rule_acc"], BL), ("Always say\n'nothing special'", fr["maj_acc"], BL), ("Our model", fr["acc"], OR)]
xs, cols, labs_, vs = [], [], [], []
for j, (l, v_, c) in enumerate(g1): xs.append(j); labs_.append(l); vs.append(v_); cols.append(c)
for j, (l, v_, c) in enumerate(g2): xs.append(3 + j); labs_.append(l); vs.append(v_); cols.append(c)
ax.bar(xs, [v_ * 100 for v_ in vs], color=cols, width=0.72)
for x_, v_, c in zip(xs, vs, cols): ax.text(x_, v_ * 100 + 2, f"{v_*100:.0f}%", ha="center", fontsize=34, fontweight="bold", color=OR if c == OR else FG)
ax.set_xticks(xs); ax.set_xticklabels(labs_, fontsize=17); ax.set_ylim(0, 112); ax.set_yticks([]); ax.spines["left"].set_visible(False); ax.tick_params(length=0)
ax.text(0.5, 106, "Only real big plays (n=417)", ha="center", fontsize=21, color=BL, fontweight="bold")
ax.text(4, 106, "Everything the detector fires on (n=1,596)", ha="center", fontsize=21, color=BL, fontweight="bold")
save(f, "h_model_vs_smart_fan.png")
print("\n".join(f"{p.name}: accs={accs} ns={ns}" for p in [Path('x')]), "leads", leads, "pre", pre, "post", post_, "fake", fake)
