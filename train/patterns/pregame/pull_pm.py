import json,os,time,datetime as dt,httpx
R='/Users/faisalnabulsi/Desktop/hackathon/degen-oracle/'
O=R+'train/patterns/pregame/pm/'; os.makedirs(O,exist_ok=True)
g25=json.load(open(R+'pipeline/out/espn2025/games.json')); gm=json.load(open(R+'pipeline/out/game_map.json'))
games=[(g['id'],g['date'],g['home'],g['away']) for g in g25]+[(g['id'],g['date'],g['home'],g['away']) for g in gm.values()]
AL={'WSH':['wsh','was'],'JAX':['jax','jac'],'LAR':['lar','la'],'LV':['lv','lvr','oak'],'LAC':['lac'],'NE':['ne','nwe'],'NO':['no','nor'],'SF':['sf','sfo'],'TB':['tb','tam'],'GB':['gb','gnb'],'KC':['kc','kan']}
al=lambda a:AL.get(a,[a.lower()])
cl=httpx.Client(timeout=30,headers={'User-Agent':'Mozilla/5.0'})
last=[0]
def get(u,p=None):
    for i in range(5):
        w=last[0]+1.05-time.time()
        if w>0: time.sleep(w)
        last[0]=time.time()
        try: r=cl.get(u,params=p)
        except Exception: time.sleep(2); continue
        if r.status_code==200: return r.json()
        if r.status_code==429: time.sleep(5); continue
        return None
for i,(gid,date,h,a) in enumerate(games):
    f=O+gid+'.json'
    if os.path.exists(f): continue
    ko=dt.datetime.fromisoformat(date.replace('Z','+00:00'))
    res=None
    for dd in (0,-1,1):
        d=(ko-dt.timedelta(hours=5)+dt.timedelta(days=dd)).strftime('%Y-%m-%d')
        for aa in al(a):
            for hh in al(h):
                r=get('https://gamma-api.polymarket.com/events',{'slug':f'nfl-{aa}-{hh}-{d}'})
                if r:
                    res=r[0]; break
            if res: break
        if res: break
    if not res: json.dump(None,open(f,'w')); continue
    m=res['markets'][0]
    outs=json.loads(m['outcomes']); toks=json.loads(m['clobTokenIds'])
    ko_ts=int(ko.timestamp())
    h_=get('https://clob.polymarket.com/prices-history',{'market':toks[0],'startTs':ko_ts-3600*24*14,'endTs':ko_ts+3600,'fidelity':60})
    json.dump(dict(slug=res['slug'],outs=outs,hist0=(h_ or {}).get('history',[]),ko=ko_ts),open(f,'w'))
    if i%20==0: print(i,res['slug'],len((h_ or {}).get('history',[])),flush=True)
