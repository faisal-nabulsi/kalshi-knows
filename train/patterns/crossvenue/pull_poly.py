import json,glob,os,time,sys,requests,datetime as dt,threading,queue
R='/Users/faisalnabulsi/Desktop/hackathon/degen-oracle/'
OUT=R+'train/patterns/crossvenue/data/'
games={}
for d in ('espn2025','espn'):
    for f in glob.glob(R+f'pipeline/out/{d}/*.json'):
        gid=os.path.basename(f)[:-5]
        try:
            c=json.load(open(f))['header']['competitions'][0]
        except Exception: continue
        h=[x for x in c['competitors'] if x['homeAway']=='home'][0]; a=[x for x in c['competitors'] if x['homeAway']=='away'][0]
        games[gid]=dict(date=c['date'],home=h['team']['abbreviation'],away=a['team']['abbreviation'],hs=h.get('score'),as_=a.get('score'),season=d)
json.dump(games,open(OUT+'games.json','w'))
have=set(os.listdir(R+'pipeline/out/trades'))|set(os.listdir(R+'pipeline/out/w2025'))
S=requests.Session(); last={}
def get(url,host):
    w=1.1-(time.time()-last.get(host,0))
    if w>0: time.sleep(w)
    last[host]=time.time()
    for i in range(4):
        try:
            r=S.get(url,timeout=30)
            if r.status_code==200: return r.json()
            if r.status_code==429: time.sleep(5)
        except Exception as e: time.sleep(2)
    return None
ALT={'WSH':['wsh','was'],'JAX':['jax','jac'],'LV':['lv','lvr','las'],'LAR':['lar','la'],'LAC':['lac'],'NO':['no','nor'],'NE':['ne','nwe'],'TB':['tb','tam'],'GB':['gb','gnb'],'KC':['kc','kan'],'SF':['sf','sfo']}
def ab(x): return ALT.get(x,[x.lower()])
from zoneinfo import ZoneInfo
Q=queue.Queue()
def clobw():
    while True:
        gid,tok,start=Q.get()
        if gid is None: break
        j=get(f"https://clob.polymarket.com/prices-history?market={tok}&startTs={start-1800}&endTs={start+5*3600+3600}&fidelity=1",'c')
        json.dump({0:(j or {}).get('history',[])},open(OUT+f'pclob_{gid}.json','w'))
th=threading.Thread(target=clobw); th.start()
done=json.load(open(OUT+'poly_index.json')) if os.path.exists(OUT+'poly_index.json') else {}
for gid,g in sorted(games.items(), key=lambda kv: (kv[1]['season']!='espn', kv[1]['date'])):
    if (gid in done and os.path.exists(OUT+f'pclob_{gid}.json')) or gid+'.parquet' not in have: continue
    t=dt.datetime.fromisoformat(g['date'].replace('Z','+00:00')); et=t.astimezone(ZoneInfo('America/New_York')).date()
    ev=None
    for dd in (et, et-dt.timedelta(1), et+dt.timedelta(1)):
        for a in ab(g['away']):
            for h in ab(g['home']):
                j=get(f"https://gamma-api.polymarket.com/events?slug=nfl-{a}-{h}-{dd}",'g')
                if j: ev=j[0]; break
            if ev: break
        if ev: break
    if not ev: done[gid]=None; print(gid,g['away'],g['home'],'NOEVENT',flush=True); json.dump(done,open(OUT+'poly_index.json','w')); continue
    ml=[m for m in ev['markets'] if m.get('sportsMarketType')=='moneyline'] or ev['markets'][:1]
    m=ml[0]; outs=json.loads(m['outcomes']); toks=json.loads(m['clobTokenIds'])
    # which outcome is home? title order away vs home per slug; map by team name in outcomes
    done[gid]=dict(slug=ev['slug'],outs=outs,toks=toks,cond=m['conditionId'],vol=m.get('volume'),title=ev['title'])
    start=int(t.timestamp()); trades=[]; off=0
    while True:
        j=get(f"https://data-api.polymarket.com/trades?market={m['conditionId']}&limit=1000&offset={off}",'d')
        if not j: break
        trades+=j
        if len(j)<1000 or min(x['timestamp'] for x in j)<start-1800 or off>=5000: break
        off+=1000
    import pandas as pd
    pd.DataFrame([dict(ts=x['timestamp'],side=x['side'],outcome=x['outcome'],idx=x['outcomeIndex'],price=x['price'],size=x['size']) for x in trades]).to_parquet(OUT+f'ptrades_{gid}.parquet')
    Q.put((gid,toks[0],start)); ph={0:[]}
    json.dump(done,open(OUT+'poly_index.json','w'))
    print(gid,g['away'],g['home'],ev['slug'],len(trades),len(ph[0]),flush=True)

Q.put((None,None,None)); th.join()
