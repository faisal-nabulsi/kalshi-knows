import json,os,sys,math,warnings
warnings.filterwarnings("ignore")
import numpy as np,pandas as pd
R='/Users/faisalnabulsi/Desktop/hackathon/degen-oracle/'; D=R+'train/patterns/crossvenue/data/'
sys.path.insert(0,R+'train'); import finetune_real as fr
B=5000; rng=np.random.default_rng(1)
games=json.load(open(D+'games.json')); idx=json.load(open(D+'poly_index.json'))
ctx=pd.read_parquet(R+'train/context/out/game_context.parquet').set_index('game_id')
W=fr.load_windows()
W['season']=W.season.astype(int)
# Kalshi trade events per game from windows
K={}; fires=[]
step,w,hold=fr.STEP,int(fr.WINDOW_S/fr.STEP),fr.HOLD_BINS
def detect(p,start=0,ok=None):
    for i in range(max(w,start),len(p)-hold):
        d=p[i]-np.nanmin(p[i-w:i+1]) if p[i]>=p[i-w] else p[i]-np.nanmax(p[i-w:i+1])
        if abs(d)>=0.08 and all(abs(p[i+k]-(p[i]-d))>=0.08*0.8 for k in range(1,hold+1)):
            return i+hold,d
    return None
ev={}
for r in W.itertuples(index=False):
    t=np.asarray(r.path_t,float); p=np.asarray(r.path_p,float); n=np.asarray(r.path_n,float)
    if np.isnan(p).all(): continue
    p=pd.Series(p).ffill().to_numpy()
    m=n>0
    ev.setdefault(r.game_id,[]).append(np.column_stack([r.wallclock_ms/1000+t[m],p[m]]))
    first=[i for i in range(len(t)) if t[i]>=-10]
    h=detect(p,first[0] if first else 0)
    if h:
        i,d=h; fires.append(dict(game_id=r.game_id,season=r.season,t0=r.wallclock_ms/1000+t[i],jump=d,cat=r.category))
for g,v in ev.items():
    a=np.vstack(v); a=a[np.argsort(a[:,0],kind='stable')]
    # dedupe identical timestamps keeping last
    K[g]=a
F=pd.DataFrame(fires).sort_values(['game_id','t0']); keep=[];last={}
for k,r in F.iterrows():
    if r.game_id in last and r.t0-last[r.game_id]<60: continue
    last[r.game_id]=r.t0; keep.append(k)
F=F.loc[keep].reset_index(drop=True)
# Polymarket series, home-oriented
P={};status={}
for g,m in idx.items():
    if not m or not os.path.exists(D+f'ptrades_{g}.parquet') or g not in K: continue
    t=pd.read_parquet(D+f'ptrades_{g}.parquet')
    if len(t)<20: continue
    t=t.sort_values('ts',kind='stable')
    # orient: outcome idx 0 assumed away (verified below against Kalshi)
    hp=np.where(t.idx==1,t.price,1-t.price)
    P[g]=np.column_stack([t.ts.to_numpy(float),hp])
# orientation check
flip=[]
def last_at(a,x):
    j=np.searchsorted(a[:,0],x,side='right')-1
    return (a[j,1],x-a[j,0]) if j>=0 else (np.nan,np.inf)
chk={}
for g in list(P):
    ts=np.arange(K[g][0,0],K[g][-1,0],30)
    kp=np.array([last_at(K[g],x)[0] for x in ts]); pp=np.array([last_at(P[g],x)[0] for x in ts])
    ok=~np.isnan(kp)&~np.isnan(pp)
    c=np.corrcoef(kp[ok],pp[ok])[0,1] if ok.sum()>10 else np.nan
    chk[g]=c
    if c<0: P[g][:,1]=1-P[g][:,1]; flip.append(g)
bad=[g for g,c in chk.items() if not (c>0.5)]
for g in bad: P.pop(g,None)
print('games with both venues',len(P),'flipped',len(flip),'dropped(low corr)',len(bad))
season={g:(2026 if games[g]['season']=='espn' else 2025) for g in P}
hw={g:ctx.home_win.get(g,np.nan) for g in P}
F=F[F.game_id.isin(P)].reset_index(drop=True)

def kfee(p,C=100): return np.ceil(np.round(0.07*C*p*(1-p)*100,9))/100/C
def pfee(p): return 0.05*p*(1-p)
def boot(vals_by_game, stat, seed=0):
    # vals_by_game: list of arrays per game; stat(concat arrays)
    r=np.random.default_rng(seed); n=len(vals_by_game)
    if n==0: return np.array([np.nan])
    out=np.empty(B)
    for b in range(B):
        ix=r.integers(0,n,n); out[b]=stat(np.concatenate([vals_by_game[i] for i in ix]))
    return out
