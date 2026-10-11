"""Reads every number for the video from the repo at render time -> build/data.json"""
import json, os, re, datetime, zoneinfo
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
J = lambda p: json.load(open(os.path.join(R, p)))
D = {}
# --- stream delay ladder (Super Bowl LX, Stats Perform), parsed from research/BRIEF.md
lad = [("ANTENNA", 19), ("CABLE", 38), ("PEACOCK", 48), ("YOUTUBE TV", 53), ("NFL+", 62)]
try:
    t = open(os.path.join(R, "research/BRIEF.md")).read()
    m = re.search(r"antenna about (\d+) s, cable (\d+), Peacock (\d+), YouTube TV (\d+).*?NFL\+ (\d+)", t)
    if m: lad = list(zip(["ANTENNA", "CABLE", "PEACOCK", "YOUTUBE TV", "NFL+"], map(int, m.groups())))
except Exception as e: print("ladder fallback", e)
D["ladder"] = lad
ml = J("docs/data/results.json")["market_lag"]
D["market_median"] = round(ml["median_s"], 1); D["market_n"] = ml["n_plays"]
# --- hero alert
d = {}
day = os.environ.get("VIDEO_DAY", "20261011")
logs = os.path.join(R, "engine/logs", day)
for l in open(os.path.join(logs, "alerts.jsonl")):
    r = json.loads(l); d[r["id"]] = r
want = os.environ.get("HERO_ID", "a_5")
if want not in d: want = max((k for k, r in d.items() if r.get("confirmed") and "sure" in r["headline"]), key=lambda k: d[k]["confirmed"]["lead_s"])
a = d[want]; c = a["confirmed"]
tz = zoneinfo.ZoneInfo("America/Los_Angeles")
at = datetime.datetime.fromtimestamp(a["ts_ms"] / 1000, tz)
D["hero"] = dict(id=want, headline=a["headline"], short=a["short_name"], away=a["away"], home=a["home"], period=a["period"], clock=a["clock"],
    play_text=c["play_text"].strip(), lead_s=c["lead_s"], alert_lag_s=c["market_lag_s"],
    espn_after_s=round((c["espn_seen_ms"] - c["espn_wallclock_ms"]) / 1000, 1),
    price_start_s=round((a["jump_started_ms"] - c["espn_wallclock_ms"]) / 1000, 1),
    time=at.strftime("%-I:%M"), date=at.strftime("%A, %B %-d"), p_before=a["p_before"], p_after=a["p_after"], team=a["team"],
    wall=c["espn_wallclock_ms"], gid=a["game_id"])
gid = a["game_id"]; w = c["espn_wallclock_ms"]
D["series"] = [[(q["ts_ms"] - w) / 1000, q["p_home"]] for q in map(json.loads, open(os.path.join(logs, "quotes.jsonl")))
               if q["game_id"] == gid and w - 40000 < q["ts_ms"] < w + 100000]
st = None
for l in open(os.path.join(logs, "espn.jsonl")):
    q = json.loads(l)
    if q["game_id"] == gid and q["ts_ms"] < w: st = q
D["state"] = {k: st[k] for k in ("home_score", "away_score", "situation", "possession", "period", "clock")} if st else {}
# --- alerts tally today
D["today"] = dict(n=len(d), confirmed=sum(1 for r in d.values() if r.get("confirmed")),
    right=sum(1 for r in d.values() if r.get("confirmed") and r["confirmed"].get("inferred_correct")))
# --- training facts
fm = J("train/out/finetune_metrics.json")
D["n_real"] = fm["n_fires"]
try: D["train_rows"] = J("train/out/metrics.json")["train_rows"]
except Exception: D["train_rows"] = 244434
cb = J("train/out/claude_bench.json")
D["claude"] = dict(n=cb["n"], gap_ci=cb["gap_ci"], rows=cb["results"])
# --- honest line: today_test > relabeled temporal_live > finetune temporal
honest = None
prereg = None
p = os.path.join(R, "results/today_test.json")
if os.path.exists(p):
    try:
        t = json.load(open(p))["all_fires"]; nc = t["named_calls"]
        prereg = dict(named=nc, right=round(t["named_precision"] * nc), n_fires=t["n_fires"])
    except Exception as e: print("today_test unreadable", e)
if not honest:
    try:
        t = J("train/out/relabeled_metrics.json")["temporal_live"]
        honest = dict(src="relabeled", acc=t["accuracy"], base=t["always_other"], n=t["n"], label="2026 games it never saw", games=t.get("games"))
    except Exception:
        t = fm["temporal"]["live_subset"]; honest = dict(src="finetune", acc=t["accuracy"], base=None, n=t["n"], label="2026 games it never saw")
D["honest"] = honest; D["prereg"] = prereg
os.makedirs(os.path.join(os.path.dirname(__file__), "build"), exist_ok=True)
json.dump(D, open(os.environ.get("DATA_OUT", os.path.join(os.path.dirname(os.path.abspath(__file__)), "build/data.json")), "w"), indent=1)
print(json.dumps({k: D[k] for k in ("hero", "today", "honest", "market_median", "n_real")}, indent=1))
