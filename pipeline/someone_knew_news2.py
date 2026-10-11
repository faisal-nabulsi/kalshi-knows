import json,sys
sys.path.insert(0,"pipeline")
from someone_knew_gdelt import gdelt
Q={
"KXGPT-OPEN-26SEP16":('OpenAI GPT-6 Astra (rolls OR launches OR releases OR unveils OR announces)',12,30),
"KXALBUMRELEASEDATE-NEWPIT-26DEC01":('Pitbull Pitcoin',12,36),
"KXALBUMRELEASEDATETRIPPIE--26SEP01":('"Trippie Redd" album (announces OR "release date" OR drops)',12,36),
"KXNEWDRUGAPPNTLA-LONV-26OCT01":('Intellia BLA',12,48),
"KXIPOANTHROPIC-DATE-26OCT01":('Anthropic IPO',6,24),
"KXGEMINI-GEM4-26OCT01":('Google Gemini',6,24),
}
ref={r["ticker"]:r for r in json.load(open("pipeline/out/someone_knew/refined.json"))}
out=json.load(open("pipeline/out/someone_knew/news.json"))
for t,(q,b,a) in Q.items():
    if t not in ref: print("missing",t); continue
    ms=ref[t]["move_start_ms"]
    out[t]=gdelt(q,ms-b*3600e3,ms+a*3600e3,75); json.dump(out,open("pipeline/out/someone_knew/news.json","w")); print(t,len(out[t] or []),flush=True)
