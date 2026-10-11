"""3 product shots for the 'everything else' line, durations driven by the spoken cues -> build/a2_shot{0,1,2}.mp4"""
import asyncio, json, os, time, glob, subprocess, shutil, re
from playwright.async_api import async_playwright
H = os.path.dirname(os.path.abspath(__file__)); B = f"{H}/build"
API = json.load(open(f"{H}/../docs/config.json"))["api"]; SITE = os.environ.get("SITE", "https://kalshi-knows.pages.dev")
CU = json.load(open(f"{B}/ad2_cues.json")); C = CU["cues"]; end = CU["bounds"]["more"][1]
DUR = [C["sync"] - CU["bounds"]["more"][0], C["agent"] - C["sync"], end - C["agent"]]
TOP = "(sel)=>{const e=document.querySelector(sel);return e?e.getBoundingClientRect().top+scrollY-70:0}"
SLOW = "([dy,d])=>new Promise(r=>{const s=scrollY,t0=performance.now();const f=n=>{const p=Math.min(1,(n-t0)/(d*1000));scrollTo(0,s+dy*p);p<1?requestAnimationFrame(f):r()};requestAnimationFrame(f)})"
async def record():
    rd = f"{B}/a2_rec"; shutil.rmtree(rd, ignore_errors=True)
    async with async_playwright() as p:
        b = await p.chromium.launch(); ctx = await b.new_context(viewport={"width": 1280, "height": 720}, record_video_dir=rd, record_video_size={"width": 1280, "height": 720})
        pg = await ctx.new_page()
        await pg.goto(f"{SITE}/?present=1&quiet=1&api={API}#/live", wait_until="domcontentloaded", timeout=60000)
        try: await pg.wait_for_function("document.querySelector('#live-meta')?.textContent.includes('GAMES TRACKED')", timeout=25000)
        except Exception: print("live-meta wait timed out; continuing")
        await pg.wait_for_timeout(3000)
        MARK = "(()=>{const d=document.createElement('div');d.style.cssText='position:fixed;left:0;top:0;width:60px;height:60px;background:#f0f;z-index:99999';document.body.appendChild(d);setTimeout(()=>d.remove(),450)})()"
        # find a feature element, centre it in view, return its rect (viewport px)
        FIND_RECT = """([kind])=>{const vis=e=>e&&e.offsetParent!==null;
          let el=null,extra=0;
          if(kind==='hide'){const b=[...document.querySelectorAll('button')].find(e=>vis(e)&&/Protect me/.test(e.textContent)); el=b&&b.parentElement; extra=40}
          if(kind==='sync'){const b=[...document.querySelectorAll('button')].find(e=>vis(e)&&/YouTube TV/.test(e.textContent)); el=b&&b.parentElement; extra=40}
          if(kind==='agent'){const t=[...document.querySelectorAll('h2,h3,div,span')].find(e=>vis(e)&&e.children.length<4&&/^KALSHI DEMO EXCHANGE/i.test(e.textContent.trim())); el=t; extra=170}
          if(!el) return null; document.documentElement.style.scrollBehavior='auto';
          const r0=el.getBoundingClientRect(); scrollBy(0, r0.top-170); const r=el.getBoundingClientRect();
          return {x:r.left,y:r.top,w:r.width,h:r.height+extra}}"""
        async def rect(kind):
            for _ in range(5):
                r = await pg.evaluate(FIND_RECT, [kind]); await pg.wait_for_timeout(400)
                if r: return r
            return dict(x=0, y=60, w=1280, h=600)
        global RECTS; rects = RECTS = []
        async def shot(kind, d):
            r = await rect(kind); rects.append(r)
            await pg.evaluate(MARK); await pg.wait_for_timeout(1000 + int(d * 1000))
        click_shield = "[...document.querySelectorAll('[data-shield]')].filter(e=>e.offsetParent).forEach(e=>e.click())"
        await pg.evaluate("[...document.querySelectorAll('button')].filter(e=>e.offsetParent&&/Protect me/.test(e.textContent)).forEach(e=>e.click())"); await pg.wait_for_timeout(500); await shot("hide", DUR[0])
        await pg.evaluate("[...document.querySelectorAll('button')].filter(e=>e.offsetParent&&/Know first/.test(e.textContent)).forEach(e=>e.click())"); await pg.evaluate("[...document.querySelectorAll('button')].filter(e=>e.offsetParent&&/YouTube TV/.test(e.textContent)).forEach(e=>e.click())"); await shot("sync", DUR[1])
        await pg.evaluate("location.hash='#/auto'"); await pg.wait_for_timeout(1800); await pg.evaluate("scrollTo(0,0)"); await shot("agent", DUR[2])
        await ctx.close(); await b.close()
    webm = glob.glob(f"{rd}/*.webm")[0]
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", webm, "-vf", "crop=40:40:0:0,signalstats,metadata=print:key=lavfi.signalstats.UAVG:file=-", "-f", "null", "-"], capture_output=True, text=True).stdout
    fr = re.findall(r"pts_time:([\d.]+)\s+lavfi.signalstats.UAVG=([\d.]+)", r.replace("\n", " ")); marks = []
    for t, u in fr:
        if float(u) > 175 and (not marks or float(t) - marks[-1] > 1.5): marks.append(float(t))
    print("markers", marks)
    if len(marks) < 3: return False
    def crop(r):
        W = max(r["w"] + 80, 640, (r["h"] + 60) * 16 / 9); W = min(W, 1280); Hh = W * 9 / 16
        x = min(max(0, r["x"] + r["w"] / 2 - W / 2), 1280 - W); y = min(max(72, r["y"] + r["h"] / 2 - Hh / 2), 650 - Hh); y = max(72, y)
        return f"crop={int(W)//2*2}:{int(Hh)//2*2}:{int(x)//2*2}:{int(y)//2*2}"
    for i, (w, d) in enumerate(zip(marks[:3], DUR)):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{w + 0.6:.2f}", "-i", webm, "-t", f"{d + 0.1:.3f}", "-vf", f"fps=30,{crop(rects[i])},scale=1920:1080:flags=lanczos", "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", f"{B}/a2_shot{i}.mp4"], check=True)
    return True
for attempt in range(3):
    if asyncio.run(record()): print("shots done"); break
    print("sync flash not found, retrying")
else: raise SystemExit("tour recording failed")
