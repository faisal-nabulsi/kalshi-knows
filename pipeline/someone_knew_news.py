import json,sys,datetime as dt
sys.path.insert(0,"pipeline")
from someone_knew_gdelt import gdelt
Q={
"KXMOVIECAST-XMAN29-ADA":'"Adam Driver" "X-Men"',
"KXALBUMRELEASEDATE-NEWTAY-26DEC01":'"Taylor Swift" album (release OR announces OR "release date")',
"KXALBUMRELEASEDATE-NEWPIT-26DEC01":'Pitbull album (announces OR release OR "new album")',
"KXCOLLEGERANK-TOP20-WU":'"U.S. News" (rankings OR ranked) universities "Washington University"',
"KXCOLLEGEDROP-27-PRI":'"U.S. News" rankings Princeton',
"KXNEWDRUGAPPNTLA-LONV-26OCT01":'Intellia (BLA OR "biologics license") lonvo-z',
"KXGPT-OPEN-26SEP16":'OpenAI "GPT-6"',
"KXBIGBROTHER-26DEC31-RIC":'"Big Brother" "Rick Devens" (wins OR winner OR crowned)',
"KXPIZZASCORE9-26":'Portnoy pizza score 9',
"KXALBUMRELEASEDATETRIPPIE--26SEP01":'"Trippie Redd" album',
"KXCOMPANYLAYOFF-27JAN01-AMZN":'Amazon layoffs',
"KXSONGRELEASEDATE-27DRAK-NOV01":'Drake "Ella Langley" remix',
"KXFEATURE-26FEA-PAR":'PARTYNEXTDOOR "Fear of Missing Out" tracklist',
"KXWEEKSNUM1-26DEC26-TAYL-3":'"Taylor Swift" Billboard 200 number one',
"KXWEEKSNUM1-26DEC26-TSWI-1":'"Patient Zero" Taylor Swift Billboard Hot 100',
"KXNETFLIXRANKMOVIE-26OCT05-UNA":'Netflix Unabomber movie top 10',
"KXCOTTONCANDYLOBSTER-27-JAN01":'"cotton candy" lobster',
"KXAISONG-27":'AI song Billboard Hot 100',
"KXALBUMRELEASEDATE-NEWDRA-26OCT10":'Drake album',
"KXGAMERELEASE-26-HAL":'Halo Campaign Evolved release',
}
if __name__=="__main__":
    ref={r["ticker"]:r for r in json.load(open("pipeline/out/someone_knew/refined.json"))}
    out=json.load(open("pipeline/out/someone_knew/news.json")) if len(sys.argv)>1 else {}
    for t,q in Q.items():
        if t in out or t not in ref: continue
        r=ref[t]; ms=r["move_start_ms"]
        a=gdelt(q,ms-48*3600e3,ms+24*3600e3,75)
        out[t]=a; json.dump(out,open("pipeline/out/someone_knew/news.json","w"))
        print(t,len(a or []),flush=True)
