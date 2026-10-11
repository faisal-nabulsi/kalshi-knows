import sys,json,datetime as dt
sys.path.insert(0,"pipeline")
from someone_knew_scan import series
def refine(m):
    yes=m["result"]=="yes"; c=m["cross_ts"]
    s=series(m,1,c-6*3600,c+2*3600)
    # forward-fill to 1-min grid
    pts=[];
    for t,p,v in s: pts.append((t*1000,p))
    f=(lambda p:p) if yes else (lambda p:1-p)
    q=[f(p) for _,p in pts]
    th=(m['pre']+m['post'])/2
    i=max((j for j,v in enumerate(q) if v<=th and pts[j][0]<=(c+7200)*1000),default=None)
    if i is None or i+1>=len(q): return None
    st=i+1
    pre=min(q[max(0,st-60):st]); post=max(q[st:st+90])
    hi=[j for j in range(st,len(q)) if q[j]>=pre+0.9*(post-pre)]
    en=hi[0] if hi else st
    ser=[[a,round(b,4)] for a,b in pts]
    while len(ser)>400: ser=ser[::2]
    return dict(move_start_ms=pts[st][0],move_end_ms=pts[en][0],p_before=round(pre if yes else 1-pre,4),p_after=round(post if yes else 1-post,4),series=ser,pre_t=pts[max(0,st-1)][0])
if __name__=="__main__":
    mv=json.load(open(sys.argv[1])); out=[]
    for m in mv:
        r=refine(m)
        if r: out.append({**m,**r}); print(m["ticker"],dt.datetime.fromtimestamp(r["move_start_ms"]/1000,dt.UTC),r["p_before"],r["p_after"],m["title"][:50],m["sub"])
    json.dump(out,open("pipeline/out/someone_knew/refined.json","w"))
