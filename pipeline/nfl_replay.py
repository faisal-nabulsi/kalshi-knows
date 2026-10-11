"""Build docs/data/replay.json from the most dramatic fully-traded game."""
import os, json, sys
import numpy as np, pandas as pd
sys.path.insert(0,os.path.dirname(__file__))
import nfl_align as A
D=A.D; ROOT=os.path.join(os.path.dirname(__file__),'..')
WORD={'TD':'touchdown','FG':'field goal','TURNOVER':'takeaway','BIG_PLAY':'big play','SAFETY':'safety','OTHER':'big moment'}
def score_game(gid,tr,plays):
    g=plays[plays.game_id==gid]
    lead=np.sign(g.home_score.values-g.away_score.values)
    late=g[g.period>=4]; ll=np.sign(late.home_score.values-late.away_score.values)
    late_changes=int(((ll[1:]*ll[:-1])<0).sum()) if len(ll)>1 else 0
    t,p=A.grid(tr,int(g.wallclock_ms.min()),int(g.wallclock_ms.max()))
    ok=~np.isnan(p); tv=float(np.abs(np.diff(p[ok])).sum()) if ok.sum()>2 else 0
    return tv+2*late_changes, late_changes, len(tr)
def main(pick=None):
    plays=pd.read_parquet(os.path.join(D,'nfl_plays.parquet')); trades=A.load_trades(); gm=json.load(open(os.path.join(D,'game_map.json')))
    sc={gid:score_game(gid,tr,plays) for gid,tr in trades.items() if len(tr)>20000}
    gid=pick or max(sc,key=lambda k:sc[k][0]); print('scores',sorted(sc.items(),key=lambda kv:-kv[1][0])[:5],'picked',gid)
    tr=trades[gid]; g=plays[plays.game_id==gid].sort_values('wallclock_ms'); m=gm[gid]
    s=json.load(open(os.path.join(D,'espn',gid+'.json')))
    comp=s['header']['competitions'][0]
    nick={t['team']['abbreviation']:t['team'].get('shortDisplayName') or t['team'].get('name') or t['team']['abbreviation'] for t in s['boxscore']['teams']}
    home,away=m['home'],m['away']
    lo=int(g.wallclock_ms.min())-120000; hi=int(g.wallclock_ms.max())+60000
    t,p=A.grid(tr,lo,hi,)
    step=2; t2=t[::2]; p2=p[::2]
    keep=~np.isnan(p2); hist=[[int(a),round(float(b),3)] for a,b in zip(t2[keep],p2[keep])]
    # detector
    sw=json.load(open(os.path.join(ROOT,'results','detector_sweep.json'))); thr=sw['recommended_threshold']
    tt,pp=A.grid(tr,lo,hi)
    cand=g[g.category.isin(A.CAND)]
    hl=g[(g.espn_wp_delta.abs()>=0.05)&~g.category.isin(A.CAND)]
    alerts=[]
    for i,(ts,pb,pa) in enumerate(A.detect(tt,pp,thr)):
        d=pa-pb; team=home if d>0 else away
        near=cand[(cand.wallclock_ms>=ts-90000)&(cand.wallclock_ms<=ts+20000)]
        # best match: play whose team matches direction, closest before alert
        near=near[near.team==team] if (near.team==team).any() else near
        if len(near):
            pl=near.iloc[(ts-near.wallclock_ms).abs().argmin()] if False else near.loc[(near.wallclock_ms-ts).abs().idxmin()]
            typ,tm=pl.category,pl.team; lag=(ts-pl.wallclock_ms)/1000
            conf=dict(play_text=pl.text[:220],espn_wallclock_ms=int(pl.wallclock_ms),espn_seen_ms=int(pl.wallclock_ms)+40000,lead_s=round(40-lag,1))
            prob=0.8
        else:
            nh=hl[(hl.wallclock_ms>=ts-90000)&(hl.wallclock_ms<=ts+20000)]
            if len(nh):
                pl=nh.loc[(nh.wallclock_ms-ts).abs().idxmin()]; lag=(ts-pl.wallclock_ms)/1000
                typ,tm,prob='OTHER',team,0.5
                conf=dict(play_text=pl.text[:220],espn_wallclock_ms=int(pl.wallclock_ms),espn_seen_ms=int(pl.wallclock_ms)+40000,lead_s=round(40-lag,1))
            else: typ,tm,conf,prob='OTHER',team,None,0.5
        alerts.append(dict(id=f"a_{i+1}",ts_ms=ts,game_id=gid,team=tm,p_before=round(pb,3),p_after=round(pa,3),delta=round(abs(d),3),
          inferred=[dict(type=typ,team=tm,prob=prob)],headline=f"{nick.get(tm,tm)} {WORD[typ]} ({int(prob*100)}% sure)",confirmed=conf))
    pl_out=[dict(wallclock_ms=int(r.wallclock_ms),text=r.text[:160],type=r.category,team=r.team) for r in cand.itertuples()]
    last=g.iloc[-1]
    game=dict(game_id=gid,short_name=f"{away} @ {home}",home=home,away=away,home_score=int(last.home_score),away_score=int(last.away_score),period=int(last.period),clock=last.clock,
      status="post",possession=None,situation="Final",kalshi_home=m['ticker'],kalshi_away=m['ticker'].rsplit('-',1)[0]+'-'+away,p_home=hist[-1][1],
      team_names=nick)
    out=dict(game=game,history=hist,alerts=alerts,plays=pl_out,meta=dict(detector_threshold=thr,assumed_stream_delay_s=40,date_utc=m['date']))
    json.dump(out,open(os.path.join(ROOT,'docs','data','replay.json'),'w'),separators=(',',':'))
    print(os.path.getsize(os.path.join(ROOT,'docs','data','replay.json')),len(hist),len(alerts),sum(a['confirmed'] is not None for a in alerts))
if __name__=='__main__': main(sys.argv[1] if len(sys.argv)>1 else None)
