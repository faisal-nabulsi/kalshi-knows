import json,sys,datetime as dt
sys.path.insert(0,"pipeline")
from someone_knew_gdelt import gdelt
Q={
"KXGAMERELEASE-26-HAL":'Halo "Campaign Evolved" release',
"KXPIZZASCORE9-26":'Portnoy pizza "9.0"',
"KXAISONG-27":'AI song "Hot 100"',
"KXMEDIARELEASEDATEAHS-26-OCT01-AME":'"American Horror Story" premiere date',
"KXPERFORMVS-26-MEG":'"Victoria\'s Secret" Fashion Show "Megan Thee Stallion"',
"KXCOMPANYLAYOFF-27JAN01-AMZN":'Amazon layoffs employees cuts',
"KXNETFLIXRANKMOVIERUNNERUP-26OCT05-WID":'Netflix "The Widower" top 10',
"KXNETFLIXRANKMOVIE-26OCT05-UNA":'Netflix Unabomber top 10',
"KXNEWDRUGAPPNTLA-LONV-26OCT01":'Intellia lonvo-z BLA submission',
"KXFEATURE-26FEA-PAR":'Drake FOMO PARTYNEXTDOOR',
"KXWEEKSNUM1-26DEC26-TAYL-3":'"Taylor Swift" Billboard 200 No. 1',
}
ref=json.load(open("pipeline/out/someone_knew/ref_all.json"))
out=json.load(open("pipeline/out/someone_knew/news.json"))
for t,q in Q.items():
    if t not in ref: print("missing",t); continue
    ms=ref[t]["move_start_ms"]
    a=gdelt(q,ms-12*3600e3,ms+30*3600e3,60) or []
    out[t+"#3"]=a; json.dump(out,open("pipeline/out/someone_knew/news.json","w"))
    print("==",t,dt.datetime.fromtimestamp(ms/1000,dt.UTC).strftime("%m-%d %H:%M"),ref[t]["p_before"],ref[t]["p_after"],ref[t]["sub"],flush=True)
    seen=set()
    for x in a:
        if x["title"] in seen: continue
        seen.add(x["title"]); print("  %+5.0f"%((x["ms"]-ms)/60000),x["src"][:20],x["title"][:90],flush=True)
        if len(seen)>=8: break
