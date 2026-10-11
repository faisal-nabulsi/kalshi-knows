"""Build real_windows_2025.parquet (2025 NFL season, same schema as real_windows.parquet + season=2025).
ESPN 2025 -> out/espn2025/; Kalshi settled KXNFLGAME; trades pulled only in windows around candidate/swing/quiet plays.
Reverse-chronological, resumable (per-game cache in out/w2025/), rewrites output every 20 games. Stops at --stop HH:MM local."""
import sys, os, json, datetime as dt, time
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
from nfl_common import get, KB
import nfl_build_plays as bp
from nfl_pull_trades import find_event
def pull(ticker,lo,hi):
    # pre-2026-08-12 trades live under /historical/trades (public)
    rows=[];cur=None
    while True:
        p={"ticker":ticker,"limit":1000,"min_ts":lo,"max_ts":hi}
        if cur:p['cursor']=cur
        d=get(KB+"/historical/trades",p)
        if d is None: return None
        for t in d['trades']:
            rows.append((int(round(dt.datetime.fromisoformat(t['created_time'].replace('Z','+00:00')).timestamp()*1000)),float(t['yes_price_dollars']),float(t['count_fp']),t['taker_side']))
        cur=d.get('cursor')
        if not cur or not d['trades']: break
    return pd.DataFrame(rows,columns=['ts_ms','p','count','taker']).sort_values('ts_ms').reset_index(drop=True)
from nfl_windows import COLS, T
CAND={'TD','FG','TURNOVER','SAFETY','BIG_PLAY'}
D=os.path.join(os.path.dirname(__file__),'out'); E=os.path.join(D,'espn2025'); W=os.path.join(D,'w2025')
os.makedirs(E,exist_ok=True); os.makedirs(W,exist_ok=True); os.makedirs(os.path.join(D,'_e25'),exist_ok=True)
lk=os.path.join(D,'_e25','espn')
if not os.path.lexists(lk): os.symlink(E,lk)
bp.D=os.path.join(D,'_e25')
B="https://site.api.espn.com/apis/site/v2/sports/football/nfl"
OUT=os.path.join(D,'real_windows_2025.parquet')
def games():
    f=os.path.join(E,'games.json')
    if os.path.exists(f): return json.load(open(f))
    gs=[]
    for st,wks in ((2,range(1,19)),(3,range(1,6))):
        for w in wks:
            d=get(B+"/scoreboard",{"dates":2025,"seasontype":st,"week":w},rate=0.1)
            for e in (d or {}).get('events',[]):
                c=e['competitions'][0]; tm={x['homeAway']:x['team']['abbreviation'] for x in c['competitors']}
                gs.append(dict(id=e['id'],date=e['date'],week=w,stype=st,state=e['status']['type']['state'],home=tm['home'],away=tm['away']))
    json.dump(gs,open(f,'w')); return gs
def events():
    f=os.path.join(E,'kalshi_events.json')
    if os.path.exists(f): return json.load(open(f))
    ev={};cur=None
    while True:
        p={"series_ticker":"KXNFLGAME","status":"settled","with_nested_markets":"true","limit":200}
        if cur:p['cursor']=cur
        d=get(KB+"/events",p)
        if not d: break
        for e in d['events']: ev[e['event_ticker']]=[m['ticker'] for m in e.get('markets',[])]
        cur=d.get('cursor')
        if not cur or not d['events']: break
    for k in [k for k,v in ev.items() if not v]:
        d=get(KB+"/historical/markets",{"event_ticker":k})
        ev[k]=[m['ticker'] for m in (d or {}).get('markets',[])]
    json.dump(ev,open(f,'w')); return ev
def do_game(g):
    plays=pd.DataFrame(bp.build_game(g['id'])).dropna(subset=['wallclock_ms']); plays['wallclock_ms']=plays.wallclock_ms.astype('int64')
    cand=plays.category.isin(CAND); swing=~cand&(plays.espn_wp_delta.abs()>=0.04)
    pool=plays[(plays.category=='OTHER')&plays.down.notna()&~swing]
    q=pool.sample(min(len(pool),max(5,int(cand.sum()))),random_state=1)
    sel=pd.concat([plays[cand|swing],q]).sort_values('wallclock_ms')
    rng=sorted((int(w//1000)-100,int(w//1000)+130) for w in sel.wallclock_ms)
    mer=[]
    for lo,hi in rng:
        if mer and lo<=mer[-1][1]: mer[-1][1]=max(mer[-1][1],hi)
        else: mer.append([lo,hi])
    parts=[]
    for lo,hi in mer:
        df=pull(g['ticker'],lo,hi)
        if df is None: return None
        parts.append(df)
    tr=pd.concat(parts).drop_duplicates().sort_values('ts_ms').reset_index(drop=True)
    ts=tr.ts_ms.values; pr=tr.p.values; qids=set(q.play_id); rows=[]
    for r in sel.itertuples():
        tt=r.wallclock_ms+T*1000
        idx=np.searchsorted(ts,tt,side='right')-1
        p=np.where(idx>=0,pr[np.clip(idx,0,None)] if len(pr) else np.nan,np.nan)
        n=np.searchsorted(ts,tt,side='right')-np.searchsorted(ts,tt-2000,side='right')
        d={c:getattr(r,c) for c in COLS}
        d['window_kind']='candidate' if r.category in CAND else ('wp_swing' if r.play_id not in qids else 'quiet')
        d['path_t']=T.tolist(); d['path_p']=p.astype('float32').tolist(); d['path_n']=n.astype('int32').tolist()
        d['season']=2025; d['week']=g['week']; d['stype']=g['stype']
        rows.append(d)
    return pd.DataFrame(rows)
def write():
    fs=[os.path.join(W,f) for f in os.listdir(W) if f.endswith('.parquet')]
    if fs: pd.concat([pd.read_parquet(f) for f in fs],ignore_index=True).drop(columns=['week','stype']).to_parquet(OUT); 
    return len(fs)
if __name__=='__main__':
    stop=sys.argv[sys.argv.index('--stop')+1] if '--stop' in sys.argv else '12:55'
    hh,mm=map(int,stop.split(':'))
    gs=[g for g in games() if g['state']=='post']; print(len(gs),'final ESPN games',flush=True)
    for g in gs:
        p=os.path.join(E,g['id']+'.json')
        if not os.path.exists(p):
            s=get(B+"/summary",{"event":g['id']},rate=0.1)
            if s: json.dump(s,open(p,'w'))
    ev=events(); print(len(ev),'kalshi settled events',flush=True)
    todo=[]
    for g in sorted(gs,key=lambda g:g['date'],reverse=True):
        e,t=find_event(g,ev)
        if not e: print('NO MARKET',g['id'],g['date'][:10],g['away'],g['home']); continue
        g['event'],g['ticker']=e,t; todo.append(g)
    print(len(todo),'games with market',flush=True); k=0
    for g in todo:
        if dt.datetime.now().replace(hour=hh,minute=mm,second=0)<=dt.datetime.now(): print('deadline'); break
        f=os.path.join(W,g['id']+'.parquet')
        if os.path.exists(f): continue
        try: df=do_game(g)
        except Exception as ex: print('err',g['id'],ex,flush=True); continue
        if df is None: print('fail',g['id'],flush=True); continue
        df.to_parquet(f); k+=1; print(g['id'],g['event'],len(df),df.window_kind.value_counts().to_dict(),flush=True)
        if k%20==0: print('wrote',write(),'games',flush=True)
    print('final',write(),'games')
