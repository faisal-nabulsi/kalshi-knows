"""Add multi-market paths to real_windows(.parquet|_today) -> real_windows_mm.parquet / real_windows_today_mm.parquet.
pts_path      : sum_k P(total>k)*w_k (w_k = half the gap to each neighbouring strike, i.e. trapezoid integral of the survival curve) over KXNFLTOTAL strikes that have a trade at every grid point of the window (partial sum; level not comparable across windows, deltas are). pts_n = strikes used.
pts_local_path: same but only the 6 strikes nearest the market's own median total at window start (where P~0.5) -- the strikes a live engine should poll.
pts_local_score_path: same, but the 6 strikes nearest the literal pre-play score total (coordinator's definition).
td_path / td_local_path (4 nearest median): same on KXNFLTOTALTD (spacing 1).
scorer_top/scorer_jump: KXNFLTD (anytime TD scorer, per-player '1+' markets; KXNFLANYTD has no 2026 markets): player whose price rose most within +60s over its price at t=-10s, if >=0.5."""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0,os.path.dirname(__file__))
D=os.path.join(os.path.dirname(__file__),'out')
def ffill_at(ts,pr,tt):
    idx=np.searchsorted(ts,tt,side='right')-1
    return np.where(idx>=0,pr[np.clip(idx,0,None)],np.nan)
def load(gid,S):
    f=os.path.join(D,'mm',gid,S+'.parquet')
    if not os.path.exists(f): return {}
    df=pd.read_parquet(f); out={}
    for t,g in df.groupby('ticker'):
        g=g.sort_values('ts_ms'); out[t]=(float(g.strike.iloc[0]) if pd.notna(g.strike.iloc[0]) else np.nan,g.label.iloc[0],g.ts_ms.values,g.p.values)
    return out
def ladder_path(mk,w,T,k_local,center_fn):
    """returns full, local, n, local_literal"""
    if not mk: return None
    ks=sorted(mk.items(),key=lambda kv:kv[1][0]); strikes=np.array([v[0] for _,v in ks])
    tt=w+T*1000
    P=np.array([ffill_at(v[2],v[3],tt) for _,v in ks])        # strikes x grid
    ok=~np.isnan(P).any(axis=1)
    if ok.sum()==0: return None
    if len(strikes)>1:
        g=np.diff(strikes); sp=np.empty(len(strikes)); sp[0]=g[0]; sp[-1]=g[-1]; sp[1:-1]=(g[:-1]+g[1:])/2   # trapezoid weights = half gap to each neighbour
    else: sp=np.ones(1)
    full=(P[ok]*sp[ok][:,None]).sum(axis=0)
    idx=np.where(ok)[0]
    return full,idx,P,sp,strikes,ok
def local_sum(P,sp,strikes,ok,center,k):
    idx=np.where(ok)[0]
    if len(idx)==0 or center is None or np.isnan(center): return None
    near=idx[np.argsort(np.abs(strikes[idx]-center))[:k]]
    return (P[near]*sp[near][:,None]).sum(axis=0)
def median_center(st,p0):
    # strike where P(total>k) crosses 0.5 at window start (interpolated)
    if len(st)==0: return np.nan
    return float(st[np.argmin(np.abs(p0-0.5))])
def run(src,dst):
    w=pd.read_parquet(src); T=w.path_t.iloc[0]; T=np.array(T); cols={k:[] for k in ['pts_path','pts_n','pts_local_path','pts_local_score_path','td_path','td_n','td_local_path','scorer_top','scorer_jump']}
    cache={}
    for r in w.itertuples():
        gid=r.game_id
        if gid not in cache: cache={gid:(load(gid,'KXNFLTOTAL'),load(gid,'KXNFLTOTALTD'),load(gid,'KXNFLTD'))}
        tot,td,sc=cache[gid]; wc=r.wallclock_ms
        for name,mk,kloc in (('pts',tot,6),('td',td,4)):
            res=ladder_path(mk,wc,T,kloc,None)
            if res is None:
                cols[name+'_path'].append(None); cols[name+'_n'].append(0)
                if name=='pts': cols['pts_local_path'].append(None); cols['pts_local_score_path'].append(None)
                else: cols['td_local_path'].append(None)
                continue
            full,idx,P,sp,strikes,ok=res
            cols[name+'_path'].append(full.astype('float32').tolist()); cols[name+'_n'].append(int(ok.sum()))
            cen=median_center(strikes[ok],P[ok][:,0])
            loc=local_sum(P,sp,strikes,ok,cen,kloc)
            cols[name+'_local_path' if name=='td' else 'pts_local_path'].append(None if loc is None else loc.astype('float32').tolist())
            if name=='pts':
                lit=local_sum(P,sp,strikes,ok,r.home_score_pre+r.away_score_pre,6)
                cols['pts_local_score_path'].append(None if lit is None else lit.astype('float32').tolist())
        best=(None,0.0)
        t0=np.searchsorted(T,-10); i60=np.searchsorted(T,60,side='right')
        for tk,(k,lab,ts,pr) in sc.items():
            p=ffill_at(ts,pr,wc+T*1000)
            b=p[t0]
            if np.isnan(b): continue
            j=np.nanmax(p[t0:i60])-b
            if j>best[1]: best=(lab,float(j))
        if best[1]>=0.5: cols['scorer_top'].append(str(best[0]).split(':')[0]); cols['scorer_jump'].append(best[1])
        else: cols['scorer_top'].append(None); cols['scorer_jump'].append(best[1] if best[0] else np.nan)
    for k,v in cols.items(): w[k]=v
    w.to_parquet(dst); return w
def report(w):
    print(len(w),'windows')
    for c in ['pts_path','pts_local_path','pts_local_score_path','td_path','td_local_path']: print(c,round(w[c].notna().mean(),3))
    print('scorer_top',round(w.scorer_top.notna().mean(),3),'scorer_jump measured',round(w.scorer_jump.notna().mean(),3))
    i30=int(np.searchsorted(np.array(w.path_t.iloc[0]),30)); i0=int(np.searchsorted(np.array(w.path_t.iloc[0]),0))
    d=w[w.pts_path.notna()].copy(); d['d']=d.pts_path.map(lambda x:x[i30]-x[i0]); d['dl']=d.pts_local_path.map(lambda x:x[i30]-x[i0] if x is not None else np.nan)
    d['dt']=d.td_path.map(lambda x:x[i30]-x[i0] if x is not None else np.nan)
    print(d.groupby('category')[['d','dl','dt']].median().assign(n=d.groupby('category').size()))
if __name__=='__main__':
    if '--today' in sys.argv: w=run(os.path.join(D,'real_windows_today.parquet'),os.path.join(D,'real_windows_today_mm.parquet'))
    else: w=run(os.path.join(D,'real_windows.parquet'),os.path.join(D,'real_windows_mm.parquet'))
    report(w)
