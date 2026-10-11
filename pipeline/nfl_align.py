"""Align ESPN plays with Kalshi home-market trades -> aligned_jumps.parquet, market_lag.json/png, detector_sweep.json."""
import os, json, sys
import numpy as np, pandas as pd
D=os.path.join(os.path.dirname(__file__),'out'); R=os.path.join(os.path.dirname(__file__),'..','results')
CAND={'TD','FG','TURNOVER','SAFETY','BIG_PLAY'}
STATE=['qtr','game_seconds_remaining','score_differential','posteam','posteam_is_home','down','ydstogo','yardline_100']
def load_trades():
    out={}
    for f in os.listdir(os.path.join(D,'trades')):
        if f.endswith('.parquet'): out[f[:-8]]=pd.read_parquet(os.path.join(D,'trades',f))
    return out
def align_play(tr,ts,pr,ct,w):
    a=np.searchsorted(ts,w-60000); b=np.searchsorted(ts,w-5000,side='right')
    if b<=a: return None
    pb=pr[b-1]
    c=np.searchsorted(ts,w+30000); d=np.searchsorted(ts,w+90000,side='right')
    if d<=c: return None
    pa=float((pr[c:d]*ct[c:d]).sum()/ct[c:d].sum())
    delta=pa-pb; mid=(pb+pa)/2
    e=np.searchsorted(ts,w-10000); first=None
    for i in range(e,d):
        if (pr[i]-mid)*np.sign(delta)>=0 and abs(delta)>1e-9: first=int(ts[i]); break
    return dict(p_home_before=float(pb),p_home_after=pa,delta_home=delta,first_move_ms=first,
        lag_s=(first-w)/1000 if first is not None else np.nan,n_trades=int(np.searchsorted(ts,w+90000)-np.searchsorted(ts,w-60000)),
        volume=float(ct[a:d].sum()))
