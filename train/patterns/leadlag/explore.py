import pandas as pd,numpy as np,json,math,os,sys
DELAY=int(sys.argv[1])*1000
R='pipeline/out/'
d=pd.read_parquet(R+'real_windows_mm.parquet')
ctx=pd.read_parquet('train/context/out/game_context.parquet'); ctx['game_id']=ctx.game_id.astype(str)
ctx=ctx.set_index('game_id')
T=np.array(d.path_t.iloc[0])
def tds(gid):
    j=json.load(open(f'{R}espn/{gid}.json')); return sum(1 for s in j['scoringPlays'] if s.get('scoringType',{}).get('abbreviation')=='TD' or s['type'].get('abbreviation')=='TD')
def load(gid,S):
    f=f'{R}mm/{gid}/{S}.parquet'
    if not os.path.exists(f): return {}
    df=pd.read_parquet(f).sort_values('ts_ms'); o={}
    for k,g in df.groupby('strike'): o[float(k)]=(g.ts_ms.values,g.p.values,g['count'].values)
    return o
def detect(p,thr):
    n=len(p);ok=np.zeros(n,bool)
    for i in range(10,n): ok[i]=abs(p[i]-p[i-10])>=thr
    for i in range(2,n):
        if ok[i] and ok[i-1] and ok[i-2] and T[i]>=-10 and T[i]<=60: return T[i]
    return None
def signals(gid,w):
    out=[]
    for r in w.itertuples():
        p=np.array(r.path_p)
        for name,thr in (('S1',.05),('S2',.08)):
            D=detect(p,thr)
            if D is not None: out.append((name,r.wallclock_ms+int(D*1000),r.category))
        if r.category=='TD': out.append(('S3',r.wallclock_ms+DELAY,r.category))
        if r.category=='FG': out.append(('S4',r.wallclock_ms+6000,r.category))
        if r.category=='TURNOVER': out.append(('S5',r.wallclock_ms+6000,r.category))
    res=[];last={}
    for name,E,c in sorted(out,key=lambda x:x[1]):
        if name in last and E-last[name]<60000: continue
        last[name]=E;res.append((name,E,c))
    return res
def fee(C,P): return math.ceil(round(0.07*C*P*(1-P)*100,6))/100
def last_at(ts,pr,t):
    i=np.searchsorted(ts,t,side='right')-1
    return (pr[i],ts[i]) if i>=0 else (np.nan,None)
def trade(lad,E,off,exitk,sign,final_val):
    ks=sorted(lad); cand=[]
    for k in ks:
        ts,pr,ct=lad[k];p,t=last_at(ts,pr,E)
        if t is None or E-t>120000: continue
        cand.append((abs(p-.5),k))
    if not cand: return None
    cand.sort(); k0=cand[0][1]; kl=[k for _,k in cand]
    # strike offset: next strike below the median strike among strikes with live quotes
    live=sorted(kk for _,kk in cand)
    j=live.index(k0)+off
    if j<0 or j>=len(live): return None
    k=live[j]; ts,pr,ct=lad[k]
    p,_=last_at(ts,pr,E)
    pyes=p if sign>0 else 1-p
    ask=pyes+0.01
    if ask>=0.99: return None
    m=(ts>=E-60000)&(ts<=E+30000); C=int(min(100,ct[m].sum()))
    if C<5: return None
    cost=C*ask+fee(C,ask)
    if exitk is None:
        won=(final_val>k) if sign>0 else (final_val<=k)
        pnl=C*(1.0 if won else 0.0)-cost
    else:
        px,_=last_at(ts,pr,E+exitk*1000); pyx=px if sign>0 else 1-px
        bid=max(pyx-0.01,0.01)
        pnl=C*bid-fee(C,bid)-cost
    return dict(C=C,cost=cost,pnl=pnl,strike=k,ask=ask)
rows=[]
for gid,w in d.groupby('game_id'):
    gid=str(gid)
    tot=load(gid,'KXNFLTOTAL'); tdl=load(gid,'KXNFLTOTALTD')
    fin=ctx.loc[gid,'home_score']+ctx.loc[gid,'away_score']; wk=int(ctx.loc[gid,'week']); ntd=tds(gid)
    for name,E,cat in signals(gid,w):
        cells=[]
        if name=='S1': cells+= [('S1','M0',0),('S1','Mm1',-1)]
        elif name=='S3': cells+=[('S3','M0',0),('S3','Mm1',-1)]
        else: cells+=[(name,'M0',0)]
        for s,m,off in cells:
            for ex in (60,120,None):
                sign=-1 if s=='S5' else 1
                r=trade(tot,E,off,ex,sign,fin)
                rows.append(dict(game=gid,week=wk,E=E,sig=s,lad='TOT',strike_rule=m,exit=str(ex or 'S'),**(r or dict(C=0,cost=0,pnl=0,strike=np.nan,ask=np.nan))))
        if name in('S1','S3'):
            for ex in (120,None):
                r=trade(tdl,E,0,ex,1,ntd)
                rows.append(dict(game=gid,week=wk,E=E,sig=name,lad='TD',strike_rule='M0',exit=str(ex or 'S'),**(r or dict(C=0,cost=0,pnl=0,strike=np.nan,ask=np.nan))))
        if name=='S2':
            for ex in (60,120,None):
                pass
r=pd.DataFrame(rows); r['filled']=r.C>0
r.to_parquet('train/patterns/leadlag/explore_trades_%s.parquet'%sys.argv[1]+'')
