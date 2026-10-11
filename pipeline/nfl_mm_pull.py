"""Pull same-game multi-market trade tapes (KXNFLTOTAL, KXNFLTOTALTD, KXNFLANYTD) -> pipeline/out/mm/<game_id>/<series>.parquet
Columns: ticker, strike (floor_strike), label (yes_sub_title), ts_ms, p, count. Usage: nfl_mm_pull.py [--today] [--max N]"""
import sys, os, json, datetime as dt
sys.path.insert(0, os.path.dirname(__file__))
from nfl_common import get, KB
import nfl_pull_trades as P
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
SERIES=['KXNFLTOTAL','KXNFLTOTALTD','KXNFLTD']  # KXNFLANYTD only has 2025-26 playoff events with no markets; KXNFLTD is the 2026 anytime-TD-scorer series
D=P.D; O=os.path.join(D,'mm'); os.makedirs(O,exist_ok=True)
def load_series(S):
    ev={};cur=None
    while True:
        p={"series_ticker":S,"limit":1000,"min_close_ts":1788000000}
        if cur:p['cursor']=cur
        d=get(KB+"/markets",p)
        for m in d['markets']: ev.setdefault(m['event_ticker'],[]).append(m)
        cur=d.get('cursor')
        if not cur or not d['markets']: break
    return ev
def pull_market(m,lo,hi):
    df=P.pull(m['ticker'],lo,hi)
    if df is None or df.empty: return None
    df['ticker']=m['ticker']; df['strike']=m.get('floor_strike'); df['label']=m.get('yes_sub_title'); return df
def find(g,evs):
    t0=dt.datetime.fromisoformat(g['date'].replace('Z','+00:00'))
    for dd in (0,-1,1):
        d=(t0+dt.timedelta(days=dd)).strftime('%y%b%d').upper()
        for a in P.al(g['away']):
            for h in P.al(g['home']):
                for S,ev in evs.items():
                    pass
                return_key=f"{d}{a}{h}"
                if any(k.endswith(return_key) for k in evs['KXNFLTOTAL']): return return_key
    return None
if __name__=='__main__':
    mx=int(sys.argv[sys.argv.index('--max')+1]) if '--max' in sys.argv else 999
    gm=json.load(open(os.path.join(D,'game_map.json'))); train=set(json.load(open(os.path.join(D,'train_games.json'))))
    ids=[g for g in gm if (g not in train)==('--today' in sys.argv)]
    evs={S:load_series(S) for S in SERIES}
    jobs=[]
    for gid in ids[:mx]:
        key=find(gm[gid],evs)
        if not key: print('no mm event',gid); continue
        lo,hi=P.gamespan(gid); lo-=300; hi+=120
        for S in SERIES:
            f=os.path.join(O,gid,S+'.parquet')
            if os.path.exists(f): continue
            ms=evs[S].get(f"{S}-{key}",[])
            jobs.append((gid,S,ms,lo,hi))
    jobs.sort(key=lambda j:(j[1]=='KXNFLTD'))  # ladders first, scorer markets last
    def job(j):
        gid,S,ms,lo,hi=j; os.makedirs(os.path.join(O,gid),exist_ok=True)
        dfs=[x for m in ms if (x:=pull_market(m,lo,hi)) is not None]
        pd.concat(dfs).to_parquet(os.path.join(O,gid,S+'.parquet')) if dfs else pd.DataFrame(columns=['ticker','strike','label','ts_ms','p','count','taker']).to_parquet(os.path.join(O,gid,S+'.parquet'))
        print(gid,S,len(ms),sum(len(x) for x in dfs),flush=True)
    with ThreadPoolExecutor(4) as ex: list(ex.map(job,jobs))
