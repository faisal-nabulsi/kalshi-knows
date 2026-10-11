import json,os,glob,math,sys
import numpy as np,pandas as pd
R='/Users/faisalnabulsi/Desktop/hackathon/degen-oracle/'; P=R+'train/patterns/pregame/'
ctx=pd.read_parquet(R+'train/context/out/game_context.parquet'); ctx['game_id']=ctx.game_id.astype(str)
ctx=ctx.set_index('game_id')
def f(x):
    try: return float(x)
    except: return np.nan
def pick(d,k):
    for kk in (k+'_dollars',k):
        if kk in d: return f(d[kk])
    return np.nan
rows=[]
for fn in glob.glob(P+'candles/*.json'):
    d=json.load(open(fn)); g=d['g']; ko=d['ko']; cs=d['cs']
    if g['id'] not in ctx.index: continue
    c=ctx.loc[g['id']]
    if np.isnan(c.home_win) or c.tie: continue
    ends=np.array([x['end_period_ts'] for x in cs])
    pr=np.array([pick(x['price'],'close') for x in cs]); ask=np.array([pick(x['yes_ask'],'close') for x in cs]); bid=np.array([pick(x['yes_bid'],'close') for x in cs])
    vol=np.array([f(x.get('volume_fp',x.get('volume'))) for x in cs])
    mid=np.where(np.isnan(ask)|np.isnan(bid),np.nan,(ask+bid)/2)
    pp=np.where(np.isnan(pr),mid,pr)
    def snap(t,win=6*3600):
        idx=np.where((ends<=t)&(ends>t-win)&~np.isnan(pp))[0]
        return idx[-1] if len(idx) else None
    k=snap(ko-3600)
    if k is None: continue
    vi=np.where((vol>0)&~np.isnan(pp)&(ends<=ko-3600))[0]
    po=pp[vi[0]] if len(vi) else np.nan
    i72=snap(ko-72*3600); i24=snap(ko-24*3600)
    ha=ask[k] if not np.isnan(ask[k]) else pr[k]+0.01
    hb=bid[k] if not np.isnan(bid[k]) else pr[k]-0.01
    rows.append(dict(game_id=g['id'],season=g['season'],ko=ko,Pk=pp[k],Pk_last=pr[k],home_ask=ha,home_bid=hb,vol_k=vol[k],
        Popen=po,P72=pp[i72] if i72 is not None else np.nan,P24=pp[i24] if i24 is not None else np.nan,ncand=len(cs),
        home_win=c.home_win,home=c.home,away=c.away,week=c.week,div=c.div_game,prime=c.primetime,home_rest=c.home_rest,away_rest=c.away_rest,
        roof=c.roof,away_dome=c.away_dome_team,gametime=c.gametime))
df=pd.DataFrame(rows); df.to_csv(P+'games_table.csv',index=False)
print(df.groupby('season').size(), df[['Pk','Popen','P72','P24']].isna().groupby(df.season).sum())
# Polymarket
pmh={}
for fn in glob.glob(P+'pm/*.json'):
    d=json.load(open(fn))
    if not d or not d['hist0']: continue
    h=pd.DataFrame(d['hist0']); h=h[h.t<=d['ko']-3600]
    if len(h)==0 or d['ko']-3600-h.t.iloc[-1]>3*3600: continue
    pmh[os.path.basename(fn)[:-5]]=h.p.iloc[-1]
df['pm0']=df.game_id.map(pmh)
sub=df.dropna(subset=['pm0'])
print('PM matched',len(sub), 'corr(pm token0, kalshi home)=',np.corrcoef(sub.pm0,sub.Pk)[0,1] if len(sub)>5 else None)
if len(sub)>5 and np.corrcoef(sub.pm0,sub.Pk)[0,1]<0: df['pm_home']=1-df.pm0
else: df['pm_home']=df.pm0
PAC={'DEN','ARI','LAR','LA','LAC','LV','SF','SEA'}; EAST={'BUF','MIA','NE','NYJ','NYG','PHI','WSH','WAS','BAL','PIT','CLE','CIN','CAR','ATL','JAX','TB','DET','IND'}; CEN={'CHI','GB','MIN','DAL','HOU','KC','TEN','NO'}
df['Pmid']=df.Pk
fee=lambda p:math.ceil(0.07*100*p*(1-p)*100-1e-9)/100/100  # per contract, C=100
def trade(r,side):
    if side=='H': ask=r.home_ask; win=r.home_win==1
    else: ask=1-r.home_bid; win=r.home_win==0
    if not(0.01<=ask<=0.99) or np.isnan(ask): return None
    fe=fee(ask); return dict(cost=ask+fe,pnl=float(win)-ask-fe,win=float(win),ask=ask,fee=fe,vol=r.vol_k)
