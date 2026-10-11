"""Story script for the ~50 s ad. Cue markers [name] attach to the next two spoken words."""
import json, os, datetime, zoneinfo
H = os.path.dirname(os.path.abspath(__file__)); R = os.path.dirname(H); B = f"{H}/build"
from ad_data import D
h = D["hero"]; tz = zoneinfo.ZoneInfo("America/Los_Angeles")
jump_dt = datetime.datetime.fromtimestamp((h["wall"] + h["price_start_s"] * 1000) / 1000, tz)
D["jump_clock"] = jump_dt.strftime("%-I:%M")
gap = int(round(D["stream_s"] - h["alert_lag_s"]))
NUM = {29: "Twenty-nine", 28: "Twenty-eight", 30: "Thirty", 27: "Twenty-seven", 31: "Thirty-one", 26: "Twenty-six", 32: "Thirty-two"}
D["gap_s"] = gap
play = "touchdown" if "TOUCHDOWN" in h["play_text"] else "big play"
D["alert_text"] = f"{D['team_name']} {play}"
cv = json.load(open(f"{R}/train/out/relabeled_metrics.json"))["cv_live"]["named_precision"]
k = max(1, min(5, round(cv * 5))); D["five_k"] = k
WORDS5 = {3: "three", 4: "four", 5: "five"}
P = [
 ("hook", "[race]Your stream is almost a minute behind real life. [mk]Prediction markets aren't, they react to every play in seconds."),
 ("story", f"[time]At {D['jump_clock']} today, [jump]Kalshi's price jumped. [buzz]Our app read the jump and buzzed this phone: [alert]{D['alert_text']}. [later]{NUM.get(gap, str(gap))} seconds later, [tv]the stream finally showed it."),
 ("proof", f"[seasons]We trained it on twenty-eight seasons of NFL plays and [moves]thousands of real market moves. [five]When it names a play, it's right about {WORDS5[k]} times out of five."),
 ("more", "[hide]Hide spoilers, [sync]sync alerts to your stream, [agent]or let an agent trade on Kalshi's demo exchange."),
 ("close", "[nc]We're not competing with Kalshi, we're the smart layer on top. [logo]Kalshi Knows. [tag]Know before your stream."),
]
if __name__ == "__main__":
    json.dump(dict(D, paras=P), open(f"{B}/ad2.json", "w"), indent=1)
    for s, t in P: print(s, "|", t)