def build():
    plays=pd.read_parquet(os.path.join(D,'nfl_plays.parquet')); trades=load_trades(); rng=np.random.default_rng(7)
    rows=[]
    for gid,tr in trades.items():
        g=plays[plays.game_id==gid].sort_values('wallclock_ms')
        ts=tr.ts_ms.values; pr=tr.p.values; ct=tr['count'].values
        wall=g.wallclock_ms.values
        cand=g[g.category.isin(CAND)]
        quiet=g[(g.category=='OTHER')&g.down.notna()]
        quiet=quiet.sample(min(len(quiet),max(5,len(cand)//2)),random_state=1)
        for _,p in pd.concat([cand,quiet]).iterrows():
            r=align_play(tr,ts,pr,ct,int(p.wallclock_ms))
            if r is None: continue
            near=((np.abs(wall-p.wallclock_ms)<=90000)&(wall!=p.wallclock_ms))&np.isin(g.category.values,list(CAND))
            r.update(game_id=gid,play_id=p.play_id,wallclock_ms=int(p.wallclock_ms),period=p.period,clock=p.clock,category=p.category,team=p.team,
                text=p.text,home=p.home,away=p.away,home_score_pre=p.home_score_pre,away_score_pre=p.away_score_pre,
                is_quiet=p.category=='OTHER',clean=bool(near.sum()==0),**{k:p[k] for k in STATE})
            sgn=1 if p.team==p.home else -1
            r['delta_team']=r['delta_home']*sgn if p.team else np.nan
            rows.append(r)
    df=pd.DataFrame(rows); df.to_parquet(os.path.join(D,'aligned_jumps.parquet')); return df,plays,trades
def q(x): 
    x=x.dropna(); 
    return dict(median_s=round(float(x.median()),2),p25_s=round(float(x.quantile(.25)),2),p75_s=round(float(x.quantile(.75)),2),n=int(len(x))) if len(x) else dict(n=0)
def lag_report(df,ngames):
    s=df[(~df.is_quiet)&(df.delta_home.abs()>=0.05)&df.lag_s.notna()]
    out=dict(games=ngames,n_candidate_plays=int((~df.is_quiet).sum()),min_abs_delta=0.05,overall=q(s.lag_s),
      by_category={c:q(g.lag_s) for c,g in s.groupby('category')},
      clean_only_overall=q(s[s.clean].lag_s),clean_only_by_category={c:q(g.lag_s) for c,g in s[s.clean].groupby('category')},
      share_moved_before_wallclock=round(float((s.lag_s<0).mean()),3),
      share_direction_matches_team=round(float((np.sign(s.delta_team)>0).mean()),3),
      stream_delay_reference_s={'broadcast':19,'best_stream':48,'worst_stream':62},
      notes="lag_s = first trade after wallclock-10s crossing halfway between pre (last trade in [-60,-5]s) and post (VWAP [+30,+90]s) price. ESPN wallclock semantics: see docs; negative lag = price moved before ESPN timestamp.")
    json.dump(out,open(os.path.join(R,'market_lag.json'),'w'),indent=1)
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(9,4.5)); x=s.lag_s.clip(-30,90)
    ax.hist(x,bins=np.arange(-30,91,2),color='#4c9be8')
    for v,l,c in [(19,'broadcast 19s','#2a9d8f'),(48,'best stream 48s','#e9c46a'),(62,'worst stream 62s','#e76f51')]: ax.axvline(v,color=c,ls='--',label=l)
    ax.axvline(s.lag_s.median(),color='k',label=f'Kalshi median {s.lag_s.median():.1f}s')
    ax.set_xlabel('seconds after ESPN play timestamp until Kalshi price moves'); ax.set_ylabel('plays'); ax.legend(); ax.set_title(f'Kalshi price lag, n={len(s)} plays, {ngames} games')
    fig.tight_layout(); fig.savefig(os.path.join(R,'market_lag.png'),dpi=130)
    return out
def grid(tr,lo,hi):
    t=np.arange(lo,hi+1,1000); idx=np.searchsorted(tr.ts_ms.values,t,side='right')-1
    p=np.where(idx>=0,tr.p.values[np.clip(idx,0,None)],np.nan); return t,p
def detect(t,p,thr,win=20,persist=3,cool=60):
    alerts=[];last=-1e18;run=0
    for i in range(win,len(t)):
        if np.isnan(p[i]) or np.isnan(p[i-win]): run=0; continue
        d=p[i]-p[i-win]
        if abs(d)>=thr:
            run+=1
            if run>=persist and t[i]-last>=cool*1000:
                alerts.append((int(t[i]),float(p[i-win]),float(p[i]))); last=t[i]; run=0
        else: run=0
    return alerts
def sweep(plays,trades):
    res=[]
    g_cache={}
    for gid,tr in trades.items():
        g=plays[(plays.game_id==gid)&plays.category.isin(CAND)]
        if g.empty: continue
        lo=int(g.wallclock_ms.min())-300000; hi=int(g.wallclock_ms.max())+120000
        hl=plays[(plays.game_id==gid)&(plays.category.isin(CAND)|(plays.espn_wp_delta.abs()>=0.05))]
        g_cache[gid]=(grid(tr,lo,hi),g,hl.wallclock_ms.values)
    for thr in np.arange(0.04,0.1501,0.01):
        na=nm=nh=0;rec=[0,0];delays=[]
        for gid,((t,p),g,hw) in g_cache.items():
            al=detect(t,p,thr); w=g.wallclock_ms.values; cats=g.category.values
            for a in al:
                na+=1; m=(a[0]>=w-20000)&(a[0]<=w+90000)
                if m.any(): nm+=1
                if ((a[0]>=hw-20000)&(a[0]<=hw+90000)).any(): nh+=1
            for wi,c in zip(w,cats):
                if c in ('TD','FG','TURNOVER'):
                    rec[1]+=1
                    ds=[a[0]-wi for a in al if -20000<=a[0]-wi<=90000]
                    if ds: rec[0]+=1; delays.append(min(ds,key=abs)/1000)
        res.append(dict(threshold=round(float(thr),2),n_alerts=na,precision=round(nm/na,3) if na else None,precision_incl_high_leverage=round(nh/na,3) if na else None,recall=round(rec[0]/rec[1],3) if rec[1] else None,
            median_detection_delay_s=round(float(np.median(delays)),1) if delays else None,n_games=len(g_cache)))
    ok=[r for r in res if r['precision_incl_high_leverage'] and r['recall']]
    good=[r for r in ok if r['precision_incl_high_leverage']>=0.85]
    best=good[0] if good else ok[-1]
    out=dict(recommended_threshold=best['threshold'],criterion='lowest threshold with precision_incl_high_leverage>=0.85 (keeps recall highest while alerts stay mostly meaningful)',
      match_window='alert within [-20s,+90s] of ESPN play wallclock; recall over TD/FG/TURNOVER',precision_note='precision = alerts near a TD/FG/TURNOVER/SAFETY/BIG_PLAY (strict); precision_incl_high_leverage also counts plays where ESPN win prob moved >=5 pts (e.g. missed FG, 4th-down stops, key conversions)',detector='|p(t)-p(t-20s)|>=thr for >=3 consecutive seconds, 60s cooldown, last-trade price on 1s grid',sweep=res)
    json.dump(out,open(os.path.join(R,'detector_sweep.json'),'w'),indent=1); return out
if __name__=='__main__':
    df,plays,trades=build()
    print(len(df),'rows',len(trades),'games'); print(json.dumps(lag_report(df,len(trades)),indent=1)[:2500])
    o=sweep(plays,trades); print(o['recommended_threshold']); [print(r) for r in o['sweep']]
