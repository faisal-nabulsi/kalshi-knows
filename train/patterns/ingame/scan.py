import json, sys, warnings, math, itertools
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[3]; sys.path.insert(0, str(ROOT/"train"))
import finetune_real as fr
THR, CD, B = 0.08, 60_000, 5000
df = fr.load_windows()
ctx = pd.read_parquet(ROOT/"train/context/out/game_context.parquet").set_index("game_id")
hw = ctx.home_win.to_dict(); tie = ctx.tie.to_dict()
def detect(t,p):
    w=int(fr.WINDOW_S/fr.STEP)
    for i in range(w,len(p)-fr.HOLD_BINS):
        if t[i]<-10 or np.isnan(p[i]) or np.isnan(p[i-w]): continue
        d=p[i]-np.nanmin(p[i-w:i+1]) if p[i]>=p[i-w] else p[i]-np.nanmax(p[i-w:i+1])
        if abs(d)>=THR and all(abs(p[i+k]-(p[i]-d))>=THR*0.8 for k in range(1,fr.HOLD_BINS+1)):
            return i+fr.HOLD_BINS,i,d
    return None
ev=[]; ext=[]
for r in df.itertuples(index=False):
    if r.game_id not in hw or pd.isna(hw[r.game_id]) or tie.get(r.game_id): continue
    t=np.asarray(r.path_t,float); p=pd.Series(np.asarray(r.path_p,float)).ffill().to_numpy()
    if np.isnan(p).all(): continue
    n=np.asarray(r.path_n,float)
    act=n[t<=-10].sum()
    pih=int(bool(r.posteam_is_home)) if pd.notna(r.posteam_is_home) else int(r.posteam==r.home)
    base=dict(game_id=r.game_id,season=int(r.season),abs_ms=r.wallclock_ms,qtr=int(r.qtr),gsr=r.game_seconds_remaining,cat=r.category,pih=pih,act=act,home_win=hw[r.game_id],t=t,p=p)
    if r.game_seconds_remaining<=300: ext.append(base)
    h=detect(t,p)
    if h is None: continue
    ic,i0,d=h
    ev.append(dict(base,ic=ic,tc=t[ic],jump=d,pb=p[i0-int(fr.WINDOW_S/fr.STEP)] if i0>=10 else np.nan,abs_ms=r.wallclock_ms+t[ic]*1000))
E=pd.DataFrame(ev).sort_values(["game_id","abs_ms"]); keep=[];last={}
for k,r in E.iterrows():
    if r.game_id in last and r.abs_ms-last[r.game_id]<CD: continue
    last[r.game_id]=r.abs_ms; keep.append(k)
E=E.loc[keep].reset_index(drop=True)
p25=E[E.season==2025]; 
# activity terciles from 2025 events
q1,q2=np.percentile(p25.act,[33.3,66.7])
print("events",E.season.value_counts().to_dict(),"act terciles",q1,q2)
aj=E.jump.abs(); up=E.jump>0
toward_off=((E.pih==1)==up)
fav=np.maximum(E.pb,1-E.pb)
cov={}
cov["jump"]={"0.08-0.12":aj<0.12,"0.12-0.20":(aj>=0.12)&(aj<0.20),">=0.20":aj>=0.20}
cov["dir"]={"toward_off":toward_off,"toward_def":~toward_off}
q=E.qtr;g=E.gsr
cov["time"]={"Q1":q==1,"Q2":q==2,"Q3":q==3,"Q4>5min":(q==4)&(g>300),"Q4<=5min/OT":((q==4)&(g<=300))|(q>=5)}
cov["price"]={"fav<0.60":fav<0.60,"0.60-0.80":(fav>=0.6)&(fav<0.8),"0.80-0.90":(fav>=0.8)&(fav<0.9),">=0.90":fav>=0.9}
cov["act"]={"low":E.act<=q1,"mid":(E.act>q1)&(E.act<=q2),"high":E.act>q2}
cov["cat"]={c:E.cat==c for c in ["OTHER","TD","FG","TURNOVER","BIG_PLAY"]}
slices={"ALL":np.ones(len(E),bool)}
for k,v in cov.items():
    for l,m in v.items(): slices[f"{k}={l}"]=m.to_numpy()
for k in ["jump","time","cat"]:
    for l,m in cov[k].items():
        for dl,dm in cov["dir"].items(): slices[f"{k}={l}&dir={dl}"]=(m&dm).to_numpy()
