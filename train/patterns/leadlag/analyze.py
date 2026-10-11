import pandas as pd,numpy as np
r=pd.read_parquet('train/patterns/leadlag/trades.parquet')
rng=np.random.default_rng(7)
def boot(df,B=10000):
    g=df.groupby('game')[['pnl','cost']].sum(); P=g.pnl.values;Cc=g.cost.values;n=len(g)
    if n==0 or Cc.sum()==0: return np.nan,np.nan,np.nan,np.nan
    roi=P.sum()/Cc.sum(); idx=rng.integers(0,n,(B,n)); b=P[idx].sum(1)/np.maximum(Cc[idx].sum(1),1e-9)
    return roi,np.percentile(b,2.5),np.percentile(b,97.5),(b<=0).mean()
keys=['lad','sig','strike_rule','exit']; rows=[]
for k,g in r.groupby(keys):
    f=g[g.filled]; dis=f[f.week<=3]; te=f[f.week>=4]
    roi,lo,hi,p=boot(dis); n=len(dis)
    passed=(n>=30) and roi>0 and p<0.10
    row=dict(zip(keys,k),signals=len(g),disc_n=n,disc_games=dis.game.nunique(),disc_roi=roi,disc_lo=lo,disc_hi=hi,disc_p=p,passed=passed,
        fill_rate=len(f)/len(g),med_C=f.C.median(),med_ask=f.ask.median())
    troi,tlo,thi,tp=boot(te); row.update(test_n=len(te),test_games=te.game.nunique(),test_roi=troi,test_lo=tlo,test_hi=thi,test_p=tp)
    row['test_p_used']=tp if passed and len(te)>0 else 1.0
    row['test_roi_shown_only_if_passed']=troi if passed else np.nan
    rows.append(row)
t=pd.DataFrame(rows); m=len(t)
# BH q=.10 over all cells
o=np.argsort(t.test_p_used.values); ps=t.test_p_used.values[o]; thr=0.10*np.arange(1,m+1)/m
k=np.where(ps<=thr)[0]; kmax=k.max()+1 if len(k) else 0
rej=np.zeros(m,bool); rej[o[:kmax]]=True
t['bh_reject']=rej; t['survives']=rej&(t.test_roi>0)&(t.test_n>=15)
t.to_csv('train/patterns/leadlag/cells.csv',index=False)
pd.set_option('display.width',250); pd.set_option('display.max_columns',40)
print(m,'cells');print(t.round(3).to_string())
