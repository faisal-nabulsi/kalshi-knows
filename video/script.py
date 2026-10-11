"""Narration for Big Spoiler Steve (original character). All numbers come from build/data.json."""
import json, os
H = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(f"{H}/build/data.json"))
h = D["hero"]; L = dict(D["ladder"]); cl = {r["model"]: r for r in D["claude"]["rows"]}
kk = next(r for m, r in cl.items() if m.startswith("Kalshi Knows")); cc = next(r for m, r in cl.items() if m.startswith("Claude"))
TEAM = {"NYG": "Giants", "WSH": "Commanders", "WAS": "Commanders"}
hn = D["honest"]; pc = lambda x: f"{round(x*100)}"
ORD = {1: "first", 2: "second", 3: "third", 4: "fourth"}
if hn["src"] == "today": hon = f"Tested on today's untouched games, it names the play right {pc(hn['acc'])} percent. Just guessing nothing happened scores {pc(hn['base'])}."
else: hon = f"Tested on 2026 games it never saw, it names the play right {pc(hn['acc'])} percent. Just guessing nothing happened scores {pc(hn['base'])}." if hn.get("base") else f"Tested on 2026 games it never saw, it names the play right {pc(hn['acc'])} percent."
SCENES = [("cold", 17.5), ("money", 38), ("tour", 40), ("how", 31), ("close", 20)]
LINES = [
 ("cold", 0.3, "Folks, your stream is LYING to you!"),
 ("cold", 3.2, f"At the Super Bowl, antenna, {L['ANTENNA']} seconds behind. Cable, {L['CABLE']}. Peacock, {L['PEACOCK']}. YouTube TV, {L['YOUTUBE TV']}. And NFL+, {L['NFL+']}!"),
 ("cold", 12.8, f"But Kalshi's price? {D['market_median']} seconds."),
 ("money", 0.3, f"{TEAM.get(h['away'],h['away'])} at {TEAM.get(h['home'],h['home'])}, {ORD[h['period']]} quarter. Strip sack! Fumble! Washington ball!"),
 ("money", 9.0, f"BUZZ! Your phone says: {h['headline']}! That's {round(h['alert_lag_s'])} seconds after the play."),
 ("money", 17.0, "Now look right. That's your stream. Nothing! Not a peep! Still sitting on second and eight."),
 ("money", 24.2, "Any second now... any second..."),
 ("money", 28.0, "BOOM! ESPN's own feed finally shows it!"),
 ("money", 31.6, f"{h['lead_s']} seconds after your phone knew. You're welcome, folks!"),
 ("tour", 0.4, "Here's the real product, live. Every alert gets a receipt, graded against ESPN, and misses stay on the board. No tout does that."),
 ("tour", 9.6, "Spoiler takeover! Full screen, a countdown to when your stream catches up, and you call the play before it airs."),
 ("tour", 17.8, f"The Proof page! Our model against Claude, head to head. {pc(kk['accuracy'])} percent to {pc(cc['accuracy'])}. A tie on accuracy, and better calibrated."),
 ("tour", 27.8, "Auto! Rules that turn signals into orders, play money only, plus movers across every market."),
 ("tour", 34.6, "And Dutch Book traps: prices that look like free money, until you read the fine print."),
 ("how", 0.3, "How's it work? Twenty-eight seasons of NFL plays teach a model what football looks like."),
 ("how", 6.2, f"Then we fine-tune it on about {round(D['n_real'],-2):,} real Kalshi price jumps, labels audited."),
 ("how", 12.0, "Then the live engine watches the public order book, and pushes the play to your phone!"),
 ("how", 18.0, "And the honest part! " + hon),
 ("how", 26.0, f"And on today's games, pre-registered: named calls, {D['prereg']['right']} of {D['prereg']['named']} right.") if D.get("prereg") else ("how", 26.0, "Pre-registered test on today's games is next."),
 ("close", 0.3, "We're not competing with Kalshi. We're the intelligence layer on top of prediction markets!"),
 ("close", 7.4, "Kalshi Knows, by Faisal Nabulsi, Kevin, and Dugar."),
 ("close", 12.4, "Scan the code. Public data only. No real money. I'm Big Spoiler Steve, and I'm outta here!"),
]
def spoken(t):
    for a, b in (("NFL+", "N F L Plus"), ("Kalshi", "Kalshee"), ("ESPN", "E S P N"), ("Dugar", "Doo-gar"), ("% sure", " percent sure"), ("(", ""), (")", "")): t = t.replace(a, b)
    return t
if __name__ == "__main__":
    json.dump(dict(scenes=SCENES, lines=[dict(scene=s, off=o, text=t, say=spoken(t)) for s, o, t in LINES]), open(f"{H}/build/script.json", "w"), indent=1)
    for l in LINES: print(l)