def roi_stats(T):
    # T: DataFrame with game_id,pnl,cost
    if len(T)==0: return dict(n=0,games=0,roi=np.nan,lo=np.nan,hi=np.nan,p1=1.0)
    gb=T.groupby('game_id')[['pnl','cost']].sum().to_numpy(); r=np.random.default_rng(2)
    dr=r.integers(0,len(gb),(B,len(gb))); bs=gb[dr,0].sum(1)/gb[dr,1].sum(1)
    roi=gb[:,0].sum()/gb[:,1].sum()
    return dict(n=len(T),games=len(gb),roi=float(roi),lo=float(np.percentile(bs,2.5)),hi=float(np.percentile(bs,97.5)),p1=float((bs<=0).mean()),
                gross=float((T.pnl+T.fees).sum()/T.cost.sum()) if 'fees' in T else None)
res={}
# ---------------- lead-lag
def t50(a,t_lo,t_hi,pre,post):
    mid=pre+0.5*(post-pre); sg=np.sign(post-pre)
    m=(a[:,0]>t_lo)&(a[:,0]<=t_hi)
    for tt,pp in a[m]:
        if sg*(pp-mid)>=0: return tt
    return np.nan
LL=[]
for r in F.itertuples():
    g=r.game_id; t0=r.t0
    pk,ak=last_at(K[g],t0-30); pp,ap=last_at(P[g],t0-30)
    if np.isnan(pk) or np.isnan(pp) or ap>120 or ak>120: continue
    qk,_=last_at(K[g],t0+120); qp,_=last_at(P[g],t0+120)
    dk,dp=qk-pk,qp-pp
    if abs(dk)<0.04 or abs(dp)<0.04 or np.sign(dk)!=np.sign(dp) or np.sign(dk)!=np.sign(r.jump): continue
    tk=t50(K[g],t0-30,t0+120,pk,qk); tp=t50(P[g],t0-30,t0+120,pp,qp)
    if np.isnan(tk) or np.isnan(tp): continue
    LL.append(dict(game_id=g,season=r.season,cat=r.cat,lead=tp-tk,t0=t0))
LL=pd.DataFrame(LL)
def cat_mask(df,c):
    if c=='ALL': return np.ones(len(df),bool)
    return (df.cat==c).to_numpy()
CATS={'L1_TD':'TD','L2_FG':'FG','L3_TURNOVER':'TURNOVER','L4_BIGPLAY':'BIG_PLAY','L5_ALL':'ALL'}
print('categories present',F.cat.value_counts().to_dict())
def ll_stats(df):
    if len(df)<5: return dict(n=len(df),median=np.nan,p2=1.0)
    byg=[g.lead.to_numpy() for _,g in df.groupby('game_id')]
    bs=boot(byg,np.median,3); med=float(df.lead.median())
    p2=float(min(1,2*min((bs<=0).mean(),(bs>=0).mean())))
    return dict(n=len(df),games=len(byg),median=med,mean=float(df.lead.mean()),lo=float(np.percentile(bs,2.5)),hi=float(np.percentile(bs,97.5)),p2=p2,
                share_kalshi_first=float((df.lead>0).mean()))
for nm,c in CATS.items():
    for s in (2025,2026):
        sub=LL[(LL.season==s)&cat_mask(LL,c)]
        res[(nm,s)]=ll_stats(sub)
# lead-lag restricted to PM-dense jumps (descriptive)
def pm_dense(g,t0):
    a=P[g][:,0]; return int(((a>=t0-10)&(a<=t0+30)).sum())
LL['dens']=[pm_dense(r.game_id,r.t0) for r in LL.itertuples()]
res['ll_dense']={}
for s_ in (2025,2026):
    for lab,m in (('all',LL.dens>=0),('pm>=8trades',LL.dens>=8),('pm>=15trades',LL.dens>=15)):
        res['ll_dense'][f'{s_}_{lab}']=ll_stats(LL[(LL.season==s_)&m])
res['ll_dense_n_sparse_share']={s_:float((LL[LL.season==s_].dens<8).mean()) for s_ in (2025,2026)}
# ---------------- grid-based A and C cells
def grid_events(g,thr,fresh=20,lat=0):
    k=K[g]; t_start=k[0,0]; t_end=k[-1,0]
    out=[]; lastent=-1e9
    for x in np.arange(t_start+20,t_end,10):
        pk,ak=last_at(K[g],x); pp,ap=last_at(P[g],x)
        if ak>fresh or ap>fresh or np.isnan(pk) or np.isnan(pp): continue
        gap=pp-pk
        if abs(gap)>=thr and x-lastent>=300:
            lastent=x
            if lat:
                pk,ak2=last_at(K[g],x+lat); pp,ap2=last_at(P[g],x+lat)
                if np.isnan(pk) or np.isnan(pp): continue
            out.append((x,pk,pp))
    return out
