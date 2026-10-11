"""Build pipeline/out/nfl_plays.parquet from cached ESPN summaries (all final games)."""
import os, json, datetime as dt
import pandas as pd
D=os.path.join(os.path.dirname(__file__),'out')
SCRIM={'Rush','Pass Reception','Pass Incompletion','Sack','Passing Touchdown','Rushing Touchdown'}
TOTYPES={'Pass Interception Return','Fumble Recovery (Opponent)','Sack Opp Fumble Recovery','Muffed Punt Recovery (Opponent)'}
def ms(x): return int(dt.datetime.fromisoformat(x.replace('Z','+00:00')).timestamp()*1000)
def secs(c): m,s=c.split(':'); return int(m)*60+int(s)
def build_game(gid):
    s=json.load(open(os.path.join(D,'espn',gid+'.json')))
    comp=s['header']['competitions'][0]
    ids={c['team']['id']:c['team']['abbreviation'] for c in comp['competitors']}
    home=[c['team']['abbreviation'] for c in comp['competitors'] if c['homeAway']=='home'][0]
    away=[c['team']['abbreviation'] for c in comp['competitors'] if c['homeAway']=='away'][0]
    raw=[(p,d) for d in s['drives']['previous'] for p in d['plays']]
    raw.sort(key=lambda x:int(x[0]['sequenceNumber']))
    wl=s.get('winprobability',[]); wpd={}
    for a,b in zip([None]+wl[:-1],wl):
        wpd[b['playId']]=(b['homeWinPercentage'],b['homeWinPercentage']-(a['homeWinPercentage'] if a else 0.5))
    rows=[];ph=pa=0;prev_clock={};
    for i,(p,d) in enumerate(raw):
        t=p['type']['text']; per=p['period']['number']; clk=p['clock']['displayValue']
        hs,as_=p['homeScore'],p['awayScore']
        dh,da=hs-ph,as_-pa
        st=p.get('start',{}) or {}; en=p.get('end',{}) or {}
        pos=ids.get(str((st.get('team') or {}).get('id')))
        yds=p.get('statYardage') or 0
        cat='OTHER';team=pos
        if p['scoringPlay']:
            stype=(p.get('scoringType') or {}).get('name')
            if stype=='touchdown' or dh>=6 or da>=6:
                cat='TD'; team=home if dh>da else away
            elif stype=='field-goal': cat='FG'; team=home if dh>da else away
            elif stype=='safety': cat='SAFETY'; team=home if dh>da else away
        elif t in TOTYPES or p.get('isTurnover') and t not in ('Blocked Field Goal','Blocked Punt'):
            cat='TURNOVER'; team=away if pos==home else home
        elif t in SCRIM and st.get('down')==4 and t!='Punt':
            # turnover on downs: next real play belongs to the other team without a punt/FG between
            for q,_ in raw[i+1:i+4]:
                qt=q['type']['text']
                if qt in ('Penalty','Timeout','Official Timeout','Two-minute warning','End Period'): continue
                qp=ids.get(str(((q.get('start') or {}).get('team') or {}).get('id')))
                if qt in SCRIM and qp and qp!=pos and (q.get('start') or {}).get('down')==1 and not (en.get('down')==1): cat='TURNOVER'; team=qp
                break
        if cat=='OTHER' and t in ('Rush','Pass Reception') and yds>=20: cat='BIG_PLAY'; team=pos
        # pre-play state
        scrim = t in SCRIM or t in ('Penalty',) and pos
        pc=prev_clock.get(per)
        cl=secs(pc) if pc else 900 if per<5 else 600
        gsr=(max(0,4-per)*900+cl) if per<=4 else cl
        sd=None
        if pos: sd=(ph-pa) if pos==home else (pa-ph)
        rows.append(dict(game_id=gid,play_id=p['id'],seq=int(p['sequenceNumber']),wallclock_ms=ms(p['wallclock']) if p.get('wallclock') else None,
            period=per,clock=clk,type_text=t,text=p['text'],category=cat,team=team,stat_yards=yds,is_scoring=bool(p['scoringPlay']),
            qtr=per,game_seconds_remaining=gsr,score_differential=sd,posteam=pos if t in SCRIM else None,
            posteam_is_home=(pos==home) if (pos and t in SCRIM) else None,
            down=st.get('down') if t in SCRIM else None,ydstogo=st.get('distance') if t in SCRIM else None,
            yardline_100=st.get('yardsToEndzone') if t in SCRIM else None,
            espn_wp_home=wpd.get(p['id'],(None,None))[0],espn_wp_delta=wpd.get(p['id'],(None,None))[1],home=home,away=away,home_score_pre=ph,away_score_pre=pa,home_score=hs,away_score=as_))
        if t not in ('End Period','End of Half','End of Game','End of Regulation','Two-minute warning'): prev_clock[per]=clk
        ph,pa=hs,as_
    return rows
if __name__=='__main__':
    games=json.load(open(os.path.join(D,'espn','games.json')))
    rows=[]
    for g in games:
        if g['state']=='post' and os.path.exists(os.path.join(D,'espn',g['id']+'.json')):
            for r in build_game(g['id']): r['week']=g['week']; rows.append(r)
    df=pd.DataFrame(rows).dropna(subset=['wallclock_ms'])
    df['wallclock_ms']=df.wallclock_ms.astype('int64')
    df.to_parquet(os.path.join(D,'nfl_plays.parquet'))
    print(len(df),df.game_id.nunique());print(df.category.value_counts())
