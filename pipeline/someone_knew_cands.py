import requests, time, json, sys, random
B="https://api.elections.kalshi.com/trade-api/v2"
def get(path, **p):
    for i in range(6):
        time.sleep(0.35)
        try: r=requests.get(B+path,params=p,timeout=30)
        except requests.RequestException: time.sleep(2**i+random.random()); continue
        if r.status_code in (429,500,502,503): time.sleep(2**i+random.random()); continue
        r.raise_for_status(); return r.json()
KEEP=("compan","entertain","science","social","health","cultur","media","mention","tech")
if __name__=="__main__":
    cur=None; out=[]; cats={}
    for pg in range(250):
        p=dict(status="settled",with_nested_markets="true",limit=200)
        if cur: p["cursor"]=cur
        d=get("/events",**p)
        for e in d["events"]:
            c=e.get("category","")
            cats[c]=cats.get(c,0)+1
            if not any(k in c.lower() for k in KEEP): continue
            for m in e.get("markets",[]):
                out.append(dict(ticker=m["ticker"],event=e["event_ticker"],series=e["series_ticker"],cat=c,title=e["title"],sub=m.get("yes_sub_title"),mtitle=m.get("title"),rules=m.get("rules_primary","")[:400],vol=float(m.get("volume_fp") or 0),result=m.get("result"),open=m.get("open_time"),close=m.get("close_time"),settle=m.get("settlement_ts") or m.get("expiration_time"),last=m.get("last_price_dollars")))
        cur=d.get("cursor")
        print(pg,len(out),flush=True)
        if not cur: break
    json.dump(out,open("pipeline/out/someone_knew/cands.json","w"))