def arb_trades(thr,s,fresh=20,lat=0):
    rows=[]
    for g in P:
        if season[g]!=s or np.isnan(hw[g]): continue
        for x,pk,pp in grid_events(g,thr,fresh,lat):
            # home cheaper on venue X
            if pk<pp: ah=pk+0.01; aa=(1-pp)+0.01; fh=kfee(ah); fa=pfee(aa)
            else: ah=pp+0.01; aa=(1-pk)+0.01; fh=pfee(ah); fa=kfee(aa)
            if ah>=0.99 or aa>=0.99: continue
            cost=ah+aa+fh+fa; rows.append(dict(game_id=g,pnl=1-cost,cost=cost,fees=fh+fa))
    return pd.DataFrame(rows)
def conv_trades(thr,s,fresh=20,lat=0):
    rows=[]
    for g in P:
        if season[g]!=s or np.isnan(hw[g]): continue
        for x,pk,pp in grid_events(g,thr,fresh,lat):
            if pk<pp: a=pk+0.01; f=kfee(a)
            else: a=pp+0.01; f=pfee(a)
            if a>=0.99: continue
            rows.append(dict(game_id=g,pnl=hw[g]-a-f,cost=a+f,fees=f))
    return pd.DataFrame(rows)
for nm,thr in (('A1',0.04),('A2',0.06),('A3',0.08)):
    for s in (2025,2026): res[(nm,s)]=roi_stats(arb_trades(thr,s))
for nm,thr in (('C1',0.03),('C2',0.05),('C3',0.08)):
    for s in (2025,2026): res[(nm,s)]=roi_stats(conv_trades(thr,s))
# robustness (descriptive, NOT cells): executability of the gap
rob={}
for nm,thr in (('A1',0.04),('A2',0.06),('A3',0.08)):
    for lab,kw in (('fresh2s',dict(fresh=2)),('lat10s',dict(lat=10)),('lat10s_fresh2s',dict(fresh=2,lat=10))):
        for s in (2025,2026): rob[f'{nm}_{lab}_{s}']=roi_stats(arb_trades(thr,s,**kw))
for nm,thr in (('C1',0.03),('C2',0.05)):
    for lab,kw in (('fresh2s',dict(fresh=2)),('lat10s',dict(lat=10))):
        for s in (2025,2026): rob[f'{nm}_{lab}_{s}']=roi_stats(conv_trades(thr,s,**kw))
res['robust']=rob
# gap convergence descriptive
def conv_desc(s,thr=0.05):
    sh=[]
    for g in P:
        if season[g]!=s: continue
        for x,pk,pp in grid_events(g,thr):
            k2,a2=last_at(K[g],x+60); p2,b2=last_at(P[g],x+60)
            if np.isnan(k2) or np.isnan(p2): continue
            sh.append(abs(p2-k2)<=0.5*abs(pp-pk))
    return dict(n=len(sh),share_halved_within_60s=float(np.mean(sh)) if sh else None)
res['conv_desc']={s:conv_desc(s) for s in (2025,2026)}
# ---------------- follow trades
def pm_fires(g):
    a=P[g]; k=K[g]; ts=np.arange(k[0,0],k[-1,0],step)
    p=np.array([last_at(a,x)[0] for x in ts])
    out=[]; i0=w; last=-1e9; i=w
    while i<len(p)-hold:
        if np.isnan(p[i-w:i+hold+1]).any(): i+=1; continue
        h=detect(p,i)
        if not h: break
        j,d=h
        if ts[j]-last>=60: out.append((ts[j],d)); last=ts[j]
        i=j+1
    return out
def follow_rows(src,dst,fires_iter,hor,s,dfee_in,dfee_out):
    rows=[]
    for g,t0,jump in fires_iter:
        if season[g]!=s or np.isnan(hw[g]): continue
        pre,ap=last_at(dst[g],t0-30)
        if np.isnan(pre) or ap>120: continue
        pe,ae=last_at(dst[g],t0+10)
        if ae>120 or abs(pe-pre)>=0.03: continue
        up=jump>0
        ent=(pe+0.01) if up else (1-pe)+0.01
        if ent>=0.99: continue
        xq,_=last_at(dst[g],t0+hor)
        ext=(xq-0.01) if up else (1-xq)-0.01
        ext=max(ext,0.0)
        fi=dfee_in(ent); fo=dfee_out(ext) if ext>0 else 0
        rows.append(dict(game_id=g,pnl=ext-ent-fi-fo,cost=ent+fi,fees=fi+fo))
    return pd.DataFrame(rows)
