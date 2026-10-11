import sys,json,os,datetime as dt
sys.path.insert(0,"pipeline")
from someone_knew_cands import get
EXC=("SHARE","STREAMS","KXYT","KXARTISTSTREAM","KXTRUMP","MENTION","KXAVG","COUNT","KXOPENSOURCE","KXANTHVSPEND","KXLLM","KXAISPIKE","KXSPACEXCOUNT","KXTOP10","KXALBUMEQUIV","SPEND")
def ts(s): return int(dt.datetime.fromisoformat(s.replace("Z","+00:00")).timestamp())
def cands():
    c=json.load(open("pipeline/out/someone_knew/cands.json"))
    return [x for x in c if x["result"] in("yes","no") and x["vol"]>=float(os.environ.get("MINVOL",10000)) and x["cat"]!="Mentions" and not any(e in x["series"] for e in EXC)]
def series(m,res,t0,t1):
    d=get(f"/series/{m['series']}/markets/{m['ticker']}/candlesticks",start_ts=t0,end_ts=t1,period_interval=res)
    out=[];last=None
    for k in d.get("candlesticks",[]):
        p=k["price"].get("close_dollars")
        if p is None:
            b=k.get("yes_bid",{}).get("close_dollars");a=k.get("yes_ask",{}).get("close_dollars")
            p=(float(b)+float(a))/2 if b and a else last
        p=float(p) if p is not None else None
        if p is not None: last=p
        out.append((k["end_period_ts"],p,float(k.get("volume_fp") or 0)))
    return [o for o in out if o[1] is not None]
def analyze(m):
    import os
    cp="pipeline/out/someone_knew/hourly/"+m["ticker"]+".json"
    os.makedirs("pipeline/out/someone_knew/hourly",exist_ok=True)
    if os.path.exists(cp): s=json.load(open(cp))
    else:
        t0=max(ts(m["open"]),ts(m["close"])-60*86400);t1=ts(m["close"])+3600
        s=series(m,60,t0,t1); json.dump(s,open(cp,"w"))
    if len(s)<6: return None
    yes=m["result"]=="yes"
    q=[p if yes else 1-p for _,p,_ in s]
    best=None
    for j in range(1,len(q)):
        lo=min(q[max(0,j-3):j]); hi=max(q[j:j+3])
        if hi-lo>=0.33 and hi>=0.7 and min(q[j+2:j+8] or [1])>=0.6 and lo<0.55:
            if best is None or hi-lo>best[0]: best=(hi-lo,j,lo,hi)
    if not best: return None
    _,j,lo,hi=best
    return dict(m,cross_ts=s[j][0],pre=lo,post=hi)
if __name__=="__main__":
    out=[];C=cands();print(len(C))
    for n,m in enumerate(C):
        try:
            r=analyze(m)
        except Exception as e: print("err",m["ticker"],e); continue
        if r: out.append(r); print(n,m["ticker"],r["pre"],r["post"],dt.datetime.utcfromtimestamp(r["cross_ts"]),flush=True)
    json.dump(out,open(os.environ.get("OUTM","pipeline/out/someone_knew/moves.json"),"w"))
    json.dump(len(C),open("pipeline/out/someone_knew/nscanned.json","w"))
