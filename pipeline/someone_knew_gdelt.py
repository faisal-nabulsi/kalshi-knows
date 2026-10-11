import sys,time,requests,datetime as dt,urllib.parse,json
_last=0
def gdelt(q,start_ms,end_ms,n=75):
    global _last
    f=lambda ms:dt.datetime.fromtimestamp(ms/1000,dt.UTC).strftime("%Y%m%d%H%M%S")
    url="https://api.gdeltproject.org/api/v2/doc/doc?"+urllib.parse.urlencode(dict(query=q,mode="ArtList",format="json",maxrecords=n,sort="DateAsc",startdatetime=f(start_ms),enddatetime=f(end_ms)))
    for i in range(4):
        w=_last+6-time.time()
        if w>0: time.sleep(w)
        _last=time.time()
        try: r=requests.get(url,timeout=40); 
        except requests.RequestException: continue
        if r.text.startswith("{"):
            try: a=r.json().get("articles",[])
            except Exception: a=[]
            return [dict(ms=int(dt.datetime.strptime(x["seendate"],"%Y%m%dT%H%M%SZ").replace(tzinfo=dt.UTC).timestamp()*1000),title=x["title"],url=x["url"],src=x["domain"]) for x in a]
    return None
if __name__=="__main__":
    q,ms=sys.argv[1],int(sys.argv[2])
    h=float(sys.argv[3]) if len(sys.argv)>3 else 48
    for a in (gdelt(q,ms-int(h*3600e3),ms+24*3600e3) or [])[:int(sys.argv[4]) if len(sys.argv)>4 else 25]:
        print(dt.datetime.fromtimestamp(a["ms"]/1000,dt.UTC).strftime("%m-%d %H:%M"),a["src"],a["title"][:110])