print("slices",len(slices))
def fee(a): return np.ceil(np.round(0.07*100*a*(1-a)*100,9))/100/100
def px(r,tt):
    j=np.searchsorted(r.t,tt)
    return r.p[j] if j<len(r.t) and r.t[j]==tt else np.nan
HZ={"+5":6,"+10":10,"+20":20,"+40":40}; EX={"settle":None,"mtm60":60,"mtm120":120}
# precompute per event prices
tcs=E.tc.to_numpy()
PE={h:np.array([px(r,tc+dh) if tc+dh<=120 else np.nan for r,tc in zip(E.itertuples(),tcs)]) for h,dh in HZ.items()}
PX={x:np.array([px(r,float(tt)) for r in E.itertuples()]) if tt else None for x,tt in EX.items()}
# note E.itertuples holds t,p arrays
def trades(mask,action,h,ex,season):
    pe=PE[h]; dh=HZ[h]
    tow_home=up.to_numpy()
    buy_home=tow_home if action=="follow" else ~tow_home
    ask=np.where(buy_home,pe+0.01,1-pe+0.01)
    ok=mask&(E.season.to_numpy()==season)&~np.isnan(pe)&(ask<1.0)
    hwv=E.home_win.to_numpy()
    win=np.where(buy_home,hwv,1-hwv); fb=fee(ask)
    if ex=="settle": pnl=win-ask-fb
    else:
        pxx=PX[ex]; bid=np.where(buy_home,pxx-0.01,1-pxx-0.01)
        ok&=~np.isnan(pxx)&((tcs+dh+10)<=EX[ex])&(bid>0)
        pnl=bid-ask-fb-fee(np.clip(bid,0.001,0.999))
        win=(bid>ask).astype(float)
    return pd.DataFrame(dict(g=E.game_id.to_numpy()[ok],ask=ask[ok],fee=fb[ok],pnl=pnl[ok],win=win[ok]))
def boot(T,seed):
    agg=T.assign(c=T.ask+T.fee).groupby("g")[["pnl","c"]].sum().to_numpy()
    d=np.random.default_rng(seed).integers(0,len(agg),(B,len(agg)))
    return agg[d,0].sum(1)/agg[d,1].sum(1)
def stat(T,seed):
    if len(T)<1: return dict(n=0)
    bs=boot(T,seed); roi=T.pnl.sum()/(T.ask+T.fee).sum()
    return dict(n=int(len(T)),games=int(T.g.nunique()),hit=round(float(T.win.mean()),3),roi=round(float(roi),4),
        ci=[round(float(np.percentile(bs,2.5)),4),round(float(np.percentile(bs,97.5)),4)],p=float((bs<=0).mean()),
        gross=round(float((T.win-T.ask+0.01).sum()/(T.ask-0.01).sum()),4) if True else 0)
cells=[]
rng_seed=0
for sn,sm in slices.items():
    for a in ["fade","follow"]:
        for h in HZ:
            for ex in EX:
                rng_seed+=1
                d=stat(trades(sm,a,h,ex,2025),rng_seed)
                cells.append(dict(cell=f"{sn}|{a}|{h}|{ex}",kind="scan",d25=d,sm=sm,a=a,h=h,ex=ex))
# extremes
X=pd.DataFrame(ext); X=X.sort_values(["game_id","abs_ms"]); 
X["pe"]=[px(r,10) for r in X.itertuples()]
def xtr(band,tm,side,season):
    lo,hi=band; rows=[]; seen=set()
    for r in X[X.season==season].itertuples():
        if np.isnan(r.pe) or r.game_id in seen: continue
        gs=r.gsr
        if not((120<gs<=300) if tm=="120-300" else gs<=120): continue
        hp=r.pe; fa=max(hp,1-hp)
        if not(lo<=fa<hi): continue
        fav_home=hp>=0.5
        buy_home=fav_home if side=="fav" else not fav_home
        s=hp if buy_home else 1-hp; ask=s+0.01
        if ask>=1: continue
        seen.add(r.game_id)
        win=r.home_win if buy_home else 1-r.home_win
        f=fee(np.array([ask]))[0]
        rows.append((r.game_id,ask,f,win-ask-f,win))
    return pd.DataFrame(rows,columns=["g","ask","fee","pnl","win"])
xc=[]
for band in [(0.90,0.93),(0.93,0.96),(0.96,0.991)]:
    for tm in ["120-300","<=120"]:
        for side in ["fav","dog"]:
            rng_seed+=1
            # for longshot: band applies to favorite price (so longshot price 1-band)
            cells.append(dict(cell=f"EXT {band}|{tm}|buy_{side}",kind="ext",d25=stat(xtr(band,tm,side,2025),rng_seed),band=band,tm=tm,side=side))
