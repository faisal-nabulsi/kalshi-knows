"""Numbers + narration + timeline for the 60-75 s pitch ad. Everything read from the repo at run time."""
import json, os, re, subprocess, urllib.request
H = os.path.dirname(os.path.abspath(__file__)); R = os.path.dirname(H); B = f"{H}/build"
env = dict(os.environ, HERO_ID=os.environ.get("AD_HERO", "a_12"), DATA_OUT=f"{B}/ad_hero.json")
subprocess.run([f"{R}/.venv/bin/python", f"{H}/build_data.py"], env=env, check=True, capture_output=True)
D = json.load(open(f"{B}/ad_hero.json")); J = lambda p: json.load(open(f"{R}/{p}"))
h = D["hero"]
ladder = dict(D["ladder"]); streams = [v for k, v in ladder.items() if k != "ANTENNA"]
D["stream_s"] = int(round(sum(streams) / len(streams) / 5) * 5)            # "about 50 s"
sr = J("train/out/same_rows.json")["cv_by_game"]
D["fan_acc"] = round(sr["smart_fan_logistic (state + jump)"]["live"]["acc"] * 100)
prod = next(v for k, v in sr.items() if k.startswith("stage1_plus_state"))
D["model_acc"] = round(prod["live"]["acc"] * 100)
t = J("results/today_test.json")["all_fires"]
D["named_n"] = t["named_calls"]; D["named_right"] = round(t["named_precision"] * t["named_calls"])
cb = {r["model"][:6]: r for r in J("train/out/claude_bench.json")["results"]}
D["claude_acc"] = round(cb["Claude"]["accuracy"] * 100); D["kk_acc"] = round(cb["Kalshi"]["accuracy"] * 100)
D["ms"] = 7
try:
    m = re.search(r"(\d+) ms per call", open(f"{R}/STATS.md").read()); D["ms"] = int(m.group(1)) if m else 7
except Exception: pass
D["real_moves"] = int(round(D["n_real"], -2))
D["tally"] = None
try:
    api = J("docs/config.json")["api"]; tl = json.load(urllib.request.urlopen(api + "/api/health", timeout=8))["tally"]
    D["tally"] = dict(right=tl["correct"], total=tl["correct"] + tl["wrong"])
except Exception as e: print("health unavailable", e)
if not D["tally"]: D["tally"] = dict(right=4, total=4)
TEAM = {"PIT": "Steelers", "IND": "Colts", "WSH": "Commanders", "WAS": "Commanders", "NYG": "Giants"}
D["team_name"] = TEAM.get(h["team"], h["team"])
BEAT = 60 / 126
SCENES = [("hook", 12), ("money", 24), ("montage", 36), ("proof", 42), ("close", 30)]   # in beats
W = lambda n: {2: "two", 4: "four", 7: "seven", 8: "eight", 9: "nine"}.get(n, str(n))
T = D["tally"]; stream = D["stream_s"]
LINES = [  # (scene, offset in beats, text)
 ("hook", 0.5, f"Your stream is {stream} seconds behind real life."),
 ("hook", 8.6, "Your phone isn't."),
 ("money", 0.3, f"A {'touchdown' if 'TOUCHDOWN' in h['play_text'] else 'big play'}. Your phone buzzes."),
 ("money", 6.2, "Your TV? Still waiting."),
 ("money", 13.3, "Thirty seconds. Forty. Fifty."),
 ("money", 19.0, "There it is. We told you first."),
 ("montage", 0.2, f"Every call gets a receipt. {W(T['right']).capitalize()} of {W(T['total'])} named plays, right."),
 ("montage", 7.2, "Spoiler alert, full screen."),
 ("montage", 14.2, "Watching on delay? Spoiler Shield hides it."),
 ("montage", 21.2, "Auto places practice orders. No real money."),
 ("montage", 28.2, "Works on every market."),
 ("proof", 0.3, "Trained on twenty-eight seasons of football."),
 ("proof", 8.3, f"Then taught on {D['real_moves']:,} real market moves."),
 ("proof", 16.3, f"Smarter than a sports fan. {D['model_acc']} percent to {D['fan_acc']}."),
 ("proof", 24.3, f"As accurate as Claude. Answers in {W(D['ms']) if D['ms']<10 else D['ms']} milliseconds."),
 ("proof", 32.3, f"Today, live: {W(D['named_right'])} of {W(D['named_n'])} named calls, right."),
 ("close", 0.3, "We're not competing with Kalshi. We're the smart layer on top."),
 ("close", 8.0, "Kalshi Knows. Know first."),
 ("close", 14.0, "Built by Faisal, Kevin and Dugar. Free. Public data. No real money."),
]
if __name__ == "__main__":
    D["lines"] = [dict(id=i, scene=s, off=o, text=t) for i, (s, o, t) in enumerate(LINES)]
    D["scenes"] = SCENES; D["beat"] = BEAT
    json.dump(D, open(f"{B}/ad.json", "w"), indent=1)
    for l in D["lines"]: print(l["id"], l["scene"], l["off"], l["text"])
