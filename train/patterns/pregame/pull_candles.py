import sys,os,json,datetime as dt
sys.path.insert(0,'/Users/faisalnabulsi/Desktop/hackathon/degen-oracle/pipeline')
from nfl_common import get, KB
from nfl_pull_trades import find_event
import pandas as pd
R='/Users/faisalnabulsi/Desktop/hackathon/degen-oracle/'
O=R+'train/patterns/pregame/candles/'; os.makedirs(O,exist_ok=True)
ev=json.load(open(R+'pipeline/out/espn2025/kalshi_events.json'))
g25=json.load(open(R+'pipeline/out/espn2025/games.json'))
gm=json.load(open(R+'pipeline/out/game_map.json'))
games=[]
for g in g25:
    e,t=find_event(g,ev)
    if t: games.append(dict(id=g['id'],date=g['date'],ticker=t,season=2025,hist=True))
for g in gm.values(): games.append(dict(id=g['id'],date=g['date'],ticker=g['ticker'],season=2026,hist=False))
print(len(games))
ts=lambda s:int(dt.datetime.fromisoformat(s.replace('Z','+00:00')).timestamp())
for i,g in enumerate(games):
    f=O+g['id']+'.json'
    if os.path.exists(f): continue
    ko=ts(g['date'])
    op=0
    url=(KB+'/historical/markets/%s/candlesticks'%g['ticker']) if g['hist'] else (KB+'/series/KXNFLGAME/markets/%s/candlesticks'%g['ticker'])
    d=get(url,{'start_ts':ko-3600*24*120,'end_ts':ko+3600,'period_interval':60},rate=0.7)
    if d is None: print('nocandles',g['id']); continue
    cs=d['candlesticks']
    json.dump(dict(g=g,open_ts=op,ko=ko,cs=cs),open(f,'w'))
    if i%20==0: print(i,len(cs),flush=True)
