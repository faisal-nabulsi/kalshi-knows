import json,time,datetime as dt,statistics
ref=json.load(open("pipeline/out/someone_knew/ref_all.json"))
news=json.load(open("pipeline/out/someone_knew/news.json"))
TIERS={1:("Dugar","Still on the waitlist for his own pre-seed round."),2:("House Cat","Pre-revenue, pre-product, pre-awake. 'Building in stealth' since 2023."),3:("Gazelle","Fast, pretty, and somebody's lunch. Series A tourist."),4:("Everyone Else","A 40-slide consulting deck with no recommendation."),5:("Lion","Tier-1 partner. Eats the gazelle, takes the board seat."),6:("Kevin & Faisal","Returned the fund. Twice.")}
def tier(l): return 1 if l<0 else 2 if l<30 else 3 if l<60 else 4 if l<120 else 5 if l<360 else 6
def ms(s): return int(dt.datetime.fromisoformat(s).replace(tzinfo=dt.UTC).timestamp()*1000)
# manual verdicts: ticker -> (news from GDELT idx match substring | explicit dict, title override, verdict template)
SPEC=json.load(open("pipeline/someone_knew_spec.json"))
cases=[];ev=[]
for t,sp in SPEC.items():
    r=ref[t]
    if "news_ms" in sp: fn=dict(ms=sp["news_ms"],title=sp["news_title"],url=sp["news_url"],src=sp["news_src"])
    else:
        fn=[a for a in news[t] if sp["match"] in a["title"] or sp["match"] in a["url"]][0]
    lead=round((fn["ms"]-r["move_start_ms"])/60000,1)
    L=abs(round(lead)); hrs=f"{L/60:.1f} hours" if L>=120 else f"{L} minutes"
    v=sp["verdict"].replace("{lead}",hrs)
    k=tier(lead)
    ser=[s for s in r["series"] if r["move_start_ms"]-6*3600e3<=s[0]<=r["move_start_ms"]+2*3600e3]
    cases.append(dict(ticker=t,title=sp.get("title") or f'{r["title"]} ({r["sub"]})',category=r["cat"],result=r["result"],move_start_ms=r["move_start_ms"],move_end_ms=r["move_end_ms"],p_before=r["p_before"],p_after=r["p_after"],first_news_ms=fn["ms"],first_news_title=fn["title"],first_news_url=fn["url"],first_news_source=sp.get("src") or fn["src"],lead_minutes=lead,series=ser,verdict=v,tier=k,tier_name=TIERS[k][0],tier_blurb=TIERS[k][1],event=r["event"]))
cases.sort(key=lambda c:-c["lead_minutes"])
evs={}
for c in cases: evs[c["event"]]=max(evs.get(c["event"],-1e9),c["lead_minutes"])
mf=[v for v in evs.values() if v>=30]
for c in cases: c.pop("event")
leads=[c["lead_minutes"] for c in cases if c["lead_minutes"]>=30]
out=dict(generated_ms=int(time.time()*1000),markets_scanned=json.load(open("pipeline/out/someone_knew/nscanned_total.json")),cases=cases,stats=dict(median_lead_minutes=round(statistics.median(leads),1),share_market_first=round(len(mf)/len(evs),3),n=len(cases)))
json.dump(out,open("docs/data/someone_knew.json","w"),separators=(",",":"))
print(len(json.dumps(out)),out["stats"],[(c["ticker"],c["lead_minutes"]) for c in cases])
