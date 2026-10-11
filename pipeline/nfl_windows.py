"""Export Kalshi home-market price paths around plays -> real_windows.parquet (frozen 66 train games) or real_windows_today.parquet (--today).
Window set: every candidate play (TD/FG/TURNOVER/SAFETY/BIG_PLAY), every non-candidate play with |espn_wp_delta|>=0.04, and the quiet control sample.
Grid: seconds -90..+120 step 2 relative to ESPN wallclock. path_p[i] = last trade price at or before t_i (NaN before first trade);
path_n[i] = trades with ts in (t_i-2s, t_i]. Trades come from pipeline/out/trades (already pulled for whole games, so no extra API calls)."""
import os, sys, json
import numpy as np, pandas as pd
sys.path.insert(0,os.path.dirname(__file__))
import nfl_align as A
D=A.D
COLS=['game_id','play_id','wallclock_ms','category','team','home','away','period','clock','text','qtr','game_seconds_remaining','score_differential','posteam','posteam_is_home','down','ydstogo','yardline_100','home_score_pre','away_score_pre','espn_wp_delta']
T=np.arange(-90,121,2)
def make(game_ids,out,quiet_ids):
    plays=pd.read_parquet(os.path.join(D,'nfl_plays.parquet')); rows=[]
    for gid in game_ids:
        f=os.path.join(D,'trades',gid+'.parquet')
        if not os.path.exists(f): print('no trades',gid); continue
        tr=pd.read_parquet(f); ts=tr.ts_ms.values; pr=tr.p.values
        g=plays[plays.game_id==gid]
        sel=g[g.category.isin(A.CAND)|(g.espn_wp_delta.abs()>=0.04)|g.play_id.isin(quiet_ids)]
        for r in sel.itertuples():
            tt=r.wallclock_ms+T*1000
            idx=np.searchsorted(ts,tt,side='right')-1
            p=np.where(idx>=0,pr[np.clip(idx,0,None)],np.nan)
            n=np.searchsorted(ts,tt,side='right')-np.searchsorted(ts,tt-2000,side='right')
            d={c:getattr(r,c) for c in COLS}
            d['window_kind']='candidate' if r.category in A.CAND else ('wp_swing' if abs(r.espn_wp_delta or 0)>=0.04 else 'quiet')
            d['path_t']=T.tolist(); d['path_p']=p.astype('float32').tolist(); d['path_n']=n.astype('int32').tolist()
            rows.append(d)
    df=pd.DataFrame(rows); df.to_parquet(out)
    print(out,len(df),'windows'); print(df.groupby(['window_kind','category']).size())
    return df
if __name__=='__main__':
    train=json.load(open(os.path.join(D,'train_games.json')))
    if '--today' in sys.argv:
        gm=json.load(open(os.path.join(D,'game_map.json'))); ids=[g for g in gm if g not in set(train)]
        al=A.build() if False else None
        quiet=set()  # quiet sample drawn fresh below
        plays=pd.read_parquet(os.path.join(D,'nfl_plays.parquet'))
        for gid in ids:
            g=plays[(plays.game_id==gid)&(plays.category=='OTHER')&plays.down.notna()]
            k=max(5,int((plays[plays.game_id==gid].category.isin(A.CAND)).sum()//2))
            quiet|=set(g.sample(min(len(g),k),random_state=1).play_id)
        make(ids,os.path.join(D,'real_windows_today.parquet'),quiet)
    else:
        al=pd.read_parquet(os.path.join(D,'aligned_jumps.parquet'))
        make(train,os.path.join(D,'real_windows.parquet'),set(al[al.is_quiet].play_id))