M=len(cells); print("cells",M)
# discovery
for c in cells:
    d=c["d25"]; c["pass"]=bool(d.get("n",0)>=40 and d.get("roi",-1)>0 and d.get("p",1)<0.05)
print("discovery passes",sum(c["pass"] for c in cells),"of",M)
# 2025 BH descriptive
def bh(ps,q=0.10):
    ps=np.asarray(ps); m=len(ps); o=np.argsort(ps); th=(np.arange(1,m+1)/m)*q
    k=np.where(ps[o]<=th)[0]; sel=np.zeros(m,bool)
    if len(k): sel[o[:k.max()+1]]=True
    return sel
p25=[c["d25"].get("p",1) if c["d25"].get("n",0)>=40 and c["d25"].get("roi",-1)>0 else 1 for c in cells]
print("BH on 2025 alone:",int(bh(p25).sum()))
# test once
for c in cells:
    if not c["pass"]: c["d26"]=None; c["p26"]=1.0; continue
    rng_seed+=1
    T=trades(c["sm"],c["a"],c["h"],c["ex"],2026) if c["kind"]=="scan" else xtr(c["band"],c["tm"],c["side"],2026)
    d=stat(T,rng_seed); c["d26"]=d
    c["p26"]=d["p"] if d.get("n",0)>=15 else 1.0
sel=bh([c["p26"] for c in cells])
for c,s in zip(cells,sel): c["bh"]=bool(s and c["d26"] and c["d26"]["roi"]>0)
surv=[c for c in cells if c["bh"]]
print("BH survivors",len(surv))
unadj=[c for c in cells if c["pass"] and c["d26"] and c["d26"].get("n",0)>=15 and c["d26"]["p"]<0.05 and c["d26"]["roi"]>0]
print("unadjusted 2026 p<.05 & roi>0:",len(unadj))
pos26=[c for c in cells if c["pass"] and c["d26"] and c["d26"].get("n",0)>=15 and c["d26"]["roi"]>0]
print("passed & 2026 roi>0:",len(pos26),"of",sum(c["pass"] for c in cells))
out=[{k:v for k,v in c.items() if k not in("sm",)} for c in cells]
json.dump(out,open(ROOT/"train/patterns/ingame/cells.json","w"),default=float)
for c in sorted([c for c in cells if c["pass"]],key=lambda c:c["p26"])[:25]:
    print(c["cell"],"25:",c["d25"].get("n"),c["d25"].get("roi"),"| 26:",c["d26"] and (c["d26"].get("n"),c["d26"].get("roi"),c["d26"].get("ci"),c["d26"].get("p")))
print("EXT cells")
for c in cells:
    if c["kind"]=="ext": print(c["cell"],c["d25"],c["d26"])
# aggregate: mean 2025 ROI across all scan cells passing vs 2026 
print("mean 2026 roi among passes",np.mean([c["d26"]["roi"] for c in cells if c["pass"] and c["d26"] and c["d26"].get("n",0)>0]))
print("---- DESCRIPTIVE (not part of test)")
sc=[c for c in cells if c["kind"]=="scan" and c["d25"].get("n",0)>=40]
print("scan cells with n>=40:",len(sc),"; with roi>0:",sum(c["d25"]["roi"]>0 for c in sc),"; min p",min(c["d25"]["p"] for c in sc))
for c in sc:
    if c["cell"].startswith("ALL|") and c["ex"]=="settle": print(c["cell"],c["d25"]["n"],c["d25"]["roi"],c["d25"]["gross"])
top=sorted(sc,key=lambda c:-c["d25"]["roi"])[:10]
dd=[]
for c in top:
    d=stat(trades(c["sm"],c["a"],c["h"],c["ex"],2026),999); dd.append(d)
    print("TOP25",c["cell"],c["d25"]["n"],c["d25"]["roi"],c["d25"]["p"],"-> 2026(desc)",d.get("n"),d.get("roi"))
# 2025 vs 2026 ROI correlation across cells with n>=40 both
a=[];b=[]
for c in sc:
    d=stat(trades(c["sm"],c["a"],c["h"],c["ex"],2026),1)
    if d.get("n",0)>=30: a.append(c["d25"]["roi"]);b.append(d["roi"])
print("cells n>=30 in 2026:",len(a),"corr(roi25,roi26)=",np.corrcoef(a,b)[0,1],"mean25",np.mean(a),"mean26",np.mean(b),"frac26>0",np.mean(np.array(b)>0))
