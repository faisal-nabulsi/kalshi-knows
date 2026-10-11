"""Map ESPN games to Kalshi KXNFLGAME events and pull in-game home-market trades to pipeline/out/trades/<game_id>.parquet.
Usage: nfl_pull_trades.py [--max N]   (ordered by ESPN win-prob drama; skips games already pulled)"""
import sys, os, json, datetime as dt
sys.path.insert(0, os.path.dirname(__file__))
from nfl_common import get, KB
import pandas as pd
D=os.path.join(os.path.dirname(__file__),'out'); T=os.path.join(D,'trades'); os.makedirs(T,exist_ok=True)
ALIAS={'WSH':['WSH','WAS'],'JAX':['JAX','JAC'],'LAR':['LAR','LA'],'LV':['LV','LVR'],'NE':['NE','NWE'],'NO':['NO','NOR'],'SF':['SF','SFO'],'TB':['TB','TAM'],'GB':['GB','GNB'],'KC':['KC','KAN']}
def al(a): return ALIAS.get(a,[a])
def load_events():
    ev={}; cur=None
    while True:
        p={"series_ticker":"KXNFLGAME","limit":1000}
        if cur:p['cursor']=cur
        d=get(KB+"/markets",p); 
        for m in d['markets']: ev.setdefault(m['event_ticker'],[]).append(m['ticker'])
        cur=d.get('cursor')
        if not cur or not d['markets']: break
    return ev
def find_event(g,ev):
    t0=dt.datetime.fromisoformat(g['date'].replace('Z','+00:00'))
    for dd in (0,-1,1):
        d=(t0+dt.timedelta(days=dd)).strftime('%y%b%d').upper()
        for a in al(g['away']):
            for h in al(g['home']):
                e=f"KXNFLGAME-{d}{a}{h}"
                if e in ev:
                    hm=[t for t in ev[e] if t.split('-')[-1]==h]
                    if hm: return e,hm[0]
    return None,None
def drama(gid):
    try: s=json.load(open(os.path.join(D,'espn',gid+'.json')))
    except Exception: return 0
    w=[x['homeWinPercentage'] for x in s.get('winprobability',[])]
    return sum(abs(b-a) for a,b in zip(w,w[1:]))
def gamespan(gid):
    s=json.load(open(os.path.join(D,'espn',gid+'.json')))
    ts=[p['wallclock'] for d in s['drives']['previous'] for p in d['plays'] if p.get('wallclock')]
    f=lambda x:int(dt.datetime.fromisoformat(x.replace('Z','+00:00')).timestamp())
    return min(map(f,ts)),max(map(f,ts))
def pull(ticker,lo,hi):
    rows=[];cur=None
    while True:
        p={"ticker":ticker,"limit":1000,"min_ts":lo,"max_ts":hi}
        if cur:p['cursor']=cur
        d=get(KB+"/markets/trades",p)
        if d is None: return None
        for t in d['trades']:
            rows.append((int(dt.datetime.fromisoformat(t['created_time'].replace('Z','+00:00')).timestamp()*1000+0.5) if False else
              int(round(dt.datetime.fromisoformat(t['created_time'].replace('Z','+00:00')).timestamp()*1000)),
              float(t['yes_price_dollars']),float(t['count_fp']),t['taker_side']))
        cur=d.get('cursor')
        if not cur or not d['trades']: break
    return pd.DataFrame(rows,columns=['ts_ms','p','count','taker']).sort_values('ts_ms').reset_index(drop=True)
if __name__=='__main__':
    mx=int(sys.argv[sys.argv.index('--max')+1]) if '--max' in sys.argv else 999
    games=[g for g in json.load(open(os.path.join(D,'espn','games.json'))) if g['state']=='post']
    ev=load_events(); mp={}
    for g in games:
        e,t=find_event(g,ev)
        if e: g['event'],g['ticker']=e,t; mp[g['id']]=g
        else: print('NO KALSHI MATCH',g)
    json.dump(mp,open(os.path.join(D,'game_map.json'),'w'))
    todo=[g for g in sorted(mp.values(),key=lambda g:-drama(g['id'])) if not os.path.exists(os.path.join(T,g['id']+'.parquet'))][:mx]
    from concurrent.futures import ThreadPoolExecutor
    def job(g):
        lo,hi=gamespan(g['id'])
        df=pull(g['ticker'],lo-900,hi+600)
        if df is None: print('fail',g['id'],flush=True); return
        df.to_parquet(os.path.join(T,g['id']+'.parquet')); print(g['id'],g['event'],len(df),flush=True)
    with ThreadPoolExecutor(4) as ex: list(ex.map(job,todo))
