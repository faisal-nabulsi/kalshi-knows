import pandas as pd,numpy as np
d=pd.read_parquet('pipeline/out/real_windows_mm.parquet')
T=np.array(d.path_t.iloc[0]); i0=np.searchsorted(T,-10)
out=[]
def half(curve,T):
    # first time after 0 where curve reaches half of its value at +120 (needs final>0 in magnitude)
    fin=curve[-1]
    if abs(fin)<1e-9: return np.nan
    f=curve/fin
    idx=np.where((T>=0)&(f>=0.5))[0]
    return T[idx[0]] if len(idx) else np.nan
for cat in ['TD','FG','TURNOVER','BIG_PLAY','OTHER']:
    s=d[(d.category==cat)&d.pts_local_path.notna()]
    sgn=np.where(s.posteam_is_home.astype(str)=='True',1,-1)
    W=np.array([np.array(x) for x in s.path_p])*sgn[:,None]
    P=np.array([np.array(x) for x in s.pts_local_path]); Q=np.array([np.array(x) for x in s.td_local_path if x is not None]) if s.td_local_path.notna().all() else None
    dw=W-W[:,[i0]]; dp=P-P[:,[i0]]
    md_w=np.median(dw,0); md_p=np.median(dp,0)
    row={'cat':cat,'n':len(s)}
    for t in [0,6,10,20,30,60,120]:
        j=np.searchsorted(T,t); row[f'wp{t}']=round(md_w[j],3); row[f'pts{t}']=round(md_p[j],2)
    row['wp_half_s']=half(md_w,T); row['pts_half_s']=half(md_p,T)
    # per-window half-adjust medians
    hw=[half(a,T) for a in dw]; hp=[half(a,T) for a in dp]
    row['wp_half_med']=np.nanmedian(hw); row['pts_half_med']=np.nanmedian(hp)
    out.append(row)
print(pd.DataFrame(out).T.to_string())
# cross-correlation of 2s changes, all windows with pts_local, using TD+FG+TURNOVER+BIG
s=d[d.pts_local_path.notna()&d.category.isin(['TD','FG','TURNOVER','BIG_PLAY'])]
sgn=np.where(s.posteam_is_home.astype(str)=='True',1,-1)
W=np.array([np.array(x) for x in s.path_p])*sgn[:,None];P=np.array([np.array(x) for x in s.pts_local_path])
dW=np.diff(W,axis=1);dP=np.diff(P,axis=1)
# restrict to -10..+60 
m=(T[1:]>=-10)&(T[1:]<=60)
res=[]
for lag in range(-5,16):  # lag>0: pts change lags wp change by lag*2s
    a=[];b=[]
    for i in range(len(dW)):
        x=dW[i][m]; y=np.roll(dP[i],-lag)[m]
        a.append(x);b.append(y)
    a=np.concatenate(a);b=np.concatenate(b)
    res.append((lag*2,round(np.corrcoef(a,b)[0,1],3)))
print('xcorr (s: pts change lags wp by +s):',res)
