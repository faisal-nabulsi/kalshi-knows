import json,sys,datetime as dt
ref={r["ticker"]:r for r in json.load(open("pipeline/out/someone_knew/refined.json"))}
news=json.load(open("pipeline/out/someone_knew/news.json"))
for t in sys.argv[1:] or news:
    r=ref[t]; ms=r["move_start_ms"]
    print("==",t,r["title"][:50],r["sub"],"move",dt.datetime.fromtimestamp(ms/1000,dt.UTC).strftime("%m-%d %H:%M"),r["p_before"],"->",r["p_after"],r["result"])
    seen=set()
    for a in news[t] or []:
        if a["title"] in seen: continue
        seen.add(a["title"])
        print("  %+6.0f"%((a["ms"]-ms)/60000),a["src"][:22],a["title"][:95])
        if len(seen)>=14: break