def fav_side(r): return 'H' if r.Pk>=0.5 else 'A'
def dog_side(r): return 'A' if r.Pk>=0.5 else 'H'
def mv(a,b): return a-b
cells={}
def add(cid,fn): cells[cid]=fn
def toward(d): return 'H' if d>0 else 'A'
def against(d): return 'A' if d>0 else 'H'
def tot(r):  return r.Pk-r.Popen
def mid_(r): return r.P24-r.P72
def late(r): return r.Pk-r.P24
add('C1',lambda r: toward(tot(r)) if abs(tot(r))>=0.03 else None)
add('C2',lambda r: against(tot(r)) if abs(tot(r))>=0.03 else None)
add('C3',lambda r: against(mid_(r)) if abs(mid_(r))>=0.04 else None)
add('C4',lambda r: toward(late(r)) if abs(late(r))>=0.02 else None)
add('C5',lambda r: against(late(r)) if abs(late(r))>=0.02 else None)
fp=lambda r: max(r.Pk,1-r.Pk)
add('C6a',lambda r: fav_side(r) if 0.5<=fp(r)<0.65 else None)
add('C6b',lambda r: fav_side(r) if 0.65<=fp(r)<0.80 else None)
add('C6c',lambda r: fav_side(r) if fp(r)>=0.80 else None)
add('C7',lambda r:'H'); add('C8',lambda r:'A')
add('C9',lambda r: dog_side(r) if r.div==1 else None)
add('C10',lambda r: dog_side(r) if r.prime==1 else None)
def c11(r):
    if r.home_rest<=6 and r.away_rest>=r.home_rest+3: return 'A'
    if r.away_rest<=6 and r.home_rest>=r.away_rest+3: return 'H'
add('C11',c11)
add('C12',lambda r:'H' if (r.away in PAC and r.home in EAST|CEN and r.gametime=='13:00') else None)
add('C13',lambda r:'H' if (r.roof in('outdoors','open') and r.away_dome==1) else None)
add('C14',lambda r:'A' if r.Pk<0.5 else None)
add('C15',lambda r:'H' if r.Pk<0.5 else None)
def c16(r,s):
    if np.isnan(r.pm_home): return None
    d=r.pm_home-r.Pk
    if abs(d)<0.03: return None
    hi='H' if d>0 else 'A'
    return hi if s==1 else ('A' if hi=='H' else 'H')
add('C16',lambda r:c16(r,1)); add('C17',lambda r:c16(r,-1))
rng=np.random.default_rng(7)
def stats(T):
    if len(T)==0: return dict(n=0)
    c=np.array([t['cost'] for t in T]); p=np.array([t['pnl'] for t in T]); w=np.array([t['win'] for t in T])
    roi=p.sum()/c.sum(); n=len(T)
    idx=rng.integers(0,n,(5000,n)); b=p[idx].sum(1)/c[idx].sum(1)
    return dict(n=n,roi=roi,lo=np.percentile(b,2.5),hi=np.percentile(b,97.5),p1=float((b<=0).mean()),hit=w.mean(),avg_ask=np.mean([t['ask'] for t in T]),pnl=p.sum()/len(T)*100,
                n_liq=int(sum(t['vol']>=500 for t in T)),fee_c=np.mean([t['fee'] for t in T])*100)
res={}
for cid,fn in cells.items():
    for s in (2025,2026):
        T=[]
        for r in df[df.season==s].itertuples():
            try: sd=fn(pd.Series(r._asdict()) if False else r)
            except Exception: sd=None
            if sd is None or (isinstance(sd,float) and np.isnan(sd)): continue
            t=trade(r,sd)
            if t: T.append(t)
        res[(cid,s)]=stats(T)
        if len(T)>0 and s==2025: pass
