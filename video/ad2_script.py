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
D["gap5"] = int(round(gap / 5.0) * 5)
P = [
 ("hook", "[race]Your stream is a minute behind. [mk]The betting market isn't, it reacts to every play in seconds."),
 ("what", "[what]Kalshi Knows is a free alert that tells you the play before your stream does."),
 ("story", f"[time]At {D['jump_clock']} today, [jump]Kalshi's price jumped. [buzz]Our app read the jump and [alert]buzzed this phone: {D['alert_text']}. [later]About thirty seconds before [tv]the stream showed it."),
 ("proof", "[seasons]We trained it on twenty-five seasons of NFL plays and [moves]thousands of real price jumps. [five]When it calls a play, it's right about four times out of five."),
 ("more", "[hide]Hide spoilers, [sync]sync to your stream, [agent]or trade on Kalshi's demo exchange."),
 ("close", "[logo]Kalshi Knows. [tag]Know before your stream."),
]
if __name__ == "__main__":
    json.dump(dict(D, paras=P), open(f"{B}/ad2.json", "w"), indent=1)
    for s, t in P: print(s, "|", t)