kf=[(r.game_id,r.t0,r.jump) for r in F.itertuples()]
pf=[]
for g in P:
    for t0,d in pm_fires(g): pf.append((g,t0,d))
print('kalshi jumps',len(kf),'pm jumps',len(pf))
res['n_jumps']=dict(kalshi=len(kf),pm=len(pf))
for nm,src,fl,dst,fe,hor in (('F1','K',kf,P,pfee,60),('F2','K',kf,P,pfee,120),('F3','P',pf,K,kfee,60),('F4','P',pf,K,kfee,120)):
    for s in (2025,2026): res[(nm,s)]=roi_stats(follow_rows(src,dst,fl,hor,s,fe,fe))
# ---------------- cross-correlation of 5 s returns
def xcorr(s):
    num=np.zeros(49);cnt=0; lags=np.arange(-120,121,5)
    acc=np.zeros(len(lags)); n=0
    for g in P:
        if season[g]!=s: continue
        k=K[g]; ts=np.arange(k[0,0],k[-1,0],5.0)
        pk=np.array([last_at(K[g],x)[0] for x in ts]); pp=np.array([last_at(P[g],x)[0] for x in ts])
        dk=np.diff(pk); dp=np.diff(pp)
        ok=~np.isnan(dk)&~np.isnan(dp)
        dk=np.where(ok,dk,0); dp=np.where(ok,dp,0)
        for li,l in enumerate(lags//5):
            if l>=0: a=dk[:len(dk)-l]; b=dp[l:]
            else: a=dk[-l:]; b=dp[:len(dp)+l]
            acc[li]+=np.sum(a*b)
        n+=1; 
    # normalise
    return lags,acc/np.max(np.abs(acc)) if np.max(np.abs(acc))>0 else acc
for s in (2025,2026):
    lg,ac=xcorr(s); res[('xcorr',s)]={'peak_lag_s':int(lg[np.argmax(ac)]),'by_lag':{int(l):round(float(a),3) for l,a in zip(lg,ac) if l%15==0}}
# resolution facts
rs={}
for s in (2025,2026):
    gaps=[];ing=[]
    for g in P:
        if season[g]!=s: continue
        a=P[g]; k=K[g]; m=(a[:,0]>=k[0,0])&(a[:,0]<=k[-1,0]); tt=a[m,0]
        if len(tt)>2: gaps+=list(np.diff(tt)); ing.append(len(tt))
    rs[s]=dict(pm_median_gap_s=float(np.median(gaps)),pm_p90_gap_s=float(np.percentile(gaps,90)),pm_trades_per_game=float(np.mean(ing)),games=len(ing))
res['pm_resolution']=rs
# BH
CELLS=[*CATS,'A1','A2','A3','C1','C2','C3','F1','F2','F3','F4']
rows=[]
for c in CELLS:
    d,t=res[(c,2025)],res[(c,2026)]
    if c in CATS:
        dp=d['p2']; tp=t['p2']; dpass=(dp<0.05); eff25=d['median']; eff26=t['median']; same=np.sign(eff25)==np.sign(eff26)
    else:
        dpass=(d['roi']>0 and d['p1']<0.05) if d['n'] else False; dp=d['p1']; tp=t['p1']; eff25=d['roi']; eff26=t['roi']; same=bool(t['n'] and t['roi']>0)
    rows.append(dict(cell=c,disc_p=dp,disc_pass=bool(dpass),eff25=eff25,n25=d['n'],test_p=tp,eff26=eff26,n26=t['n'],same_sign=bool(same)))
T=pd.DataFrame(rows)
p=T.test_p.fillna(1).to_numpy(); o=np.argsort(p); m=len(p); thr=0
rank=np.empty(m,int); rank[o]=np.arange(1,m+1)
kmax=max([r for r,i in zip(range(1,m+1),o) if p[i]<=0.10*r/m] or [0])
T['bh_reject']=rank<=kmax
T['survivor']=T.bh_reject&T.disc_pass&T.same_sign
print(T.to_string())
T.to_csv(D+'../cells.csv',index=False)
def clean(o):
    if isinstance(o,dict): return {str(k):clean(v) for k,v in o.items()}
    if isinstance(o,(np.floating,)): return float(o)
    if isinstance(o,(np.integer,)): return int(o)
    return o
json.dump(clean(res),open(D+'../results.json','w'),indent=1,default=str)
print(json.dumps(clean({k:v for k,v in res.items() if isinstance(k,str)}),indent=1))