out=[]
for cid in cells:
    a=res[(cid,2025)]; b=res[(cid,2026)]
    passed= a.get('n',0)>=30 and a.get('roi',-1)>0 and a.get('p1',1)<0.05
    out.append(dict(cell=cid,n25=a.get('n',0),roi25=a.get('roi'),lo25=a.get('lo'),hi25=a.get('hi'),p25=a.get('p1'),hit25=a.get('hit'),avgask25=a.get('avg_ask'),
        passed=passed,n26=b.get('n',0),roi26=b.get('roi'),lo26=b.get('lo'),hi26=b.get('hi'),p26=b.get('p1'),hit26=b.get('hit'),avgask26=b.get('avg_ask'),liq26=b.get('n_liq'),liq25=a.get('n_liq')))
O=pd.DataFrame(out)
def bh(p,q=0.10):
    p=np.array(p,float); m=len(p); o=np.argsort(p); r=np.empty(m,bool); r[:]=False
    k=0
    for i,j in enumerate(o):
        if p[j]<=q*(i+1)/m: k=i+1
    r[o[:k]]=True; return r
# cells with no 2026 trades get p=1
p26=np.where(O.passed & (O.n26>0), O.p26.fillna(1), 1.0)
O['p26_used']=p26; O['bh26']=bh(p26); O['bh25']=bh(O.p25.fillna(1))
O['survive']=O.passed & (O.roi26>0) & O.bh26
pd.set_option('display.width',250); pd.set_option('display.max_columns',40)
print(O.round(3).to_string())
O.to_csv(P+'cells.csv',index=False)
# descriptive calibration
def logit(p): p=np.clip(p,0.01,0.99); return np.log(p/(1-p))
def fitlog(X,y,iters=50):
    X=np.column_stack([np.ones(len(X)),X]); b=np.zeros(X.shape[1])
    for _ in range(iters):
        pr=1/(1+np.exp(-X@b)); W=pr*(1-pr); H=X.T@(X*W[:,None])+1e-9*np.eye(X.shape[1]); b=b+np.linalg.solve(H,X.T@(y-pr))
    pr=1/(1+np.exp(-X@b)); cov=np.linalg.inv(X.T@(X*(pr*(1-pr))[:,None])); return b,np.sqrt(np.diag(cov))
desc=[]
for s in (2025,2026,'all'):
    d=df if s=='all' else df[df.season==s]
    y=d.home_win.values
    b,se=fitlog(logit(d.Pk.values),y)
    line=f'{s}: n={len(d)} slope={b[1]:.3f}+-{1.96*se[1]:.3f} intercept={b[0]:.3f}+-{1.96*se[0]:.3f} Brier Pk={np.mean((d.Pk-y)**2):.4f}'
    for c in ('Popen','P72','P24'):
        dd=d.dropna(subset=[c,'Pk']); line+=f' | {c}: n={len(dd)} Brier {c}={np.mean((dd[c]-dd.home_win)**2):.4f} vs Pk same rows {np.mean((dd.Pk-dd.home_win)**2):.4f}'
    dd=d.dropna(subset=['Popen']); 
    if len(dd)>20:
        X=np.column_stack([logit(dd.Pk.values),logit(dd.Pk.values)-logit(dd.Popen.values)]); bb,ss=fitlog(X,dd.home_win.values)
        line+=f' | logit regress: coef Pk={bb[1]:.3f}+-{1.96*ss[1]:.3f}, drift={bb[2]:.3f}+-{1.96*ss[2]:.3f}'
    desc.append(line)
print('\n'.join(desc))
# reliability by bucket on favorite side
d=df.copy(); d['fav']=np.where(d.Pk>=0.5,d.Pk,1-d.Pk); d['favwin']=np.where(d.Pk>=0.5,d.home_win,1-d.home_win)
d['bk']=pd.cut(d.fav,[0.5,0.6,0.7,0.8,0.9,1.0])
rel=d.groupby(['season','bk'],observed=True).agg(n=('fav','size'),mean_price=('fav','mean'),win_rate=('favwin','mean')).round(3)
print(rel)
rel.to_csv(P+'reliability.csv')
# decile home reliability pooled
d['dec']=pd.qcut(d.Pk,10,duplicates='drop'); r2=d.groupby('dec',observed=True).agg(n=('Pk','size'),mean_p=('Pk','mean'),win=('home_win','mean')).round(3); print(r2)
open(P+'desc.txt','w').write('\n'.join(desc)+'\n\n'+rel.to_string()+'\n\n'+r2.to_string())
print('PM n',df.pm_home.notna().groupby(df.season).sum().to_dict())
