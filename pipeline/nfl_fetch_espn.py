"""Fetch ESPN scoreboards (weeks 1-6) + summaries to pipeline/out/espn/. Re-runnable; skips finished cached games."""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
from nfl_common import get
OUT=os.path.join(os.path.dirname(__file__),'out','espn'); os.makedirs(OUT,exist_ok=True)
B="https://site.api.espn.com/apis/site/v2/sports/football/nfl"
games=[]
for w in range(1,8):
    d=get(B+"/scoreboard",{"dates":2026,"seasontype":2,"week":w},rate=0.1)
    for e in (d or {}).get('events',[]):
        c=e['competitions'][0]; tm={x['homeAway']:x['team']['abbreviation'] for x in c['competitors']}
        games.append(dict(id=e['id'],date=e['date'],week=w,state=e['status']['type']['state'],home=tm['home'],away=tm['away']))
json.dump(games,open(os.path.join(OUT,'games.json'),'w'))
for g in games:
    if g['state']=='pre': continue
    p=os.path.join(OUT,g['id']+'.json')
    if os.path.exists(p) and json.load(open(p)).get('_final'): continue
    s=get(B+"/summary",{"event":g['id']},rate=0.1)
    if s:
        s['_final']=g['state']=='post'
        json.dump(s,open(p,'w'))
print(len(games), sum(g['state']=='post' for g in games),'final')
